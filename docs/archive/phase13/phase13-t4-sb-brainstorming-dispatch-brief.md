# Phase 13 T4.SB — Brainstorming Dispatch Brief

**Audience:** Fresh Claude Code instance dispatched as the T4.SB brainstorming implementer. No prior conversation context.

**Mission:** Produce a brainstorming spec doc + OQ list at `docs/superpowers/specs/2026-05-22-phase13-t4-sb-closer-design.md` (or operator-paired-named equivalent) that scopes the Phase 13 closer covering 7 operator-supplied triage items + identifies investigations the executing-plans phase will need to perform.

**T4.SB is the Phase 13 closer** — Phase 13 sub-bundle ship count is currently 11 of 11 SHIPPED; this brainstorming dispatch begins the path to 12 of 12 SHIPPED / Phase 13 FULLY CLOSED.

**Workflow:** `copowers:brainstorming` skill (wraps `superpowers:brainstorming` with adversarial Codex MCP review). Expected 2-5 Codex rounds — operator-supplied 7-item triage list is well-structured + framings are explicit; pre-Codex discipline now at 27 cumulative validations.

**Branch:** `phase13-t4-sb-brainstorming` — branches from main HEAD `6e3ed06` (post-research-question-banking).

**Worktree:** create via `git worktree add .worktrees/phase13-t4-sb-brainstorming phase13-t4-sb-brainstorming`. Work runs from that worktree's cwd. Invoke `python -m swing.cli` (NOT bare `swing`) per `feedback_worktree_cli_invocation`.

**Expected duration:** ~3-6 hours operator-paced (per `feedback_time_estimates_overstated.md` ÷3-5x). Spec doc target: ~500-900 lines (T2.SB6c brainstorming spec was 659 lines + this brief scopes more disparate items so likely the upper end).

---

## §0 Read first (in this order)

1. **`docs/phase3e-todo.md` "T4.SB triage items" section (lines 11-101)** — PRIMARY SCOPE SUBSTRATE. 7 items (Items 1-7) each with 5-field-template scaffolding per spec §7.3. Read end-to-end:
   - Item 1 — 0 A+ candidates diagnostic (HIGH severity)
   - Item 2 — Path A labeler subagent contract widening (Medium severity)
   - Item 3 — Market weather chart volume-axis noise (Cosmetic)
   - Item 4 — Lightning icon offsets thumbnails (Cosmetic/UX)
   - Item 5 — Chart scope too narrow + JIT/flat-file architectural Q (Medium severity; orchestrator recommendation REVISED to JIT-primary per operator framing)
   - Item 6 — Watchlist expand-then-collapse loses thumbnail (UX)
   - Item 7 — Metrics wiring audit + hyp-progress=0 defect (HIGH severity)

2. **`docs/superpowers/specs/2026-05-18-phase13-charts-patterns-autofill-usability-design.md`** — Phase 13 main spec. T4.SB scope per main-spec §7.3 was originally "Q4 close-tracking flag + Theme 4 usability" but Q4 schema landed in v20 per migration `0020_phase13_charts_patterns_autofill_usability.sql:262-307`, so **T4.SB scope shrinks to Theme 4 usability work only** (i.e., the 7 operator-supplied triage items). The main spec is reference-only for T4.SB scope; the BINDING substrate is the 7 triage items.

3. **`docs/phase13-t2-sb6c-executing-plans-return-report.md`** — T2.SB6c return report. **§4.1 V1 simplifications banked** (8 NEW; some directly relevant to T4.SB scope): row 1 OQ-6 outcome distribution surrogate (relates to Item 7 metrics audit); row 4 exemplar cache-miss write-through skip (relates to Item 5 JIT/flat-file decision); row 5 market_weather literal `trend_template_state="stage_2"` (related to Item 3 chart-rendering audit).

4. **`research/phase-0-tasks.md`** "Later (deferred)" — research-branch banking on A+-like-indicators applied-research question. **Item 1 diagnostic outcome feeds the research-branch first-method-record selection.** T4.SB brainstorm should explicitly acknowledge the cross-branch dependency.

5. **`CLAUDE.md`** at repo root — project conventions + 117+ cumulative gotchas. ESPECIALLY relevant for T4.SB brainstorming phase:
   - **Form-render anchor lifecycle audit (NEW Expansion #9 candidate BINDING for 28th cumulative validation)** — banked at T2.SB6c executing-plans 2026-05-22 PM
   - **SQL aggregation UNIT audit (Expansion #8 candidate BINDING)** — banked at T2.SB6c writing-plans
   - **Brief-vs-actual schema reality check + SQL skeleton column verification (Expansion #4 refinement BINDING)** — banked at T2.SB6c brainstorming
   - **Grouping-key fields need canonicalization-at-persistence-boundary, not just display safety** — orchestrator-context archive Tranche B-ops lesson; DIRECTLY APPLIES to Item 7 root-cause-(a)
   - **HTMX OOB-swap partials that hand-duplicate full-page markup drift silently** — DIRECTLY APPLIES to Item 6
   - **Matplotlib mathtext fires on `$`, `^`, `_`, unbalanced `\`** — applies to Item 3 chart-rendering work
   - **Server-recompute at POST (T3.SB3 R1 M#2 LOCK)** — applies to any new POST handlers in T4.SB scope
   - **F6 transient-empty defense at construction barrier** — applies to chart_renders write paths in Item 5 architecture work
   - **§A.14 paired discipline** — applies to any schema-touching work (T4.SB likely does NOT need schema changes; main spec §7.3 LOCK confirmed Q4 schema already landed in v20)

6. **`docs/orchestrator-context.md`** "Currently in-flight work" + "Recent decisions and framings" — current state reflects Phase 13 11 of 11 SHIPPED + T4.SB paused. Three-branch architecture context.

---

## §1 Operator-confirmed severity + framing (BINDING)

Per operator-paired triage 2026-05-22 PM (post-S2-S11 gate run + 7-item triage list assembly): **operator concurred with orchestrator-triaged severities** for all 4 TBD-severity items (1, 2, 5, 7). All 7 items now have operator-confirmed severity + verbatim operator framing per `docs/phase3e-todo.md:15-101`.

Highlights for brainstorming phase scope:

- **Item 1 (HIGH)**: "Purpose is to enter trades and make profit. No candidates = no trades. Conservative answer, but does not meet mission (ships are designed to go to sea...)" — operator framing emphasizes that 0 A+ over 63 eval runs is a **mission-critical gap**, NOT just a calibration question. Brainstorming should treat this with high urgency.

- **Item 2 (Medium)**: "Similar to 1. Potentially too limiting, making it more difficult to identify good entry opportunities." — rhymes with Item 1; both items represent restrictions on operator's setup-discovery workflow. Brainstorming should consider whether Item 2 fix should fold into Item 1 fix (e.g., if Item 1 diagnostic surfaces that the detector pipeline + labeler emit contract are coupled, then Item 1 fix may naturally widen the labeler contract).

- **Item 5 (Medium)**: orchestrator recommendation REVISED to **JIT-primary with minimal pre-gen for market_weather + position_detail only** post operator framing. Operator's concerns: (a) archive bloat ("Likely not an issue for modern hardware for a very, very long time but just worth a question"); (b) re-run collision handling ("How is that handled WRT to the raster charts? Charts dynamically created would not have this issue"). Both concerns argue FOR JIT semantics. See §3 below for OQ surface.

- **Item 7 (HIGH)**: "The metrics need a thorough review to ensure they are properly hooked up. Specific example: the hypothesis progress card is reporting 0 for all hypothesis which is incorrect, several sub-A+ VCP not formed having been executed. two wins are running, several losses have been closed." — operator framing distinguishes specific defect (hyp-progress=0) from broader scope (metrics audit). Brainstorming should preserve both — specific-defect fix + broader audit.

---

## §2 Scope (BINDING for brainstorming phase output)

The brainstorming spec MUST cover all 7 items + identify cross-item architectural relationships. Per operator decision 2026-05-22 PM: **no merge/drop/additions** — list of 7 stands as-is. The spec MAY surface natural cross-item couplings (e.g., Item 1 + Item 7 share the "false-zero on closed-loop surface" failure-mode family; Item 5 + Item 6 share HTMX-OOB-swap + chart-rendering territory).

### §2.1 Per-item scope summary (cross-reference `docs/phase3e-todo.md:15-101`)

| Item | Severity | Investigation needed? | Architectural decision? | Cosmetic/UX-only? |
|---|---|---|---|---|
| 1 — 0 A+ candidates diagnostic | HIGH | YES (instrument `bucket_for`; capture blocking-criterion distribution) | YES (may surface threshold-loosening proposals) | No |
| 2 — Path A labeler subagent contract widening | Medium | NO (architectural; contract change) | YES (silver-label emit contract; coupled with Item 1) | No |
| 3 — Market weather volume-axis noise | Cosmetic | NO | NO | YES |
| 4 — Lightning icon removal | Cosmetic/UX | NO | NO | YES |
| 5 — Chart scope + JIT/flat-file | Medium | NO (orchestrator recommendation REVISED to JIT-primary) | YES (cache architecture decision; retention policy OQ) | No |
| 6 — Watchlist expand→collapse thumbnail loss | UX | NO (canonical HTMX-OOB-swap gotcha applies) | NO | Almost-yes (1-template fix) |
| 7 — Metrics wiring audit | HIGH | YES (instrument `compute_hypothesis_progress_breakdown`; identify root cause of 3 candidates; broader audit) | NO (mostly fix-the-wiring; audit scope) | No |

### §2.2 Cross-item couplings (brainstorming spec should explicitly enumerate)

- **Item 1 ↔ Item 7**: shared "false-zero on closed-loop surface" failure-mode family. Item 1 diagnostic output (which criteria block A+ candidates) may inform Item 7 broader audit (e.g., other metric surfaces may have analogous filter-too-tight issues).
- **Item 1 ↔ Item 2**: if Item 1 diagnostic surfaces that detector pipeline + labeler emit contract are coupled, Item 2 fix may naturally fold in.
- **Item 1 ↔ Research branch**: per `research/phase-0-tasks.md` "Later (deferred)" — Item 1 diagnostic output feeds research-branch first-method-record selection. Brainstorming spec should NOT pre-commit to a research outcome; just acknowledge the cross-branch dependency.
- **Item 5 ↔ Item 6**: both touch HTMX-driven dashboard watchlist surface. Item 5 architecture decision (JIT cache-miss live-render) constrains the partial-template structure that Item 6 collapse-handler must round-trip. Coupling worth flagging.
- **Item 3 ↔ Items 4-6**: chart-rendering surfaces all share `swing/web/charts.py` + `swing/web/templates/partials/` surface area. Brief consolidation possible (Item 3 fix surfaces other axis-label cleanup opportunities; Item 4 lightning-glyph removal could reveal other cosmetic items in the watchlist row).

### §2.3 Investigation priorities (executing-plans phase sequencing)

Per the brainstorming spec, the executing-plans phase should sequence:

1. **Item 1 diagnostic FIRST** (`bucket_for` instrumentation + run against operator DB + identify blocking-criterion distribution). Output: data + analysis that informs Items 2 + 5 + 7 broader audit + research-branch first-method-record selection.
2. **Item 7 specific-defect diagnostic SECOND** (`compute_hypothesis_progress_breakdown` instrumentation + identify which of 3 root-cause candidates).
3. **Item 7 broader metrics audit THIRD** (enumerate ALL metric surfaces; per-surface verify data-source + filter + join + add discriminating round-trip test).
4. **Item 5 architecture work FOURTH** (JIT cache-miss live-render fallback + minimal pre-gen for market_weather + position_detail; retention policy decision per OQ).
5. **Item 2 labeler contract widening FIFTH** (architectural; depends on Item 1 outcome).
6. **Items 3 + 4 + 6 (cosmetic/UX) IN PARALLEL** with other tasks OR last (small file:line edits; minimal Codex risk; can fold into closer task).

---

## §3 Open questions (OQs) for operator-paired triage post-brainstorming

The brainstorming spec MUST surface these OQs (and any others surfaced during exploration) for operator-paired triage before writing-plans dispatch:

### §3.1 Item 1 — 0 A+ candidates diagnostic

- **OQ-1.1**: Diagnostic output format — CLI subcommand (e.g., `swing diagnose aplus-blockers`) + CSV / Markdown analysis report? OR fold into existing pipeline step output? OR research-branch `research/notes/`?
- **OQ-1.2**: Diagnostic time-window — single eval_run? rolling N eval_runs? full 63-run history?
- **OQ-1.3**: Post-diagnostic action threshold — what fraction of blocking-criterion concentration would warrant immediate threshold loosening vs. just banking findings for research?
- **OQ-1.4**: Should the diagnostic instrument live in production (`swing/`) or research branch (`research/`)? V2.1 §V branch posture argues research; operational urgency may argue swing.

### §3.2 Item 2 — Path A labeler subagent contract widening

- **OQ-2.1**: Subagent emit contract — new keys `rule_criteria` + `narrative` schema? (per-rule pass/fail + threshold + tolerance + per-criterion narrative paragraph?)
- **OQ-2.2**: Re-label existing 34 corpus exemplars OR only emit new contract on FRESH exemplars going forward?
- **OQ-2.3**: V1 Path C backfill script retention — keep as fallback for future cohort imports?

### §3.3 Item 5 — Chart scope + JIT/flat-file architecture

- **OQ-5.1**: Cache retention policy — should chart_renders rows older than N pipeline_runs be auto-evicted? If yes, N = ? (operator's archive-bloat concern; back-of-envelope ~1.3GB/year unbounded).
- **OQ-5.2**: JIT cache-miss render latency budget — what's the upper bound on first-render time before falling back to "Chart loading..." placeholder + async-render? (matplotlib first-render is typically 200-500ms; operator's expand-and-view UX expects sub-second)
- **OQ-5.3**: Pre-gen scope — orchestrator recommendation is "market_weather + position_detail ONLY" (NOT watchlist top-N, NOT hyp-rec A+). Operator confirms or counter-proposes?
- **OQ-5.4**: Re-run collision semantics — when pipeline runs multiple times in a day, dashboard reads "latest completed pipeline_run" cache rows. JIT cache-miss path adds new rows for whatever pipeline_run_id is "current" at the time of expand. Acceptable, or should JIT path always read most-recent-overall regardless of pipeline_run? (Operator framing suggests latter — "simply use the most recent data in the cache".)
- **OQ-5.5**: Chart-unavailable banner removal — once JIT path lights up, the `swing/web/chart_scope.py:130-131` banner text becomes unreachable. Delete the banner code path OR keep as fallback for genuine errors (e.g., OHLCV cache empty)?

### §3.4 Item 7 — Metrics wiring audit

- **OQ-7.1**: Diagnostic-then-fix vs. parallel — should the Item 7 specific-defect diagnostic ship as a separate fix-bundle ahead of the broader audit, or fold into the broader audit as a single task?
- **OQ-7.2**: Broader audit scope — enumerate every metric surface in `swing/metrics/` + `swing/web/view_models/metrics/` + dashboard cards. Per-surface verify (i) data source query against current operator DB row distribution; (ii) state-filter scope vs operator expectation; (iii) join semantics vs persisted FK reality; (iv) discriminating round-trip test. Operator confirms scope, or wants narrower (e.g., only the surfaces that currently report zeros)?
- **OQ-7.3**: Canonicalization-at-persistence-boundary fix for hypothesis_label — strip "(watch); failed: ..." suffix at entry-form POST? OR matching logic in `compute_hypothesis_progress_breakdown` does prefix-match? Per orchestrator-context Tranche B-ops precedent, canonicalize at persistence is preferred.

### §3.5 Items 3, 4, 6 — cosmetic/UX fixes

These items are bounded enough to skip OQs in most cases. Brainstorming spec may surface 1-2 OQs if exploration reveals non-obvious decisions (e.g., Item 4 lightning-glyph removal may surface "should `% to pivot` column gain a color-coded visual indicator to compensate for the removed glyph?").

### §3.6 Phase 13 closure marker + post-T4.SB sequencing

- **OQ-CL.1**: Phase 13 formal CLOSURE marker — at T4.SB SHIPPED, update CLAUDE.md current-state line + orchestrator-context "Currently in-flight work" with "Phase 13 FULLY CLOSED — 12 of 12 sub-bundles SHIPPED". Operator confirms naming?
- **OQ-CL.2**: Phase 14 trigger — does T4.SB SHIPPED kick off Phase 14 (operator-defined), OR does the project transition to Applied Research branch focus per V2.1 §X tranche progression?
- **OQ-CL.3**: Research-branch first-method-record selection — schedule immediately post-T4.SB-SHIPPED (Item 1 diagnostic in hand), or hold for separate operator-paired session?

---

## §4 Sub-bundle decomposition (preview; brainstorming spec produces the BINDING decomposition)

Suggested per-task decomposition for the brainstorming spec to refine (not BINDING; spec output is authoritative):

- **T-T4.SB.1** — Item 1 diagnostic + Item 7 specific-defect diagnostic (combined investigation task; outputs analysis docs)
- **T-T4.SB.2** — Item 7 broader metrics audit (enumeration + per-surface verification + discriminating tests)
- **T-T4.SB.3** — Item 5 architecture work (JIT cache-miss + retention policy implementation; minimal pre-gen)
- **T-T4.SB.4** — Item 2 labeler subagent contract widening
- **T-T4.SB.5** — Items 3 + 4 + 6 cosmetic/UX fixes (bundled small-file edits)
- **T-T4.SB.6** — Closer (1 fast E2E + ruff sweep + Phase 13 closure docs + cross-bundle pin row 13 if needed)

Concurrent dispatch potential: T-T4.SB.4 (labeler) + T-T4.SB.5 (cosmetic) can run concurrent with the investigation tasks if implementer prefers. T-T4.SB.6 closer is sequential.

Expected test delta: ~50-150 fast tests + 1 fast E2E. Schema UNCHANGED (T4.SB doesn't touch schema; Q4 already in v20; v21 trades backlinks already in place). Baseline 5670 → ~5720-5820 fast post-T4.SB.

---

## §5 Watch items + cumulative discipline (BINDING for brainstorming phase)

### §5.1 Pre-Codex 7-expansion + 3 NEW refinements (28th cumulative C.C lesson #6 validation expected)

Brainstorming phase pre-Codex review applies ALL 7 expansions + 3 NEW refinements banked at recent dispatches:

1. **Expansion #1** — hardcoded-duplicate audit (T3.SB2 hotfix `cf3c489`)
2. **Expansion #2** — brief-vs-spec source-of-truth + brief-vs-actual schema reality check (T2.SB4 + T2.SB6c brainstorm)
3. **Expansion #3** — schema-CHECK-vs-semantic-contract gap audit (T2.SB6a R1 CRITICAL #1)
4. **Expansion #4** — CLAUDE.md gotcha specific-scenario trace **PLUS NEW REFINEMENT** SQL skeleton column verification (T2.SB6c brainstorm + writing-plans banking)
5. **Expansion #5** — cross-section spec inventory grep (T2.SB6a R1 MAJOR #3)
6. **Expansion #6** — content-completeness audit (T2.SB6b lessons)
7. **Expansion #7** — cross-row semantic SCOPE audit + **NEW BOUNDARY CLARIFICATION** scope-vs-unit (T2.SB6b + T2.SB6c brainstorm + writing-plans bankings)
8. **Expansion #8 (NEW CANDIDATE BINDING)** — per-aggregation-function UNIT audit on SQL skeletons (T2.SB6c writing-plans banking)
9. **Expansion #9 (NEW CANDIDATE BINDING)** — form-render anchor lifecycle audit 4-dimension (T2.SB6c executing-plans banking) — DIRECTLY APPLIES if T4.SB introduces any new hidden form anchors; brainstorm should explicitly enumerate the 4 lifecycle dimensions per any new anchor

### §5.2 4 NEW gotchas from T2.SB6c writing-plans banking (BINDING)

- (9) SQL aggregation UNIT audit (Expansion #8 candidate)
- (10) Existing-field reuse audit before claiming new dataclass fields
- (11) Template-rendering surface audit before claiming "no template edit needed"
- (12) `date.fromisoformat()` discipline for cross-type-boundary calls

### §5.3 NEW gotcha from T2.SB6c executing-plans (BINDING)

- (13) Form-render anchor lifecycle audit (Expansion #9 candidate) — 4 dimensions per anchor

### §5.4 Cumulative process discipline

- **NO Co-Authored-By footer** — cumulative ~370+ commit streak ZERO trailer drift through T2.SB6c executing-plans housekeeping at `5f0368f` + research banking at `6e3ed06`; do NOT regress. Cite per fresh forward-binding lesson #7 (Phase 12 Sub-sub-bundle C.B 2026-05-15) in every commit message.
- **`python -m swing.cli` from worktree cwd**, NOT bare `swing` (per `feedback_worktree_cli_invocation`)
- **ASCII-only on runtime CLI paths** + template narrative text (Windows cp1252 stdout safety)
- **TDD per task** via `superpowers:test-driven-development`
- **Edit tool for per-file edits**
- **Cite the discipline in commit messages** per cumulative precedent

### §5.5 Cumulative discipline NOT in scope for T4.SB (Q4 already in v20; v21 trades backlinks already landed)

T4.SB is expected to be SCHEMA-UNCHANGED. The brainstorming spec should NOT propose any schema changes unless investigation surfaces an absolute necessity (e.g., a retention-policy table for chart_renders archive purging). If schema changes ARE proposed, §A.14 paired discipline + backup-gate strict-equality + migration runner discipline all apply per cumulative precedent.

---

## §6 Done criteria for brainstorming-phase output

The brainstorming spec at `docs/superpowers/specs/2026-05-22-phase13-t4-sb-closer-design.md` (or operator-paired-named equivalent) MUST cover:

- [ ] **§A Status + scope** — 7 triage items + operator-confirmed severity + framing; cross-references to T2.SB6c return report + research branch
- [ ] **§B Per-item investigation + design** — for each of the 7 items: (i) what to investigate; (ii) what architectural decisions need locking; (iii) what code surfaces are touched; (iv) what discriminating tests pin the behavior
- [ ] **§C Cross-item couplings** — Items 1 ↔ 7, 1 ↔ 2, 1 ↔ research, 5 ↔ 6, 3 ↔ 4-6
- [ ] **§D Investigation outputs format** — Item 1 diagnostic + Item 7 specific-defect diagnostic + Item 7 broader audit
- [ ] **§E Cross-bundle pin** — does T4.SB introduce a NEW cross-bundle pin row 13 (e.g., chart_renders retention policy invariant)? Or close existing pins?
- [ ] **§F Test scope projection** — per-task test budget; baseline 5670 → ~5720-5820 fast expected
- [ ] **§G Sub-bundle decomposition** — T-T4.SB.1..T-T4.SB.6 (or as refined) with per-task acceptance criteria + commit message templates
- [ ] **§H Dispatch sequence** — investigation-first sequencing (Item 1 + Item 7 specific-defect → Item 7 broader audit → architecture → labeler → cosmetics → closer); concurrent dispatch potential noted
- [ ] **§I Forward-binding lessons inherited** — from T2.SB6c executing-plans + writing-plans + brainstorming + cumulative gotcha set
- [ ] **§J Open questions** — surface OQs per §3 above + any new ones surfaced during exploration. Operator-paired triage post-brainstorming locks dispositions before writing-plans dispatch.
- [ ] **§K Phase 13 closure marker** — T4.SB SHIPPED transitions Phase 13 to "12 of 12 sub-bundles SHIPPED / Phase 13 FULLY CLOSED"; sub-bundle ship count update at CLAUDE.md + orchestrator-context
- [ ] **§L References** — `docs/phase3e-todo.md:15-101` (PRIMARY); T2.SB6c return reports; Phase 13 main plan + spec; CLAUDE.md gotcha references; `research/phase-0-tasks.md` cross-branch dependency

Brainstorming-phase Codex chain expected 2-5 rounds. Pre-Codex 7-expansion + 3 NEW refinements (Expansion #4 + #8 + #9 candidates) + 5 NEW gotchas (#9-#13) discipline BINDING; verdict per expansion captured in brainstorming return report.

---

## §7 NON-scope (V2 / future arc / explicitly out of T4.SB)

- **Phase 14 (operator-defined; pending)** — Phase 13 closure marker only at T4.SB SHIPPED; Phase 14 dispatch separate
- **Research branch advancement** — Item 1 diagnostic OUTPUT informs research-branch first-method-record selection but the research-branch authoring itself is NOT in T4.SB scope per V2.1 §V branch-posture (research branch is separately governed; T4.SB SHIPPED unblocks research-branch progress but doesn't drive it)
- **Schema changes** — Q4 already in v20; v21 trades backlinks already in place; T4.SB should NOT propose schema changes unless investigation surfaces absolute necessity
- **ZERO new Schwab API calls** (L2 LOCK preserved per Phase 13 arc cumulative discipline)
- **V2 candidates from T2.SB6c return report §4.1** — most preserved as V2-banked; T4.SB may close Item 7 broader-audit-implied false-zero candidates (row 1 OQ-6 outcome distribution surrogate, row 5 market_weather literal trend_template_state) if investigation surfaces evidence

---

## §8 Post-brainstorming handback

When brainstorming Codex chain converges to NO_NEW_CRITICAL_MAJOR:

1. Write return report at `docs/phase13-t4-sb-brainstorm-return-report.md` per cumulative precedent (commit chain + per-expansion verdict + Codex chain shape + forward-binding lessons + V2 candidates banked + cumulative streaks).
2. Inline self-verification: ruff check; schema unchanged at v21 (brainstorming touches docs only); baseline 5670 fast tests UNCHANGED.
3. Hand back to operator with summary.

Orchestrator-side next steps post-brainstorming:
- Operator-paired OQ triage (per §3 above + any new ones surfaced)
- Merge brainstorming branch `--no-ff` to main + post-merge housekeeping
- Draft T4.SB writing-plans dispatch brief
- Continue copowers chain: writing-plans → executing-plans → operator-witnessed gates → merge + housekeeping → Phase 13 FULLY CLOSED marker

---

*End of T4.SB brainstorming dispatch brief. 7 operator-confirmed triage items (Items 1-7 per `docs/phase3e-todo.md:15-101`); 4 severity ratings operator-confirmed 2026-05-22 PM concurring with orchestrator triage; 3 items have verbatim operator framing (1, 2, 5 + cosmetic/UX items 3, 4, 6, 7 already verbatim from prior turns); pre-Codex 7-expansion + 3 NEW refinements + 5 NEW gotchas (#9-#13) BINDING for 28th cumulative C.C lesson #6 validation; ~370+ ZERO Co-Authored-By footer streak preserved through this brief commit; Phase 13 sub-bundle ship count currently 11 of 11 → T4.SB SHIPPED transitions to 12 of 12 / Phase 13 FULLY CLOSED; research branch first-method-record selection unblocks post-T4.SB-Item-1-diagnostic SHIPPED per `research/phase-0-tasks.md` "Later (deferred)".*
