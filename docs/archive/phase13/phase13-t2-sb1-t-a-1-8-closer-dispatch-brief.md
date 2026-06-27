# Phase 13 T2.SB1 — T-A.1.8 Closer Dispatch Brief

**Audience:** Fresh Claude Code instance dispatched as the T-A.1.8 closer implementer. No prior conversation context.

**Mission:** Close the T2.SB1 sub-bundle on the worktree branch by (1) wiring the random-15% Codex 2nd-reviewer dispatch per spec §5.9 step 4 + OQ-5 phased rollout; (2) shipping the cassette-mode E2E test exercising silver → Codex disagreement → codex_silver row insertion; (3) closing 2 surgical ship-defects surfaced at the T-A.1.7 operator-paired session (relabel-promote-to-gold SQL bug + FlatBaseEvidence schema gap); (4) full-suite verification + ruff sweep + final return report. After T-A.1.8 closes + orchestrator QA + Codex chain to NO_NEW_CRITICAL_MAJOR, the orchestrator merges T2.SB1 (first per OQ-12 Option E) then T3.SB1 (second; already SHIPPED on sibling worktree).

**Brief:** `docs/phase13-t2-sb1-t-a-1-8-closer-dispatch-brief.md` (THIS file; committed on worktree branch).

**Scope envelope:** ~120-200 LOC production + ~250-400 LOC test + 1 cassette test infrastructure update. ~2-3 Codex rounds expected.

---

## §0 Status at session start

- **Worktree:** `.worktrees/phase13-t2-sb1-dev-time-labeling-infra/` (you operate here).
- **Branch:** `phase13-t2-sb1-dev-time-labeling-infra` (HEAD `bd0775f` = T-A.1.7 corpus committed).
- **Schema:** v20 (UNCHANGED through T-A.1.5b hotfix + T-A.1.7 corpus).
- **Baseline:** 5068 fast tests passing / 6 skipped / ruff 0 errors / ZERO Co-Authored-By footer drift across 22 worktree commits (1 T-A.1.1 + 1 interim report + 8 T-A.1.1b..T-A.1.6 + 2 briefs (T-A.1.7 + T-A.1.5b) + 10 T-A.1.5b hotfix + 1 T-A.1.7 corpus = 22).
- **Branch base:** main HEAD `6383cfa` (pre-dispatch).
- **T-A.1.1 SHA (for T3.SB1 coordination; unchanged):** `4cfd5f2`. T3.SB1 is SHIPPED on a sibling worktree awaiting T2.SB1 merge per OQ-12 Option E.
- **T-A.1.7 corpus:** 34 rows in `~/swing-data/swing.db` (13 gold / 21 silver across 5 V1 classes) + manifest at `data/phase13-t2-sb1-corpus/README.md` + JSONL dump at `data/phase13-t2-sb1-corpus/pattern_exemplars_dump.jsonl`.

T-A.1.7 SHIPPED with operator-acknowledged deviation: 13/25 gold (52% of target), but all 5 V1 classes have positive exemplars; orchestrator accepted the corpus as sufficient bootstrap material per `feedback_orchestrator_qa_implementer_product.md` post-QA. Five T-A.1.6 web-surface deficiencies + three spec-strictness observations + two reproducibility banks landed in operator's resume signal; T-A.1.8 absorbs the surgical ship-defects (Deficiency 2 + Deficiency 3) and banks the rest forward.

---

## §0.5 Skill posture

- Invoke **`copowers:executing-plans`** (wraps `superpowers:subagent-driven-development` + adversarial Codex review). Iterate to `NO_NEW_CRITICAL_MAJOR`. Expected 2-3 Codex rounds.
- Use **`superpowers:test-driven-development`** per task.
- Pre-Codex orchestrator-side review per **C.C lesson #6 BINDING** before invoking `copowers:adversarial-critic` at each round. This is the **16th cumulative validation** expected (15× precedent CLEAN through T-A.1.5b).

---

## §1 Strategic context

### §1.1 T-A.1.8 scope (per plan §G.1 T-A.1.8 + spec §5.9 step 4 + T-A.1.7 deficiency closure)

T-A.1.8 closes T2.SB1 by shipping the previously-deferred Codex 2nd-reviewer pipeline + cassette-mode E2E test + 2 ship-defect closures + verification gate.

Per **spec §5.9 step 4** + OQ-5 phased rollout: the random-15% Codex 2nd-reviewer (high-stakes disagreement clause activates at T2.SB3+/SB4 retroactively; T2.SB1 ships RANDOM-15% sampling ONLY). The dispatching logic already exists at `swing/patterns/labeling.py` (`should_fire_codex` + `fire_codex_review_for_silver_row` per T-A.1.3 + Codex SIM103 cleanup at `c1ad90f`); T-A.1.8 wires the actual invocation pipeline + the cassette infrastructure for replayable testing.

### §1.2 What T-A.1.7 left for T-A.1.8

From the operator's resume signal:

**Surgical ship-defects to close in T-A.1.8 (IN SCOPE)**:

1. **Deficiency 2 — relabel-promote-to-gold SQL bug** at `swing/web/routes/patterns.py:166-168` (ACTUAL line range; the operator's :163-168 reference is close):
   ```python
   conn.execute(
       "UPDATE pattern_exemplars SET label_source = 'curated_gold', "
       "final_decision = 'confirmed', gold_validated_at = ?, "
       "final_pattern_class = NULL "       # <-- BUG: overwrites relabel
       "WHERE id = ?",
       (now_iso, exemplar_id),
   )
   ```
   When operator clicks "Promote to gold" on a previously-relabeled row (`final_pattern_class` was set to the relabel target via the `relabel:<class>` action), this SQL OVERWRITES the relabel back to NULL. Operator has no path to promote a relabeled row to gold under its corrected class.

   **Fix shape:** preserve existing `final_pattern_class` if non-NULL; otherwise stamp NULL. Two acceptable approaches: (a) read the row's current `final_pattern_class` first + branch the UPDATE; (b) use a CASE expression in the UPDATE to keep current value when non-NULL. Prefer (b) for atomicity.

   **Discriminating tests:**
   - Plant a row with `final_pattern_class='flat_base'` (relabeled from VCP); POST promote-to-gold; assert row's `final_pattern_class` STAYS `flat_base`; `label_source='curated_gold'`.
   - Plant a row with `final_pattern_class=NULL` (unmodified silver); POST promote-to-gold; assert `final_pattern_class` STAYS NULL; `label_source='curated_gold'`.

2. **Deficiency 3 — FlatBaseEvidence schema gap** at `swing/patterns/spec_static.py` lines 524-534 (`flat_base` entry in `_STRUCTURAL_EVIDENCE_SCHEMA_BY_CLASS`):

   ```python
   "flat_base": {
       "pattern_class": "flat_base",
       "spec_section": "section 5.3",
       "evidence_dataclass": "FlatBaseEvidence",
       "fields": {
           "range_top": "float",
           "range_bottom": "float",
           "regression_slope_pct_per_week": "float",
           "mean_atr_pct": "float",
           "duration_days": "int",
           "pivot_price": "float",
           "geometric_score": "float in [0.0, 1.0]",
       },
   },
   ```

   No `base_start_date` / `base_end_date` sub-window fields (VCP has them at lines 498-499). The subagent must compute range over the full fetched window, which fails the flat-base criteria when there's a clean pre-breakout consolidation WITHIN a longer window (operator's TGT 2020-05-01..2020-08-31 corpus row was the only one to clear despite this gap).

   **Fix shape:** add `base_start_date` + `base_end_date` fields to `flat_base` `fields` dict mirroring VCP shape:
   ```python
   "base_start_date": "date (ISO YYYY-MM-DD)",
   "base_end_date": "date (ISO YYYY-MM-DD)",
   ```
   Cross-check spec §5.3 verbatim for any additional fields the spec mentions but the schema omits.

   **Discriminating tests:**
   - Parametrized over flat_base, assert structural_evidence_schema['fields'] contains `base_start_date` + `base_end_date` keys.
   - Audit the other 3 classes (`cup_with_handle` + `high_tight_flag` + `double_bottom_w`) for analogous sub-window gaps; the operator noted cup_with_handle has `cup_left_edge_date`/`cup_right_edge_date` (good) + high_tight_flag should have `flag_start_date`/`flag_end_date` + double_bottom_w has `trough_*_date` (good). Verify each class has sufficient sub-window granularity per spec §5.4-§5.6.

**Banked for T2.SB3+/SB4 detector calibration (NOT T-A.1.8 scope; document in §"Forward-binding lessons" of return report)**:

- **Cup-with-handle rounded-vs-V hard gate** caused 4 of 5 cup dispatches to fail by sub-1% margins. Recommend widening tolerance OR downgrading from hard-reject to scoring penalty in T2.SB3 detector landing.
- **HTF consolidation tightness (pullback ≤25%, width ≤15%)** — real parabolic HTFs (BLNK 583%, NIO 108%, PLTR 84% poles) consistently exceed. Consider widening pullback to 35% / width to 25% for high-magnitude-pole cases.
- **VCP monotonic-tightening hard gate** — real bases sometimes break monotonicity due to news/earnings. Consider 1-violation tolerance for high-confidence other-criteria-pass cases.
- **Precursor 3-dip "early identifier" pattern** — surfaced 2026-05-20 via operator's TSM + TGT + SNAP annotated chart references (the three "Bought Here" charts with red-dashed precursor curves). Minervini's setup-quality framework treats the broader chart context (prior 3-dip stair-step leading INTO the base) as part of setup quality; the per-class V1 detectors only score the BASE itself. **This is the structural explanation for the cup/HTF/DBW operator-visual-override pattern in T-A.1.7**: operator's visual judgment incorporates precursor-structure quality the subagent can't see. Three observed instances: (a) TSM Nov-2019 → Aug-2020 (operator window labels failed across 4 framings because the precursor curve dominated the fetched window when expanded enough to capture it); (b) TGT Dec-2019 → Oct-2020 (3 ascending dips May-Aug 2020 build a clean flat-base at $124 that breaks out + the flat-base scored geometric_score=1.0 because the labeling window was tight to the base, NOT inclusive of the precursor); (c) SNAP Jan-2020 → Oct-2020 (3 dips Jul-Sep 2020 leading into the operator's promoted exemplar). Two design surfaces this opens for T2.SB3+/SB4 + V2: (1) **labeling-window-vs-setup-quality separation** — the labeling window for shape identification should be SCOPED TIGHT to the base; including the precursor structure dilutes shape identification. Detector dispatches should articulate this contract explicitly. (2) **NEW V2 detector surface: "precursor 3-dip identifier"** — a separate algorithmic detector that scores the broader uptrend + dip-stair-step quality preceding a base. Would let the system flag candidates earlier (pre-base-formation) + score setup quality via composite (precursor + base) signal + close the operator-visual-override gap. Banking as V2 candidate; T2.SB3+/SB4 designers SHOULD include the "labeling window scoped to base only" contract in their per-detector specs to prevent future operator-paired labeling sessions from hitting the TSM-4-framing exhaustion.

**Banked for T-A.1.8 cassette-mode test OR forward-binding lessons**:

- **SNAP reproducibility variance** — same window dispatched twice yielded different swing-detection (T3 9.10% vs 4.10%) and opposite labels (rejected vs watch). Plant a cassette-mode discriminating test asserting `should_fire_codex` flags disagreement-eligible silvers on opposite-evaluation re-dispatches (the subagent's non-determinism here SHOULD trigger Codex 2nd-reviewer per spec §5.9 step 4 selective policy). If the cassette test cannot capture this naturally, bank as forward-binding lesson.

**Deferred to separate web-refinement task (NOT T-A.1.8 scope; capture as outstanding item)**:

- **Deficiency 1 — T-A.1.6 template rendering gaps** (no chart, no per-criterion table, no narrative display at `swing/web/templates/patterns/exemplars.html.j2`). Significant scope (~150-300 LOC across mplfinance/SVG chart rendering + structural_evidence per-criterion table + narrative rendering); pushes T2.SB1 past envelope; doesn't block T2.SB1 ship (corpus is committed; T2.SB3 detectors don't need the web UI to consume the JSONL dump); operator has external workaround. Bank as standalone post-T2.SB1-merge follow-up dispatch OR fold into T2.SB6 closed-loop surface.
- **TSM 4-framing exhausted** — operator anecdote (4 framings of TSM all rejected). Bank as forward-binding lesson: some real chart history doesn't fit a clean V1 class; informs V2 detector enrichment (additional classes or wider criteria envelopes).

### §1.3 Per-task structure

- **T-1.8.1** — Random-15% Codex 2nd-reviewer dispatch wiring (CLI subcommand or test-fixture invocation per spec §5.9 step 4; consumes existing `should_fire_codex` + `fire_codex_review_for_silver_row` plumbing from `swing/patterns/labeling.py`).
- **T-1.8.2** — Cassette-mode E2E test (silver → 15% Codex sample → disagreement → codex_silver row insertion). Uses the cassette infrastructure shipped at T-A.1.4 + recording scripts at `scripts/record_codex_mcp_pattern_review_cassettes.py`.
- **T-1.8.3** — Deficiency 2 fix (relabel-promote-to-gold SQL bug) + 2 discriminating tests per §1.2.
- **T-1.8.4** — Deficiency 3 fix (FlatBaseEvidence schema gap + audit-pass on other 3 non-VCP classes) + parametrized discriminating tests.
- **T-1.8.5** — Closer (ruff sweep + full-suite verification; final return report at `docs/phase13-t2-sb1-return-report.md` SUPERSEDING the interim at `3c925a2`).

Each task ends with a commit per the per-task message below. Iterate Codex rounds after T-1.8.5 ships; do NOT begin Codex until all 5 tasks land.

### §1.4 Cross-bundle pin schedule status (per plan §H.3)

- `test_schema_version_v20_invariant` — un-skipped at T3.SB1 worktree HEAD; will activate on main at T3.SB1 merge.
- `test_pattern_exemplars_schema_shape_invariant` — un-skips at T2.SB3 + T2.SB5 (UNCHANGED by T-A.1.8).
- `test_v20_atomic_landing_python_constants_validators_paired` — un-skips at T4.SB closer (UNCHANGED).
- `test_fill_origin_enum_complete_after_v20` — un-skips at T3.SB2 (UNCHANGED).
- `test_flag_classifier_integration.py:21` (currently skipped: "No labeled fixtures committed yet (Task 7.3 operator-only)") — **T-A.1.8 should evaluate** whether the T-A.1.7 corpus at `data/phase13-t2-sb1-corpus/` qualifies as the labeled fixtures referenced; if yes, un-skip it. If no (e.g., the test expected a different fixture shape), document why + leave skipped + bank as forward-binding for later resolution.

### §1.5 Inherited LOCKs (preserved through T-A.1.8)

- **L1**: No run-time AI inferencing. Codex 2nd-reviewer is DEV-TIME ONLY.
- **L9**: Codex SELECTIVE policy phased per OQ-5 — T2.SB1 implements **random 15% only** (high-stakes disagreement clause activates at T2.SB3+/SB4 retroactively).
- **§A.14 LOCK**: ALL v20 enum constants in `swing/data/models.py`; later modules IMPORT not REDEFINE.
- **§A.15 LOCK**: NO `INSERT OR REPLACE` on the 5 audit-trail tables.
- **§B.6 escalation rule**: NO new schema beyond plan §G.1 + spec §3. Schema v20 UNCHANGED.
- **Pre-Codex orchestrator-side review BINDING** per C.C lesson #6 (16th cumulative validation expected).

### §1.6 Forward-binding lessons inherited (load-bearing for T-A.1.8)

1. **Synthetic-fixture-vs-production-emitter shape drift** (THREE recent instances + counting). T-A.1.8 cassette test fixtures MUST mirror PRODUCTION emitter shape (the actual Codex MCP response shape; the actual `should_fire_codex` invocation flow). Do NOT hand-craft cassettes that diverge from real subagent/Codex output.
2. **`Literal[...]` not runtime-enforced** (T-A.1.5b R3 M#1). Any new dataclass with Literal field on data-integrity path adds `__post_init__` runtime validation.
3. **Service-layer ValueErrors must be wrapped at CLI boundary** (T-A.1.5b R4 M#1). Any new CLI surface around the Codex 2nd-reviewer dispatch wraps service-layer dispatch in `try: ... except ValueError as exc: raise click.ClickException(...)`.
4. **Dict-shape-mismatch-at-sqlite3-bind defense-in-depth** (T-A.1.5b R1 M#3 + M#4). Cassette-mode test fixtures should exercise the dataclass `__post_init__` coercion path.
5. **Cassette URI/path + body sanitization** (post-Phase-12 forward-binding lesson #2) — `before_record_request` + `before_record_response` filters at `tests/integrations/_cassette_sanitization` cover Codex MCP cassettes too.
6. **Phase 13 T1.SB0 hook fallback window-completeness** + **session-anchor inequality discipline** — preserved through T-A.1.5b; T-A.1.8 inherits.

---

## §2 Per-task structure (with commit messages)

### T-1.8.1 — Random-15% Codex 2nd-reviewer dispatch wiring

Per spec §5.9 step 4: silver-tier rows have a 15% chance of triggering a Codex 2nd-review pass. The plumbing exists at `swing/patterns/labeling.py:should_fire_codex` (T-A.1.3) + `fire_codex_review_for_silver_row` (T-A.1.3). T-1.8.1 wires the invocation pipeline so the random-15% sample actually fires:

1. Identify the firing surface — likely a CLI subcommand `swing patterns review-silver-with-codex` (or fold into existing `label-exemplars` post-persist trigger; implementer chooses cleanest shape per spec §5.9 step 4 semantics).
2. Read existing `should_fire_codex` policy implementation; verify random-15% sampling correctness; confirm phased rollout policy LOCK preserved (NOT high-stakes disagreement clause; that's T2.SB3+/SB4).
3. Wire Codex MCP invocation via existing project Codex infrastructure (`mcp__plugin_copowers_codex__codex` etc).
4. Persist Codex review response per spec §5.9 (likely a NEW row in `pattern_exemplars` with `label_source='codex_silver'` + `parent_exemplar_id=<silver_row_id>` for the disagreement chain).

**Per-task acceptance criteria:**
- New CLI subcommand (or wired persist-time trigger) exercising `should_fire_codex` + `fire_codex_review_for_silver_row` end-to-end.
- Random-15% sampling correctness verified via discriminating test (large-N sample assertion; e.g., over 1000 mocked invocations, 12-18% fire rate).
- ZERO Codex high-stakes disagreement clause activation (LOCK; T2.SB3+/SB4 territory).
- Caller-tx contract preserved at any repo-level inserts.
- ASCII-only on CLI output.

**Commit message:**
```
feat(phase13): T-A.1.8 - random-15% Codex 2nd-reviewer dispatch wiring (spec section 5.9 step 4)
```

### T-1.8.2 — Cassette-mode E2E test

Per spec §5.9 step 4 + brief original T-A.1.8 closer scope:

1. Wire a cassette-mode E2E test that exercises: silver row insertion → `should_fire_codex` returns True (forced via test seed) → `fire_codex_review_for_silver_row` invocation → Codex MCP response captured in cassette → `codex_silver` row insertion → disagreement-chain `parent_exemplar_id` linkage verified.
2. Cassette location: `tests/integrations/cassettes/codex_mcp_pattern_review/` (already scaffolded at T-A.1.4).
3. Sanitization: `before_record_request` URI/header filtering + `before_record_response` body sanitization per T-A.1.4 + post-Phase-12 forward-binding lesson #2.
4. Sentinel-leak audit: `python scripts/record_codex_mcp_pattern_review_cassettes.py --audit-sentinels` passes (no PII / secrets in cassette content).
5. **Plant a discriminating test for SNAP-reproducibility-variance pattern**: simulate two opposite-evaluation re-dispatches of the same window; assert `should_fire_codex` flags BOTH; assert `codex_silver` rows are independently persisted with `parent_exemplar_id` linkage.

**Per-task acceptance criteria:**
- 1 slow E2E test marked `@pytest.mark.slow` (per CLAUDE.md slow-test marking convention).
- Cassette content sanitized + sentinel-leak audit passes.
- Disagreement-chain `parent_exemplar_id` linkage end-to-end verified.
- SNAP-reproducibility-variance discriminating test passes.

**Commit message:**
```
test(phase13): T-A.1.8 - cassette-mode E2E silver to Codex disagreement to codex_silver row insertion
```

### T-1.8.3 — Deficiency 2 fix (relabel-promote-to-gold SQL bug)

Per §1.2 Deficiency 2:

1. Fix `swing/web/routes/patterns.py:166-168` UPDATE statement to PRESERVE existing `final_pattern_class` when non-NULL.
2. Two discriminating tests per §1.2 (relabel-then-promote preserves class; unmodified-silver-then-promote stamps NULL).
3. Cross-audit other action handlers (`reject` / `relabel`) for analogous `final_pattern_class` overwrite bugs.

**Per-task acceptance criteria:**
- SQL fix uses CASE expression OR explicit branch; preserves relabel through promote-to-gold.
- 2 discriminating tests pass; pre-fix verified FAIL via temporary revert.
- No analogous bug in `reject` or `relabel` handlers.

**Commit message:**
```
fix(phase13): T-A.1.8 - relabel-then-promote-to-gold preserves final_pattern_class (Deficiency 2)
```

### T-1.8.4 — Deficiency 3 fix (FlatBaseEvidence schema gap + audit pass on non-VCP classes)

Per §1.2 Deficiency 3:

1. Add `base_start_date` + `base_end_date` fields to `flat_base` entry at `swing/patterns/spec_static.py:_STRUCTURAL_EVIDENCE_SCHEMA_BY_CLASS[flat_base][fields]`.
2. Audit `cup_with_handle` + `high_tight_flag` + `double_bottom_w` schemas for analogous sub-window gaps per spec §5.4-§5.6 verbatim. Operator's resume notes:
   - `cup_with_handle` has `cup_left_edge_date` / `cup_right_edge_date` ✓
   - `high_tight_flag` should have `flag_start_date` / `flag_end_date` (verify)
   - `double_bottom_w` has `trough_*_date` ✓
3. Parametrized discriminating test asserting per-class structural_evidence_schema contains required sub-window fields.
4. Per-class anchor tests pin spec section citation + field-list verbatim match.

**Per-task acceptance criteria:**
- `flat_base` schema gains `base_start_date` + `base_end_date`.
- `high_tight_flag` schema audited + missing sub-window fields added if any.
- Parametrized tests assert sub-window granularity per class.
- §A.14 LOCK preserved (no constants moved; only schema field additions).

**Commit message:**
```
fix(phase13): T-A.1.8 - flat_base + high_tight_flag structural_evidence_schema sub-window fields (Deficiency 3)
```

### T-1.8.5 — Closer (ruff + full-suite + final return report)

1. Full-suite pytest verification (expect 5068 baseline + N tests added across T-1.8.1..T-1.8.4 + 1 slow E2E test).
2. Ruff sweep: 0 errors on `swing/`.
3. Cross-bundle pin disposition: evaluate `test_flag_classifier_integration.py:21` against the T-A.1.7 corpus; un-skip if the corpus qualifies as the labeled-fixtures dependency; else document.
4. Final return report at `docs/phase13-t2-sb1-return-report.md` (SUPERSEDES interim at `3c925a2`; cites full commit chain from T-A.1.1 through T-A.1.8 closer; banks all forward-binding lessons from T-A.1.7 + T-A.1.5b + T-A.1.8 for orchestrator post-merge housekeeping).

**Per-task acceptance criteria:**
- pytest fast suite passes; expected delta ~+10-30 from T-A.1.7 baseline (5068 → ~5080-5100).
- ruff 0 errors.
- Final return report at the canonical path with full chain enumeration + cross-bundle pin update.

**Commit message:**
```
test(phase13): T-A.1.8 closer - full-suite verification + ruff sweep + final return report
```

---

## §3 Inherited LOCKS + DROPS (preserved through T-A.1.8)

- **Schema v20 UNCHANGED** — closer is application-layer only.
- **Subagent definition `.claude/agents/pattern-labeler.md` UNCHANGED**.
- **Web routes (T-A.1.6 surface) — T-A.1.8 surgical fix at swing/web/routes/patterns.py:166-168 ONLY** (Deficiency 2). DO NOT refactor the template rendering (Deficiency 1 is DEFERRED).
- **Repo modules (T-A.1.1b) UNCHANGED**.
- **CLI surface (T-A.1.5 + T-A.1.5b)** — extended for Codex 2nd-reviewer wiring if a new subcommand is the chosen shape; otherwise UNCHANGED.
- **Cassette infrastructure (T-A.1.4) UNCHANGED** — T-A.1.8 USES it, doesn't modify.
- **§A.14 LOCK preserved** — no constants move.
- **§A.15 LOCK preserved** — no INSERT OR REPLACE.
- **§B.6 escalation rule** — NO new schema beyond plan §G.1 + spec §3.
- **L1 LOCK preserved** — Codex 2nd-reviewer is DEV-TIME ONLY.
- **L9 LOCK preserved** — random-15% phase ONLY (no high-stakes disagreement clause).
- **Plan §H.3 cross-bundle pin schedule** — UNCHANGED by T-A.1.8 except possible un-skip of `test_flag_classifier_integration.py:21` per §1.4.

---

## §4 Adversarial review watch items

1. **T-1.8.1 random-15% sampling correctness** — large-N test verifies firing rate in 12-18% band; sample selection is genuinely random + seed-pinned for test determinism.
2. **T-1.8.1 phased-rollout LOCK preserved** — random-15% ONLY; no high-stakes disagreement clause activation (LOCK for T2.SB1 phase per OQ-5).
3. **T-1.8.1 caller-tx contract** — repo-level inserts honor caller-tx discipline (BEGIN IMMEDIATE / COMMIT / ROLLBACK owned by service layer per Phase 12 C.C lesson #2).
4. **T-1.8.2 cassette content sanitization** — `before_record_request` + `before_record_response` filters fire; sentinel-leak audit passes; ZERO PII / secrets in committed cassette content.
5. **T-1.8.2 disagreement-chain `parent_exemplar_id` linkage** — `codex_silver` row INSERT references the originating silver row's id; FK constraint honored.
6. **T-1.8.2 SNAP-reproducibility-variance discriminating test** — reflects operator's observed non-determinism; asserts `should_fire_codex` flags opposite-evaluation re-dispatches.
7. **T-1.8.3 SQL fix uses atomic UPDATE** — CASE expression preferred over SELECT-then-UPDATE (latter has TOCTOU window).
8. **T-1.8.3 cross-handler audit** — `reject` + `relabel` handlers checked for analogous `final_pattern_class` overwrite bugs.
9. **T-1.8.4 spec verbatim cross-check** — `base_start_date` + `base_end_date` field naming matches VCP schema convention; high_tight_flag audit catches any additional sub-window gaps.
10. **T-1.8.4 §A.14 LOCK preserved** — only schema dict additions; no constants moved.
11. **T-1.8.5 cross-bundle pin disposition** — `test_flag_classifier_integration.py:21` evaluated against T-A.1.7 corpus; decision documented either way.
12. **Final return report SUPERSEDES the interim** — interim at `3c925a2` stays as historical record; final report cites it as predecessor + enumerates full commit chain.
13. **ZERO Co-Authored-By footer trailer drift** preserved.
14. **ASCII-only on all new CLI output paths** preserved.
15. **Spec-strictness observations banked as forward-binding lessons** in return report (cup rounded-vs-V; HTF tightness; VCP monotonic-tightening) for T2.SB3+/SB4 detector calibration.
16. **Deficiency 1 (template rendering) documented as DEFERRED** with explicit rationale (significant scope; doesn't block ship; operator has external workaround).
17. **TSM 4-framing exhausted observation** banked as forward-binding for V2 detector enrichment.
18. **Pre-Codex orchestrator-side review at every Codex round (C.C lesson #6 BINDING)** — 16th cumulative validation expected.
19. **Implementer self-report accuracy gate** — return report cites file:line + test counts pre/post + commit SHAs verbatim.

---

## §5 Done criteria

1. Branch `phase13-t2-sb1-dev-time-labeling-infra`; 5 task-commits (T-1.8.1 through T-1.8.5) + optional Codex-fix bundles + 1 final return report commit.
2. 5 tasks T-1.8.1..T-1.8.5 executed per §2 verbatim.
3. ≥2 Codex rounds → NO_NEW_CRITICAL_MAJOR (2-3 rounds expected).
4. Random-15% Codex 2nd-reviewer pipeline wired + statistically verified.
5. Cassette-mode E2E test exercises silver → Codex disagreement → codex_silver row insertion.
6. Deficiency 2 SQL fix preserves relabel through promote-to-gold; 2 discriminating tests pass.
7. Deficiency 3 schema additions land for flat_base + high_tight_flag audit pass; parametrized discriminating tests pass.
8. Cross-bundle pin `test_flag_classifier_integration.py:21` evaluated + disposition documented.
9. Baseline 5068 → ~5080-5100 fast (delta projection +10-30).
10. Ruff 0 E501 on `swing/`.
11. Schema v20 UNCHANGED.
12. Final return report at `docs/phase13-t2-sb1-return-report.md` per §6 (SUPERSEDES interim `3c925a2`).
13. Forward-binding lessons banked: cup rounded-vs-V calibration + HTF tightness + VCP monotonic + SNAP reproducibility + TSM 4-framing.
14. Deficiency 1 (template rendering) documented as DEFERRED with rationale.
15. ZERO Co-Authored-By footer trailer drift across all commits.

---

## §6 Return report format

```
## Return report — Phase 13 T2.SB1 (FINAL)

### Sub-bundle location
Worktree branch: `phase13-t2-sb1-dev-time-labeling-infra` at `.worktrees/phase13-t2-sb1-dev-time-labeling-infra/`

### Full commit chain (T-A.1.1 through T-A.1.8)
[enumerate all task-commits + Codex-fix bundles + interim/T-A.1.5b/T-A.1.7/T-A.1.8 return reports]
- {SHA} T-A.1.1 (4cfd5f2 — branch base for T3.SB1 per OQ-12 Option E)
- {SHA} T-A.1.1b
- ... (through T-A.1.8 closer + final return)

### Codex review history
- Pre-Codex (C.C lesson #6 BINDING; 16th cumulative validation): CLEAN
- R1..RN: ... (2-3 rounds expected)
- Final verdict: NO_NEW_CRITICAL_MAJOR

### T-A.1.7 corpus disposition
- 13 gold / 21 silver across 5 V1 classes; committed at bd0775f
- Manifest at data/phase13-t2-sb1-corpus/README.md
- JSONL dump at data/phase13-t2-sb1-corpus/pattern_exemplars_dump.jsonl (34 rows)

### Defect closure verification (T-A.1.8-scoped)
- Deficiency 2 (relabel-promote SQL): {file:line of fix}; pre-fix revert verification confirmed.
- Deficiency 3 (FlatBaseEvidence + HTF audit): {file:line of schema additions}; per-class parametrized tests pass.

### Cross-bundle pin disposition
- test_flag_classifier_integration.py:21 — {UN-SKIPPED / STAYS-SKIPPED with rationale}.

### Test count pre/post (T2.SB1 full delta)
- Pre-baseline (main HEAD 6383cfa): 4939 fast
- Post-T2.SB1 closer: {fast count} (cumulative delta: +{N}; T-A.1.1=+10; T-A.1.1b through T-A.1.6=+64; T-A.1.5b=+55; T-A.1.8=+{M})

### Operator-witnessed gate results
- S1 (inline pytest+ruff): PASS via implementer
- S2 ({CLI surface check or production-readiness check}): {PASS/FAIL post-merge}
- S3 (T-A.1.7 operator-paired exemplar bootstrap): PASS at bd0775f (with documented deviation: 13/25 gold)

### Forward-binding lessons banked
1. Synthetic-fixture-vs-production-emitter shape drift (THIRD instance in 3 days) — banks defense-in-depth pattern for CLAUDE.md.
2. Literal[...] not runtime-enforced — dataclass __post_init__ validation pattern.
3. Service-layer ValueErrors must be wrapped at CLI boundary — try/except → click.ClickException pattern.
4. Cup-with-handle rounded-vs-V hard gate — T2.SB3 detector should widen or downgrade to scoring penalty.
5. HTF consolidation tightness — widen pullback/width caps for high-magnitude-pole cases.
6. VCP monotonic-tightening — 1-violation tolerance for high-confidence other-criteria-pass cases.
7. SNAP reproducibility variance — non-determinism observed; Codex 2nd-reviewer should catch (cassette test plants the pattern).
8. TSM 4-framing exhausted — some real chart history doesn't fit V1 class set; informs V2 enrichment.
9. Random-15% Codex policy phased rollout — T2.SB1 ships RANDOM-15% only; high-stakes disagreement clause for T2.SB3+/SB4.

### Outstanding capture-needs that DEFER
- Deficiency 1 (T-A.1.6 template rendering: chart + per-criterion table + narrative): DEFERRED to separate web-refinement task OR T2.SB6 closed-loop surface fold-in.
- V2 hardening from T-A.1.5b R1 Minor #1 (sort_keys byte-original preservation): banked.
- Schwab cassette runbook for pattern-labeler: V2 planned.
- Weekly timeframe auto-fetch: V2 candidate.

### CLAUDE.md gotcha candidates for post-merge housekeeping
- Synthetic-fixture-vs-production-emitter shape drift family (REINFORCE existing gotcha with two-pronged defense-in-depth pattern).
- Schema-version-aware INSERT pattern (T3.SB1 surfaced).
- Hidden anchor 4-tier rejection ladder (T3.SB1 surfaced).
- Recovery form anchor-clear discipline (T3.SB1 surfaced).
- Literal[...] runtime validation (T-A.1.5b surfaced).
- Service-layer ValueError → CLI ClickException pattern (T-A.1.5b surfaced).
```

---

## §7 If you get stuck

- If `should_fire_codex` random-15% policy implementation is unclear, STOP + escalate. Do NOT introduce a NEW policy; the existing plumbing at `swing/patterns/labeling.py` is authoritative.
- If Codex MCP invocation requires schema beyond what's in `~/swing-data/swing.db` v20, STOP — §B.6 escalation rule.
- If the cassette test reveals a sanitization gap (PII / secret leaks past `before_record_request` or `before_record_response` filters), STOP + fix the filter; the cassette content is a discriminating audit surface.
- If the Deficiency 2 fix breaks existing `reject` or `relabel` action tests, STOP — backward-compat is BINDING.
- If the Deficiency 3 audit reveals additional sub-window gaps in `high_tight_flag` or `double_bottom_w` beyond what the operator noted, address them in T-1.8.4 atomic with the flat_base fix.
- If `test_flag_classifier_integration.py:21` requires a fixture shape that the T-A.1.7 corpus doesn't match, STOP + escalate (do NOT mutate the corpus to fit the test).
- If you find yourself adding to the T-A.1.6 template (Deficiency 1), STOP — that's out of scope; bank as DEFERRED.
- If Codex review surfaces a SCHEMA need beyond v20, STOP — §B.6 escalation rule.
- If you find yourself proposing run-time AI inferencing, STOP — L1 LOCK violated.

---

## §8 References

- **T-A.1.7 corpus manifest**: `data/phase13-t2-sb1-corpus/README.md`
- **T-A.1.7 corpus JSONL dump**: `data/phase13-t2-sb1-corpus/pattern_exemplars_dump.jsonl` (34 rows)
- **T-A.1.7 labeling briefing**: `docs/phase13-t2-sb1-t-a-1-7-labeling-briefing.md` (post-T-A.1.5b refresh)
- **T-A.1.5b hotfix dispatch brief**: `docs/phase13-t2-sb1-t-a-1-5b-hotfix-dispatch-brief.md`
- **T-A.1.5b return report**: `docs/phase13-t2-sb1-t-a-1-5b-return-report.md`
- **Interim return report (post-T-A.1.1)**: `docs/phase13-t2-sb1-interim-return-report.md`
- **Original T2.SB1 dispatch brief**: `docs/phase13-t2-sb1-executing-plans-dispatch-brief.md`
- **Plan §G.1 (T2.SB1 task contracts)**: `docs/superpowers/plans/2026-05-18-phase13-charts-patterns-autofill-usability-plan.md` lines 1044-1343
- **Spec §5.9 (operator-paired exemplar bootstrap + Codex 2nd-reviewer)**: `docs/superpowers/specs/2026-05-18-phase13-charts-patterns-autofill-usability-design.md`
- **Existing Codex 2nd-reviewer plumbing**: `swing/patterns/labeling.py` (`should_fire_codex` + `fire_codex_review_for_silver_row`)
- **Cassette infrastructure**: `tests/integrations/_cassette_sanitization.py` + `scripts/record_codex_mcp_pattern_review_cassettes.py`

---

*End of brief. Phase 13 T2.SB1 T-A.1.8 closer dispatch — 5 tasks closing the sub-bundle. Branch `phase13-t2-sb1-dev-time-labeling-infra` HEAD `bd0775f`. Expected 2-3 Codex rounds. Pre-Codex orchestrator-side review BINDING per C.C lesson #6 (16th cumulative validation). After T-A.1.8 ships + orchestrator QA + Codex closure, T2.SB1 merges to main FIRST (per OQ-12 Option E), then T3.SB1 merges SECOND. Post-merge housekeeping commit absorbs all banked CLAUDE.md gotcha candidates from T3.SB1 + T-A.1.5b + T-A.1.8 + size-check trigger evaluation.*
