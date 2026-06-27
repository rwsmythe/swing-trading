# Orchestrator handoff — 2026-05-20 (post-T2.SB1-T-A.1.8 SHIPPED + T3.SB1 SHIPPED + pre-merge)

You are taking over as orchestrator for the Swing Trading project at the **post-T-A.1.8 + post-T3.SB1 + pre-merge** breakpoint. Both bundles are SHIPPED-validated on their respective worktrees; main HEAD has not yet advanced past the previous T1.SB0 gate-fix housekeeping. Outgoing orchestrator handed off due to context-window pressure ahead of the substantial post-merge housekeeping work (~5+ NEW CLAUDE.md gotchas + Prior state archive-split + V2 candidates banking + S2/S3 gate driving).

**main HEAD AT HANDOFF**: `6383cfa` (T1.SB0 gate-fix housekeeping; UNCHANGED since 2026-05-19 morning).

**WORKING DIRECTORY**: `c:\Users\rwsmy\swing-trading`

**CRITICAL FIRST TASK**: Execute the T2.SB1 → T3.SB1 merge sequence per OQ-12 Option E, then the post-merge housekeeping commit (see §2 of this brief).

---

## §0 Critical bootstrap framing

**Memory entries inherited (all BINDING; load-bearing across recent handoffs)**:
- `feedback_pause_means_pause.md` — when operator says pause, STOP all forward motion immediately.
- `feedback_worktree_cli_invocation.md` — `python -m swing.cli` from worktree cwd, NOT bare `swing`.
- `feedback_time_estimates_overstated.md` — orchestrator wall-clock estimates 3-5x too long; divide by 3-5x for operator-paced.
- `feedback_orchestrator_qa_implementer_product.md` — orchestrator MUST QA every implementer product before merge; verify against reality on disk; don't merely summarize self-report. **BINDING** (validated 14x+ cumulatively across Phase 12/12.5/13 arcs through T-A.1.8).
- `feedback_orchestrator_performs_merge.md` — merge + push + post-merge housekeeping = orchestrator action; do NOT ask "shall I merge".
- `feedback_orchestrator_vs_implementer_execution.md` — default to implementer-dispatch for context budget; orchestrator-inline only for orchestration work (housekeeping is orchestrator-inline).
- `feedback_always_provide_inline_dispatch_prompt.md` — every brief gets an inline dispatch prompt as fenced code block.
- `feedback_commit_brief_before_inline_prompt.md` — commit the brief BEFORE providing inline prompt.
- `feedback_regression_test_arithmetic.md` — when specifying tests in orchestrator briefs, compute values under both pre-fix and post-fix paths to confirm the test distinguishes.

**Operator dispatches implementers themselves** (durable). Orchestrator drafts brief + provides inline dispatch prompt as fenced code block.

**NO Claude co-author footer.** Cumulative streak **~239+ commits ZERO trailer drift** through T-A.1.8 + T3.SB1 + T-A.1.5b + T-A.1.7 corpus + all predecessors. Pattern is DURABLE. DO NOT regress. Explicit citation in commit messages required:

> Per fresh forward-binding lesson #7 (Phase 12 Sub-sub-bundle C.B 2026-05-15): do NOT add `Co-Authored-By: Claude Opus 4.7 (1M context) <noreply@anthropic.com>` (or any other Co-Authored-By footer attributing the AI assistant) to ANY commit message.

**Pre-Codex orchestrator-side review (C.C lesson #6) — BINDING. 16x cumulative CLEAN through T-A.1.8.** 17th+ validations expected at downstream dispatches (T2.SB2 + Phase-9 TZ-drift followup if dispatched + T2.SB3 + T2.SB4 + ...).

**Size-check trigger discipline** at `docs/orchestrator-context.md` §"Maintenance: retention discipline" §"Size-check trigger at housekeeping-commit time". Soft thresholds:
- CLAUDE.md line 3: >2,000 chars → trim back.
- orchestrator-context.md "Prior state" sub-sections: >10 retained → archive oldest.
- orchestrator-context.md "Lessons captured": >40 entries → migrate oldest 5-10.
- phase3e-todo.md SHIPPED entries: >25 retained → archive-split.

**CRITICAL pre-flight for post-merge housekeeping**: Prior state count is currently 10 (at cap). Demoting CURRENT state for T2.SB1+T3.SB1 merge will push to 11+ → **archive-split trigger fires**. Plan archive of 1-2 oldest Prior states.

---

## §1 Read these in order

1. **This brief end-to-end** — captures T-A.1.8 SHIPPED outcome + T3.SB1 SHIPPED context + merge sequence + post-merge housekeeping deliverables + 9 CLAUDE.md gotcha candidates verbatim-ready.

2. **`.worktrees/phase13-t2-sb1-dev-time-labeling-infra/docs/phase13-t2-sb1-return-report.md`** (190 lines; FINAL T2.SB1 return report at worktree HEAD `9904e8a`) — Codex chain summary + 9 forward-binding lessons + 9 CLAUDE.md gotcha candidates + cross-bundle pin disposition + 2 PRE-EXISTING TZ-drift failure analysis.

3. **`.worktrees/phase13-t3-sb1-entry-auto-fill/docs/phase13-t3-sb1-return-report.md`** (T3.SB1 final return report on sibling worktree at HEAD `a73bab6`) — Codex chain + 4 ACCEPT-WITH-RATIONALE banks (all TECHNICALLY SOUND per prior QA) + 3 NEW CLAUDE.md gotcha candidates.

4. **`.worktrees/phase13-t2-sb1-dev-time-labeling-infra/data/phase13-t2-sb1-corpus/README.md`** (T-A.1.7 corpus manifest; 13 gold / 21 silver across 5 V1 classes; operator-acknowledged 13/25 deviation accepted).

5. **`docs/phase3e-todo.md`** top entries — current SHIPPED ledger; will need NEW SHIPPED entries for T2.SB1 + T3.SB1 in YOUR housekeeping commit.

6. **`docs/orchestrator-context.md`** sections "Currently in-flight work" + "Lessons captured" + "Maintenance: retention discipline" (especially "Size-check trigger at housekeeping-commit time"; Prior state archive-split will fire this commit).

7. **`CLAUDE.md`** — project conventions + gotchas. Current state line 3 reflects HEAD `d772f23` (T1.SB0 gate-fix); will need refresh to capture T2.SB1 + T3.SB1 + housekeeping merge SHAs in YOUR commit.

8. **Plan §H.1 dispatch sequence** at `docs/superpowers/plans/2026-05-18-phase13-charts-patterns-autofill-usability-plan.md` — next sub-bundle after T2.SB1+T3.SB1 ship is T2.SB2 (foundation primitives).

---

## §2 ⚠ CRITICAL FIRST TASKS — Merge sequence + housekeeping commit

### §2.1 Merge sequence (per OQ-12 Option E)

**T2.SB1 MERGES FIRST; T3.SB1 MERGES SECOND.** T3.SB1's branch base is `4cfd5f2` (T2.SB1's T-A.1.1 first-commit SHA); merging T3.SB1 BEFORE T2.SB1 would require additional reconciliation.

#### A. T2.SB1 merge

```bash
# From project root /c/Users/rwsmy/swing-trading
git checkout main
git status  # expect clean
git merge --no-ff phase13-t2-sb1-dev-time-labeling-infra \
    -m "Merge phase13-t2-sb1-dev-time-labeling-infra into main: Phase 13 T2.SB1 SHIPPED — dev-time labeling infrastructure + v20 migration + Codex 2nd-reviewer + T-A.1.7 operator-paired corpus (13 gold / 21 silver across 5 V1 classes) + 3 Codex rounds NO_NEW_CRITICAL_MAJOR at R2 + R3 CLEAN + 16th cumulative C.C lesson #6 BANKED + ZERO Co-Authored-By footer drift"
git log -1 --pretty='%H %s'  # capture merge SHA
git log -1 --pretty='%(trailers:key=Co-Authored-By)'  # verify empty
```

**NO Co-Authored-By footer on the merge commit.** Per cumulative discipline.

Run bootstrap verification post-merge:
```bash
python -m pytest -m "not slow" -q -n auto | tail -5
# Expect: 5092 passed, 2 failed (PRE-EXISTING TZ-drift; NOT introduced by T2.SB1), 6 skipped
ruff check swing/ --statistics | tail -3
# Expect: All checks passed!
python -c "from swing.data.db import EXPECTED_SCHEMA_VERSION; print(EXPECTED_SCHEMA_VERSION)"
# Expect: 20  (v19 → v20 transition via T-A.1.1)
```

**Then push T2.SB1 merge to remote**:
```bash
git push origin main
```

#### B. T3.SB1 merge

```bash
# Still on main; T3.SB1's branch base (4cfd5f2) is now ancestor of main via T2.SB1 merge
git status  # expect clean
git merge --no-ff phase13-t3-sb1-entry-auto-fill \
    -m "Merge phase13-t3-sb1-entry-auto-fill into main: Phase 13 T3.SB1 SHIPPED — entry auto-fill via Schwab Trader API at trade-entry form-render time + fill_origin enum transitions + hidden audit anchors + 5 Codex rounds NO_NEW_CRITICAL_MAJOR at R5 + 4 TECHNICALLY SOUND ACCEPT-WITH-RATIONALE banks + 14th cumulative C.C lesson #6 BANKED + 3 NEW CLAUDE.md gotcha candidates + ZERO Co-Authored-By footer drift"
git log -1 --pretty='%H %s'
git log -1 --pretty='%(trailers:key=Co-Authored-By)'  # verify empty
```

Run bootstrap verification post-T3.SB1-merge:
```bash
python -m pytest -m "not slow" -q -n auto | tail -5
# Expect: ~5158 passed (5092 + ~66 from T3.SB1's +67 with cross-bundle pin un-skip), 2 failed (TZ-drift), 5 skipped (test_schema_version_v20_invariant un-skipped per plan §H.3 row 2)
ruff check swing/ --statistics | tail -3
# Expect: All checks passed!
```

**Then push T3.SB1 merge**:
```bash
git push origin main
```

### §2.2 Combined post-merge housekeeping commit

This is the largest single artifact in your handoff scope. Touches 4-5 files; substantial content; size-check trigger fires for Prior state archive-split.

#### A. CLAUDE.md updates

**Line 3 refresh** (size-checked under 2,000 chars):
- Update HEAD reference from `d772f23` (current) to post-T3.SB1-merge HEAD (~`<new SHA after T3.SB1 merge>`).
- Mention T2.SB1 + T3.SB1 SHIPPED.
- Mention 9 new gotchas added in this housekeeping.
- Mention T2.SB2 next per plan §H.1.

**CLAUDE.md gotchas section: ADD 9 new entries** (verbatim text below; insertion point at end of existing gotcha list, after the "Byte-parity test as algorithmic substitute" gotcha that landed at `6383cfa`).

##### Gotcha #1 — Synthetic-fixture-vs-production-emitter shape drift (FOURTH instance; REINFORCE existing entry)

The existing gotcha at `6383cfa` documents the third instance via T1.SB0 gate-fix byte-parity insufficiency. T-A.1.5b (third) and T-A.1.8 (fourth) reinforce the pattern. Append to the existing entry OR add a new entry citing the cumulative pattern:

> **Synthetic-fixture-vs-production-emitter shape drift — FOURTH CUMULATIVE INSTANCE (T-A.1.5b CLI dict→str + T-A.1.8 cassette filter chain).** The T-A.1.5b dispatch closed a CLI dict→str shape drift where `_SilverLabelResponse.structural_evidence_json` was typed `str` but the subagent contract emits a JSON object; test fixtures used `json.dumps({...})` (pre-serialized string-in-a-string) masking the bug until production-shape input fired `sqlite3.ProgrammingError: type 'dict' is not supported`. The T-A.1.8 dispatch added a similar surface at the cassette filter chain — Codex R1 Major #3 caught that the cassette E2E test ran the sentinel-leak audit but NEVER actually exercised the `codex_mcp_vcr_config()` filter chain (`before_record_request` + `before_record_response`); a contributor recording a real-MCP-HTTP cassette without the filter chain attached would silently leak secrets. **The defense-in-depth pattern across all 4 instances**: (a) production-shape fixtures derived from real emitter output (T-A.1.5b: `tests/fixtures/pattern_labeler/silver_response_vcp_dict_shape.json` from `tmp/phase13-labeling/silver_1_SNAP_vcp.json`); (b) CLI-level explicit shape coercion + validation at parse time; (c) dataclass-level `__post_init__` coercion + validation; (d) filter-chain regression tests that exercise the filter against synthetic sentinels even when the upstream traffic-recording is V2-deferred. Pre-empt: in any new file-based parse + dataclass-construction code path OR any new cassette-filter chain, the discriminating test MUST exercise the production-shape input through the production filter chain, NOT a synthetic shortcut.

##### Gotcha #2 — Brief-prescription-vs-schema-CHECK collision

> **Brief-prescription-vs-schema-CHECK collision — closing a "preserve operator-set column" prescription may collide with the table's CHECK constraints.** Failure mode discovered 2026-05-20 (Phase 13 T2.SB1 T-A.1.8 Deficiency 2 closure). The closer dispatch brief §1.2 prescribed `preserve final_pattern_class as-is` for the relabel-to-gold workflow. The literal prescription is INCOMPATIBLE with `pattern_exemplars` Invariant #1 (CHECK constraint at migration `0020_phase13_charts_patterns_autofill_usability.sql:109-114` precludes `final_decision='confirmed' AND final_pattern_class IS NOT NULL`). The implementer's semantic-equivalent fix: COALESCE-into-related-column at state transition (`UPDATE ... SET proposed_pattern_class = COALESCE(final_pattern_class, proposed_pattern_class), final_pattern_class = NULL ...`); operator's class choice survives gold promotion + Invariant #1 holds + NO schema migration. **Pre-empt in any future "preserve column at state transition" prescription:** cross-check the table's CHECK constraints first; the literal preservation may be schema-incompatible. If incompatible, the semantic-equivalent fix (COALESCE-into-related-column; capture audit trail in a JSON field; etc.) may be the only schema-faithful path. Brief authors should cite the relevant CHECK constraint shape when prescribing column preservation.

##### Gotcha #3 — Schema-version-aware INSERT for newly-widened columns (T3.SB1)

> **Schema-version-aware INSERT for newly-widened columns** — when a migration widens a table with new NOT-NULL-DEFAULTED columns, the repo INSERT path must detect schema version via `PRAGMA table_info` AND branch between legacy-column-list and new-column-list INSERTs OR all pre-current-version test fixtures must migrate up. T3.SB1 chose the runtime branch at `swing/data/repos/fills.py:51-53` to preserve ~30 pre-v20 fixtures unchanged. Forward-binding lesson: any future migration that adds NOT-NULL-DEFAULTED columns inherits this pattern OR commits to a fixture-update sweep.

##### Gotcha #4 — Hidden anchor 4-tier rejection ladder (T3.SB1)

> **Hidden anchor 4-tier rejection ladder** — when a web form has hidden audit anchors driving POST-time provenance stamping, the canonical pattern is the 4-tier rejection: (a) malformed JSON → 400 + clear anchor on recovery; (b) non-dict JSON → 400 + clear; (c) dict missing required keys → 400 + clear; (d) dict with invalid value shapes (NaN, non-int, calendar-invalid date) → 400 + clear. The `_reject_anchor` helper pattern at `swing/web/routes/trades.py:899-910` is the reusable template. Plus a `claimed_auto_fill` consistency-check gate prevents anti-forgery (valid anchor without claim must NOT stamp provenance).

##### Gotcha #5 — Recovery form anchor-clear discipline (T3.SB1)

> **Recovery form anchor-clear discipline** — on anchor-rejection 400 responses, the recovery form MUST clear the bad anchor (pass `submitted_*=None` to the re-render helper, NOT the raw rejected anchor) — otherwise the operator gets trapped in repeated 400s when their next submit replays the same bad anchor. Forward-binding for any form-rejection path that emits a recovery form. Closes the Phase 13 T3.SB1 Codex R3 Major #2 finding.

##### Gotcha #6 — Literal[...] not runtime-enforced (T-A.1.5b)

> **`Literal[...]` type hints are NOT runtime-enforced.** Failure mode discovered 2026-05-19 (Phase 13 T-A.1.5b Codex R3 M#1). Codex flagged that `confidence: Literal["high", "medium", "low"]` did not validate at runtime — an invalid value would have persisted into `labeler_evidence_json` silently. Pattern for any future dataclass with `Literal[...]` field on the data-integrity path: add explicit `__post_init__` runtime validation against an explicit frozenset of allowed values. Defense-in-depth catches malformed external inputs (subagent emissions; CLI parse paths). Closes a recurring class of "stricter type hint than runtime check" bugs.

##### Gotcha #7 — Service-layer ValueError → CLI ClickException pattern (T-A.1.5b)

> **Service-layer ValueErrors must be wrapped at CLI boundary.** Failure mode discovered 2026-05-19 (Phase 13 T-A.1.5b Codex R4 M#1). Codex flagged that `_map_silver_evaluation_to_decision`'s `relabel:<same_class>` rejection escaped the CLI's construction-time except clause because it fires AFTER `_fire_claude_silver_label` invocation. Pattern: CLI's command-handler boundary must wrap ALL service-layer dispatch calls in `try: ... except ValueError as exc: raise click.ClickException(...)` so any future service-level ValueError (validation, invariant check) surfaces as a clean error rather than a raw traceback.

##### Gotcha #8 — HTF naming: `consolidation_*` not `flag_*` (T-A.1.8)

> **High-tight-flag (HTF) post-pole sub-window is named `consolidation_*`, NOT `flag_*`.** Surfaced 2026-05-20 at Phase 13 T2.SB1 T-A.1.8 Deficiency 3 audit. Spec §5.5 names the post-pole sub-window `consolidation_*` per criterion #3 + #4 lock strings + Structural evidence enumeration (e.g., `consolidation_start_date`, `consolidation_end_date`, `consolidation_pullback_pct`, `consolidation_width_pct`, `consolidation_duration_days`). Operator's colloquial "flag_start_date / flag_end_date" terminology is a misnomer that propagated to T-A.1.7 resume notes. Pre-empt in any future structural_evidence_schema audit or HTF-related work: read the spec section's criterion lock strings (NOT the colloquial pattern name) to identify the canonical sub-window field names. Locked at `tests/patterns/test_spec_static.py::test_high_tight_flag_consolidation_naming_matches_spec_5_5_not_flag_naming` for regression safety.

##### Gotcha #9 — Cross-bundle pin fixture-shape mismatch (T-A.1.8)

> **Cross-bundle pin fixture-shape mismatch silently extends the pin window beyond the schedule.** Surfaced 2026-05-20 at Phase 13 T2.SB1 T-A.1.8 cross-bundle pin disposition for `test_flag_classifier_integration.py:21`. The fixture loader at `tests/evaluation/patterns/_fixtures.py:load_labeled_fixtures` expects paired `<name>.csv` + `<name>.json` files at `tests/evaluation/patterns/fixtures/` with labels `"flag"` or `"none"` — that's the older Phase 3e/7 chart-pattern flag-v1 classifier infrastructure. The T-A.1.7 corpus at `data/phase13-t2-sb1-corpus/pattern_exemplars_dump.jsonl` has a DIFFERENT shape (JSONL with 5 V1 detector pattern classes) + does NOT carry paired OHLCV CSVs. **Pre-empt in any future cross-bundle pin disposition:** verify fixture shape compatibility BEFORE the pin promises an un-skip date. Shape mismatch silently extends the pin window beyond what the schedule documents. Banked as forward-binding for V2 dispatch: either (a) port the Phase 3e flag-v1 classifier to consume the Phase 13 corpus shape (likely T2.SB3+/SB4 territory); OR (b) retire `test_flag_classifier_integration.py` as superseded by Phase 13 detector test suite.

#### B. phase3e-todo.md updates

**New top entry for T2.SB1 SHIPPED** (~120-150 lines covering full chain T-A.1.1 → T-A.1.8 + T-A.1.5b hotfix + T-A.1.7 corpus + 9 forward-binding lessons + cross-bundle pin disposition + 2 pre-existing TZ-drift failures banked + 9 CLAUDE.md gotcha candidates integrated).

**New entry for T3.SB1 SHIPPED** (~80-100 lines covering Codex chain shape + 4 TECHNICALLY SOUND ACCEPT banks + 3 NEW CLAUDE.md gotcha candidates).

**V2 candidates banked (NEW for post-T2.SB1+T3.SB1 backlog)**:
- **Precursor 3-dip "early identifier" detector** — banked at T-A.1.8 brief amendment per operator's TSM/TGT/SNAP annotated chart references. Two design surfaces: (a) labeling-window-vs-setup-quality separation as detector-spec contract; (b) NEW V2 detector surface scoring precursor uptrend + dip-stair-step quality. For T2.SB3+/SB4 detector calibration OR late-Phase-13 sub-bundle.
- **Deficiency 1 (T-A.1.6 template rendering: chart + per-criterion table + narrative)** — DEFERRED. Significant scope; doesn't block T2.SB1 ship; operator has external workaround. Candidates: standalone web-refinement task OR fold into T2.SB6 closed-loop surface.
- **sort_keys byte-original preservation** (T-A.1.5b R1 Minor #1) — V2 audit-trail enhancement if byte-identical preservation later required.
- **Schwab cassette runbook for pattern-labeler** — `scripts/record_pattern_labeler_cassettes.py` scaffold exists but not invoked.
- **Weekly timeframe auto-fetch** in labeling CLI — V1 supports `daily` only.
- **V2 hidden-anchor architectural hardening** (T3.SB1 Codex R1 Critical #1) — replace hidden `schwab_source_value_json` JSON transport with `schwab_api_call_id` server-side audit-row lookup. 30-50 LOC dispatch.
- **VM inheritance refactor** (T3.SB1 Codex R1 Major #4) — all 6 base-layout VMs inherit from `BaseLayoutVM` in a single sweep.
- **Schwab Trader API lookback widening** (T3.SB1 Codex R1 Major #5) — expand lookback to cover GTC / staged orders.
- **Fractional-share support** (T3.SB1 Codex R1 Minor #1) — replace `int(quantity)` truncation in 6+ adapters.

**Phase-9 followup TODO (NEW)**:
- **`is_back_recorded` UTC-vs-HST date-boundary fix** at `swing/trades/account_equity_snapshots.py:49-63`. The `> 7` strict inequality fails on the exact 7-day-boundary day. Two pre-existing test failures: `test_phase9_full_happy_path_across_all_sub_bundles` + `test_phase9_bundle_c_e2e_account_snapshot_and_hypothesis_audit`. One-line fix: change `> 7` to `>= 7` OR make threshold timezone-aware. Banked from T-A.1.8 return report §"Test count pre/post" verification (failures definitively pre-existing per `git diff 6383cfa..phase13-t2-sb1-dev-time-labeling-infra/HEAD -- <affected files>` returning empty).

#### C. orchestrator-context.md updates

**"Currently in-flight work" section refresh**:
- New current state: T2.SB1 + T3.SB1 SHIPPED + post-merge housekeeping complete; T2.SB2 dispatch UNBLOCKED.
- Demote previous current state (T1.SB0 gate-fix SHIPPED + S3 PASS) to first Prior state subsection.
- **Size-check trigger fires**: Prior state count was 10 (at cap pre-this-housekeeping); demoting CURRENT state + adding T2.SB1+T3.SB1 SHIPPED Prior state would push to 11+ → archive oldest 1-2 Prior states.

**`orchestrator-context-archive.md` appendix update**: add new "Appended 2026-05-20" section capturing the archived Prior state(s) verbatim (mirror the 2026-05-19 appendix pattern).

#### D. Commit message structure

Per recent precedent (`6383cfa` T1.SB0 gate-fix housekeeping):
- Heading: `docs(housekeeping): Phase 13 T2.SB1 + T3.SB1 SHIPPED post-merge + 9 NEW CLAUDE.md gotchas + orchestrator-context.md archive-split per size-check trigger`
- Body covers: T2.SB1 + T3.SB1 ship summary + 9 new gotchas description + V2 candidates banked + Phase-9 TZ-drift followup banked + size-check post-flight stats + streaks preserved.
- **NO Co-Authored-By footer.** Cite the discipline.

### §2.3 Push housekeeping commit

```bash
git push origin main
```

Bootstrap verification post-housekeeping:
```bash
git log --oneline -10
git status  # expect clean except untracked scripts/convert_books_pdf_to_md.py (operator-pending)
python -m pytest -m "not slow" -q -n auto | tail -5
# Expect: ~5158 passed (depending on T3.SB1 cross-bundle pin un-skip), 2 failed (TZ-drift pre-existing), <5 skipped
ruff check swing/
python -c "from swing.data.db import EXPECTED_SCHEMA_VERSION; print(EXPECTED_SCHEMA_VERSION)"
# Expect: 20
```

---

## §3 Phase 13 forward dispatch readiness (post-housekeeping)

### §3.1 T2.SB2 next per plan §H.1

After T2.SB1+T3.SB1 ship + housekeeping, plan §H.1 dispatch sequence is:

```
T1.SB0 → T2.SB1 ∥ T3.SB1 → T2.SB2 → T2.SB3 → T3.SB2 → T2.SB4 → T2.SB5 → T3.SB3 → T2.SB6 → T4.SB → CLOSED
              [HERE NOW]
```

T2.SB2 = foundation primitives (smoothing / extrema / zigzag). Per plan §G.3 lines ~1508-1700 (verify exact span before commissioning). 6 tasks; +60-100 fast tests projected.

T2.SB2 inherits the OhlcvCache substrate from T1.SB0 + the v20 schema + the pattern_exemplars/pattern_evaluations/chart_renders/watchlist_close_track repo modules from T-A.1.1b. The forward-binding lessons from T-A.1.7 corpus (cup rounded-vs-V calibration; HTF tightness; VCP monotonic; precursor 3-dip identifier) should inform T2.SB3+/SB4 detector design, NOT T2.SB2.

### §3.2 Pre-Codex orchestrator-side review at T2.SB2

17th cumulative C.C lesson #6 validation expected. Pattern is durably effective (16x CLEAN through T-A.1.8). Continue applying at every executing-plans dispatch.

### §3.3 Deficiency 1 follow-up

**Operator decision needed** post-merge:
- **Option A**: Standalone web-refinement task (small dispatch ~150-300 LOC; mplfinance chart rendering + structural_evidence per-criterion table + narrative display in `swing/web/templates/patterns/exemplars.html.j2`).
- **Option B**: Fold into T2.SB6 closed-loop surface (T2.SB6 already plans pattern-outcomes metric surface; can absorb the rendering enhancements).

Operator preference TBD. Bank in `phase3e-todo.md` as TODO.

### §3.4 Phase-9 TZ-drift followup

**Optional dispatch** (1-line fix; could batch with T2.SB2 or be standalone):
- Change `is_back_recorded` `> 7` to `>= 7` at `swing/trades/account_equity_snapshots.py:49-63`
- OR make threshold timezone-aware (more invasive)
- Closes 2 pre-existing failures `test_phase9_full_happy_path_across_all_sub_bundles` + `test_phase9_bundle_c_e2e_account_snapshot_and_hypothesis_audit`
- Operator-decision-pending whether to dispatch now or wait

### §3.5 Remaining sub-bundles post-T2.SB1+T3.SB1

Per plan §H.1 dispatch sequence (8 more sub-bundles after this merge):
- T2.SB2 (6 tasks; foundation primitives) ← NEXT
- T2.SB3 (9 tasks; detectors batch 1: VCP + flat_base + cup_with_handle)
- T3.SB2 (5 tasks; exit auto-fill; sequenced after T2.SB3)
- T2.SB4 (7 tasks; detectors batch 2: HTF + DBW)
- T2.SB5 (6 tasks; template matching DTW + 120s benchmark gate)
- T3.SB3 (5 tasks; review auto-fill; consumes OhlcvCache patterns)
- T2.SB6 (7 tasks; closed-loop surface + Theme 1 annotated charts)
- T4.SB (7 tasks; usability triage + Q4 close-tracking flag closer)

Phase 13 close projection: ~5500-5940 fast tests after T4.SB closer.

---

## §4 Cumulative streaks to preserve

- **ZERO Co-Authored-By footer trailer drift**: ~239+ commits cumulative through T-A.1.8. ABSOLUTELY DO NOT regress. Explicit citation in commit messages + dispatch prompts is the discipline.
- **ZERO Critical findings across the full T2.SB1 chain** (T-A.1.1 through T-A.1.8 closer including all Codex rounds). Same for T3.SB1.
- **Schema v20 LANDED at T-A.1.1** (4cfd5f2; will be on main post T2.SB1 merge); unchanged through T-A.1.8.
- **Baseline 4939 → 5092 fast** (+153 cumulative across T2.SB1) + 3 slow E2E / **0 ruff E501** / production ZERO open discrepancies (post-merge predicate; 2 TZ-drift failures are pre-existing Phase 9 territory, banked).
- **16x cumulative C.C lesson #6 validation through T-A.1.8 + 14x through T3.SB1** (different validation lineages; both CLEAN streaks).
- **Pre-Codex orchestrator-side review BINDING**: 17th+ validation expected at T2.SB2 + any new dispatches.

---

## §5 Operator-pending items (NOT orchestrator-blocking)

- **Worktree husks pending operator's `cleanup-locked-scratch-dirs.ps1 -DeregisterFirst` pass**: `phase13-t2-sb1-dev-time-labeling-infra` + `phase13-t3-sb1-entry-auto-fill` (both ready for cleanup after merge ships).
- **Untracked `scripts/convert_books_pdf_to_md.py`** (carried since previous handoff; operator-decision-pending; not blocking).
- **Untracked `tmp/phase13-labeling/`** in worktree (operator's T-A.1.7 paired-session artifacts: 34 dispatch payloads + 34 silver responses + 34 chart PNGs; preserved for fixture provenance per T-A.1.5b discipline; not blocking).
- **Schwab refresh-token clock**: operator runs `swing schwab status --environment production` to check; renew via `/schwab/setup` web if expired (~7-day rolling clock).
- **Production `~/swing-data/swing.db` is at schema v20** (operator manually ran `swing db-migrate` during T-A.1.7 paired session; backup at `~/swing-data/backups/swing-20260519T070446.db`). Once T2.SB1 merges to main, the production DB + main repo align at v20.
- **2 pre-existing TZ-drift failures** ban Phase-9-followup-pending. NOT introduced by T2.SB1 (verified). Banked for separate dispatch.
- **T-A.1.7 corpus** committed at `bd0775f` (manifest + JSONL dump at `data/phase13-t2-sb1-corpus/`); 13 gold / 21 silver across 5 V1 pattern classes; operator-acknowledged 13/25 deviation accepted.

---

## §6 Suggested first session flow

1. Read this brief + return reports + corpus manifest + orchestrator-context current-state + Phase 13 plan §H.1 + CLAUDE.md (end-to-end).

2. **Execute T2.SB1 merge** (§2.1.A). Verify clean merge + bootstrap pass + ZERO trailer + push.

3. **Execute T3.SB1 merge** (§2.1.B). Verify clean merge + bootstrap pass + cross-bundle pin un-skip + ZERO trailer + push.

4. **Draft + execute combined post-merge housekeeping commit** (§2.2). This is the largest single-artifact deliverable; expect 30-60K tokens of orchestrator context to assemble (CLAUDE.md line 3 refresh + 9 gotcha additions + phase3e-todo entries × 2 + V2 candidates × 9 + orchestrator-context refresh + Prior state archive-split). Size-check trigger WILL fire on Prior state count.

5. **Push housekeeping**.

6. **Operator-witnessed S2/S3 gates** for both bundles (operator-paired session). T2.SB1: `python -m swing.cli web` + visit `/patterns/exemplars` to spot-check + `swing patterns label-exemplars --help` smoke. T3.SB1: browser `/trades/entry/form` with Schwab auto-fill exercise.

7. **Commission T2.SB2** (next per plan §H.1; foundation primitives). Brief + plan §G.3 lookup + inline dispatch prompt.

8. **Optional**: dispatch Phase-9 TZ-drift one-line fix (operator decision; could batch with T2.SB2 or wait).

9. **Optional**: commission Deficiency 1 follow-up OR document fold-in to T2.SB6 (operator decision).

---

## §7 Do NOT

- Re-litigate T-A.1.8 + T3.SB1 outcomes (ALL SHIPPED + Codex-closed + QA-verified).
- Re-merge T2.SB1 or T3.SB1 (idempotent; both are `--no-ff` merges that should land once).
- Skip pre-Codex orchestrator-side review at T2.SB2 or any future dispatch (C.C lesson #6 BINDING).
- Add Co-Authored-By footer to ANY commit (CLAUDE.md binding convention; ~239+ streak).
- Touch the v20 migration semantics (locked).
- Modify the T-A.1.7 corpus at `data/phase13-t2-sb1-corpus/*` (operator-validated as-is).
- Address Deficiency 1 (T-A.1.6 template rendering) in the housekeeping commit (DEFERRED per T-A.1.8 brief §1.2; separate dispatch).
- Fix the 2 TZ-drift failures inline in housekeeping (DEFERRED; separate Phase-9 followup dispatch; banked in phase3e-todo).
- Commit any change to `~/swing-data/` (operator's local DB; production state).
- Push without verifying ZERO trailer trailer on the commit.
- Skip size-check pre-flight before housekeeping (Prior state count is at cap; archive-split WILL fire).

---

## §8 Quick-reference SHA roster

| Item | SHA |
|---|---|
| main HEAD at handoff | `6383cfa` |
| T-A.1.1 v20 migration (T3.SB1 branch base) | `4cfd5f2` |
| T2.SB1 worktree HEAD | `9904e8a` |
| T3.SB1 worktree HEAD | `a73bab6` |
| T2.SB1 interim return report (predecessor; historical) | `3c925a2` |
| T-A.1.5b hotfix HEAD | `b461f03` |
| T-A.1.7 corpus commit | `bd0775f` |
| T-A.1.8 closer HEAD = T-A.1.8 final return report | `9904e8a` (post-Codex chain) |
| Post-T2.SB1+T3.SB1+housekeeping HEAD | `<your housekeeping commit SHA>` |

---

## §9 Forward-binding lessons surfaced this session

Inherited from T-A.1.8 final return report §"Forward-binding lessons banked" (9 lessons):

1. **Synthetic-fixture-vs-production-emitter shape drift** (FOURTH instance; cumulative discipline).
2. **`Literal[...]` not runtime-enforced** (T-A.1.5b inherited).
3. **Service-layer ValueError → CLI ClickException** (T-A.1.5b inherited).
4. **Cup-with-handle rounded-vs-V hard gate** caused 4 of 5 cup dispatches to fail by sub-1% margins. T2.SB3 should widen OR downgrade to scoring penalty.
5. **HTF consolidation tightness** — widen for high-magnitude-pole cases.
6. **VCP monotonic-tightening hard gate** — consider 1-violation tolerance.
7. **SNAP reproducibility variance** — subagent non-determinism; Codex 2nd-reviewer SHOULD catch.
8. **TSM 4-framing exhausted** — V2 detector enrichment candidate.
9. **Precursor 3-dip "early identifier" pattern** — banked at T-A.1.8 brief amendment per operator TSM/TGT/SNAP chart references. Two surfaces: (a) labeling-window-scoped-to-base contract for T2.SB3+/SB4 detector specs; (b) NEW V2 detector surface.

**Orchestrator-side lesson surfaced this session**: when handing off mid-arc (post-T-A.1.8 SHIPPED + pre-merge), the brief should enumerate the MERGE SEQUENCE + HOUSEKEEPING DELIVERABLES with verbatim content (not just pointers) because the housekeeping commit assembly is the heaviest single-artifact orchestrator-inline work + the new orchestrator should be able to assemble it without re-reading 30+ predecessor docs. THIS brief honors that pattern.

---

*End of handoff brief. Post-T-A.1.8-SHIPPED + T3.SB1-SHIPPED + pre-merge orchestrator transition. T2.SB1 → T3.SB1 merge sequence + post-merge housekeeping with 9 CLAUDE.md gotcha additions + V2 candidates banking + Prior state archive-split (size-check trigger fires) are the CRITICAL FIRST TASKS. ~239+ cumulative ZERO Co-Authored-By footer drift streak preserved through both bundles. 16x cumulative C.C lesson #6 validation BANKED CLEAN. Schema v20 ready to LAND on main via T2.SB1 merge. T2.SB2 next per plan §H.1. Operator-paced.*
