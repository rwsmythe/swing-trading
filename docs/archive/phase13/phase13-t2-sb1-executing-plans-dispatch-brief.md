# Phase 13 T2.SB1 — Executing-Plans Dispatch Brief

**Audience:** Fresh Claude Code instance dispatched as the Phase 13 T2.SB1 executing-plans implementer. No prior conversation context.

**Mission:** Execute the 9-task T2.SB1 plan (v20 migration atomic landing + dev-time labeling infrastructure + selective Codex 2nd-reviewer + operator-paired mid-dispatch exemplar bootstrap pause). Foundation for Theme 2 detectors. T2.SB1 ships **CONCURRENT with T3.SB1** per OQ-12 Option E — T3.SB1's worktree branches off T2.SB1's first-commit SHA (the T-A.1.1 v20 migration-only commit), so T2.SB1's first commit must land first.

**Brief:** `docs/phase13-t2-sb1-executing-plans-dispatch-brief.md` (this file).

**Plan (PRIMARY):** `docs/superpowers/plans/2026-05-18-phase13-charts-patterns-autofill-usability-plan.md` §G.1 (lines 1044-1343; 9 tasks T-A.1.1..T-A.1.8 + T-A.1.1b split per Codex R1 M#1 + R2 M#2 closure).

**Sequencing:** T1.SB0 SHIPPED 2026-05-18 PM at `418bcc8` (post-merge housekeeping at `dc0cfea`). T2.SB1 ∥ T3.SB1 concurrent dispatch UNBLOCKED per OQ-12 Option E. T2.SB1 must commission BEFORE T3.SB1 (T3.SB1 branches off T2.SB1's T-A.1.1 first-commit SHA).

**Expected duration:** **3-5 substantive Codex rounds** (largest single sub-bundle in Phase 13 arc by LOC; +500-800 prod + +600-900 test LOC projected per plan §K; 9 tasks; v20 atomic schema landing + dev-time labeling infra + operator-paired pause). Test delta projection: **+50-90 fast tests + 0 slow** (cassette-mode); schema delta: **v19 → v20 single migration** (per OQ-12 Option E + §B.4 atomic-landing roster).

---

## §0 Read first

In this order:

1. **`docs/superpowers/plans/2026-05-18-phase13-charts-patterns-autofill-usability-plan.md`** — PRIMARY SUBSTRATE. Read end-to-end at minimum: §0 top-matter + §A general architectural decisions (especially §A.14 constant-placement LOCK + §A.7 pattern labeler subagent + §A.10 cassette infrastructure + §A.14 paired-atomic-landing) + **§B v20 migration mechanics (OQ-12 Option E coordination at §B.2; atomic-landing roster at §B.4; escalation rule at §B.6)** + **§G.1 T2.SB1 (lines 1044-1343; THE 9-TASK SPEC for this dispatch)** + §H.3 cross-bundle pin schedule + §K test/LOC projections + §L forward-binding lessons.

2. **`docs/phase13-t2-sb1-executing-plans-dispatch-brief.md`** (this file).

3. **`docs/superpowers/specs/2026-05-18-phase13-charts-patterns-autofill-usability-design.md`** — operator-confirmed brainstorm spec (1483 lines). Read §1 LOCKS L1-L11 + §3 v19→v20 schema delta (especially §3.0 DETECTOR_PATTERN_CLASSES + §3.1 pattern_exemplars 5 cross-column CHECK invariants + §3.5 migration mechanics) + §5 Theme 2 (especially §5.9 dev-time labeling infrastructure) + §11 forward-binding lessons inherited.

4. **`docs/orchestrator-context.md`** sections "Currently in-flight work" + "Lessons captured" + "Maintenance: retention discipline".

5. **`CLAUDE.md`** at repo root — project conventions + gotchas. **Especially**:
   - **Schema-CHECK + Python-constant + dataclass-validator paired atomic landing** (Phase 12 C.A T-A.2 LOCK; BINDING for T-A.1.1).
   - **Migration backup-gate strict equality** (`pre_version == 19`, NOT `<=`; Phase 9 Sub-bundle A precedent).
   - **`executescript()` implicit-COMMIT gotcha** (migration runner uses explicit BEGIN/COMMIT/ROLLBACK; foreign_keys=OFF discipline; Phase 7 hotfix `283d4fa` canonical).
   - **`INSERT OR REPLACE` cascade-wipe gotcha** (use SELECT-then-UPDATE-or-INSERT for UPSERT; Phase 8 daily-management precedent).
   - **Cassette URI/path + body sanitization** (post-Phase-12 forward-binding lesson #2; T2.SB1 ships NEW cassette infrastructure for Claude Code subagent labeler + Codex MCP review).
   - **NEW Phase 13 T1.SB0 gotchas** (just landed at `dc0cfea`):
     - Session-anchor inequality discipline (forward-looking `>=` vs backward-looking `>`).
     - Hook fallback window-completeness (return full archive; consumers slice).
   - Existing Phase 8 form-driven-route discipline (server-stamp hidden audit fields at handler entry; display-only `<span class="muted">`; remove hidden inputs from form).
   - Test fixture USERPROFILE+HOME monkeypatch (Phase 9 Sub-bundle A lesson).
   - Windows cp1252 stdout (ASCII-only on runtime CLI paths).

6. **Existing `swing/data/models.py`** — T-A.1.1 lands 5 NEW dataclasses + widens 2 existing dataclasses; read existing dataclass patterns (especially `__post_init__` validator structure from Phase 12 C.A precedent).

7. **Existing `swing/data/db.py`** — `EXPECTED_SCHEMA_VERSION` constant + `_apply_migration` function with backup-gate; T-A.1.1 bumps version 19 → 20.

8. **Existing `swing/integrations/schwab/audit_service.py`** — T-A.1.1 widens `_SCHWAB_API_SURFACE_VALUES` to include `'trade_entry'` + `'trade_exit'`.

9. **Existing `swing/data/repos/`** — existing repo patterns (especially `fills.py`); T-A.1.1b creates 4 NEW repo modules (`pattern_exemplars.py`, `pattern_evaluations.py`, `chart_renders.py`, `watchlist_close_track.py`).

10. **Existing Schwab cassette infrastructure** at `tests/integrations/cassettes/schwab/` + `scripts/record_schwab_cassettes.py` — T2.SB1 cassettes for `pattern_labeler` + `codex_mcp_pattern_review` follow the SAME sanitization filter discipline.

11. **Precedent executing-plans dispatch briefs**:
    - `docs/phase13-t1-sb0-executing-plans-dispatch-brief.md` (just shipped; smallest sub-bundle precedent).
    - `docs/phase12-5-bundle-1-oqf-executing-plans-dispatch-brief.md` (Phase 12.5 #1 executing-plans precedent).
    - `docs/phase12-5-bundle-3-project-hygiene-executing-plans-dispatch-brief.md` (Phase 12.5 #3 precedent).

---

## §0.5 Skill posture

- Invoke **`copowers:executing-plans`** (wraps `superpowers:subagent-driven-development` + adversarial Codex review). Iterate to `NO_NEW_CRITICAL_MAJOR`.
- Plan §G.1 has per-task acceptance criteria + per-step instructions. Follow plan exactly; do NOT deviate.
- Use **`superpowers:test-driven-development`** for per-task work.
- **T-A.1.7 is the operator-paired pause** — implementer ships labeling infra + recording-script + sanitization filter through T-A.1.6; at T-A.1.7 signal operator to run labeling against historical universe + commit exemplar corpus to worktree branch; then continue T-A.1.8.

---

## §1 Strategic context

### §1.1 T2.SB1 scope (per plan §G.1)

- **Goal**: Land v20 migration atomically (T-A.1.1; per §B.4 + §A.14 paired-atomic-landing LOCK); ship dev-time labeling infrastructure (Claude Code subagent + selective Codex 2nd-reviewer); operator-paired mid-dispatch exemplar bootstrap pause per OQ-6.
- **Branch**: `phase13-t2-sb1-dev-time-labeling-infra`. Worktree branches from main HEAD `dc0cfea` (post-T1.SB0-housekeeping) at dispatch time.
- **Files in scope** (per plan §G.1 line 1051-1064): see plan; ~13 files create/modify.

### §1.2 OQ-12 Option E coordination (BINDING per §B.2)

T-A.1.1 is **migration-only commit**:
1. T2.SB1 worktree branches from main HEAD `dc0cfea` at dispatch time.
2. T-A.1.1 commits the v20 migration file + `EXPECTED_SCHEMA_VERSION` bump + Python constants + dataclass validators + Schwab audit-service widening **ATOMIC** per §B.4 (NO Python-then-validator split; NO NEW repo CRUD bundled).
3. **Record T-A.1.1's commit SHA** — operator relays to T3.SB1 implementer for worktree branch-base coordination.
4. T-A.1.1b lands NEW repo CRUD modules SEPARATELY (per Codex R1 M#1 + R2 M#2 closure) AFTER T-A.1.1.
5. T2.SB1 remaining tasks (T-A.1.2..T-A.1.8) proceed in parallel with T3.SB1 (T3.SB1 worktree branches off T-A.1.1's SHA).
6. Merge ordering: T2.SB1 merges first; T3.SB1 merges second.

### §1.3 Per-task structure (per plan §G.1)

- **T-A.1.1** — v20 migration atomic landing (MIGRATION-ONLY commit per OQ-12 Option E).
- **T-A.1.1b** — NEW repo CRUD modules (`pattern_exemplars.py`, `pattern_evaluations.py`, `chart_renders.py`, `watchlist_close_track.py`).
- **T-A.1.2** — `swing/cli.py` `swing patterns label-exemplars` subcommand skeleton.
- **T-A.1.3** — Claude Code subagent definition at `.claude/agents/pattern-labeler.md` (per OQ-11; project-local).
- **T-A.1.4** — `swing/patterns/labeling.py` — subagent dispatch + selective Codex 2nd-reviewer 15% random per OQ-5 phased rollout.
- **T-A.1.5** — Cassette infrastructure (`scripts/record_pattern_labeler_cassettes.py` + `tests/integrations/cassettes/pattern_labeler/` + sanitization filter per forward-binding lesson #9).
- **T-A.1.6** — Web UI skeleton for exemplar inspection (`swing/web/routes/patterns.py` + `swing/web/view_models/patterns/exemplars.py` + `swing/web/templates/patterns/exemplars.html.j2`; HTMX gotcha trinity + base-layout VM banner pin).
- **T-A.1.7** — **OPERATOR-PAIRED PAUSE** — implementer signals operator to run labeling against historical universe + spot-check + commit ~30-80 silver-tier exemplars to worktree branch.
- **T-A.1.8** — Closer (Codex retroactive evaluation activation; cross-bundle pin plant; ruff sweep).

Each task has per-step instructions in plan §G.1 — follow them verbatim. Each task ends with a commit per the plan-provided commit message.

### §1.4 Inherited LOCKS + DROPS (per plan §A + spec §1.4)

- **L1**: No run-time AI inferencing. DEV-TIME ONLY for the labeler subagent.
- **L9**: Codex SELECTIVE policy phased per OQ-5 — T2.SB1 implements **random 15% only** (high-stakes disagreement clause activates at T2.SB3+/SB4 retroactively).
- **§A.14 LOCK BINDING**: ALL v20 enum constants live in `swing/data/models.py`; later modules IMPORT not REDEFINE.
- **§A.15 LOCK**: NO `INSERT OR REPLACE` on `pattern_exemplars` / `pattern_evaluations` / `chart_renders` / `watchlist_close_track_flags` / `watchlist_close_track_flag_events`.
- **§B.6 escalation rule**: NO new schema beyond plan §G.1 + spec §3. If you find yourself adding a column or table that's not in spec §3, STOP + escalate.

### §1.5 Cross-bundle pins (per plan §H.3)

T-A.1.1 plants:
- `test_schema_version_v20_invariant` (un-skips at T3.SB1 merge).
- `test_pattern_exemplars_schema_shape_invariant` (un-skips at T2.SB3 + T2.SB5).
- `test_v20_atomic_landing_python_constants_validators_paired` (un-skips at T4.SB closer).

### §1.6 Forward-binding lessons inherited (most-load-bearing for T2.SB1)

1. **Schema-CHECK + Python-constant + dataclass-validator paired atomic landing** (Phase 12 C.A T-A.2 LOCK; §A.14 + §B.4 BINDING).
2. **Migration backup-gate strict equality** (`pre_version == 19`).
3. **`executescript()` implicit-COMMIT gotcha** — migration runner uses explicit BEGIN/COMMIT/ROLLBACK.
4. **Cassette URI/path + body sanitization** (post-Phase-12 forward-binding lesson #2; T-A.1.5 ships NEW cassette infrastructure).
5. **Standalone recording scripts** (post-Phase-12 forward-binding lesson #3; `scripts/record_pattern_labeler_cassettes.py`).
6. **HTMX gotcha trinity** — T-A.1.6 web routes inherit.
7. **Base-layout VM banner pin** — `PatternExemplarsVM` populates `unresolved_material_discrepancies_count` + `banner_resolve_link`.
8. **Phase 13 T1.SB0 NEW gotcha #1**: Session-anchor inequality discipline (forward-looking `>=`; backward-looking `>`).
9. **Phase 13 T1.SB0 NEW gotcha #2**: Hook fallback window-completeness (full archive; consumers slice).

---

## §2 Executing-plans scope

Execute plan §G.1 verbatim. The plan provides per-task acceptance criteria, per-step instructions with TDD pattern, per-task commit messages, and operator-witnessed gate definitions.

Plan §G.1 lines 1044-1343 are authoritative. Implementer follows exactly. Any deviation requires escalation to orchestrator (do NOT silent-deviate).

---

## §3 OUT OF SCOPE

- **Schema changes beyond plan §G.1 + spec §3** — §B.6 escalation rule BINDING.
- **Theme 2 detector code** — T2.SB1 ships LABELING INFRASTRUCTURE only; detectors at T2.SB3 + T2.SB4.
- **Foundation primitives** (smoothing / extrema / zigzag) — those land at T2.SB2.
- **Theme 3 entry auto-fill code** — T3.SB1 ships concurrent.
- **Codex high-stakes disagreement clause** — T2.SB1 phase is random-15%-only per OQ-5 phased rollout; clause activates at T2.SB3+/SB4 retroactively.
- **Run-time AI inferencing** — L1 LOCK; labeler subagent is DEV-TIME ONLY.

---

## §4 Binding conventions

- **Branch**: `phase13-t2-sb1-dev-time-labeling-infra` (per plan §G.1 line 1048). Worktree at `.worktrees/phase13-t2-sb1-dev-time-labeling-infra/` (branches from main HEAD `dc0cfea`).
- **Commit messages**: per-task message provided in plan §G.1. Do NOT amend; do NOT bundle multiple tasks into one commit.
- **NO Claude co-author footer.** CLAUDE.md binding convention. Cumulative streak ~204+ commits ZERO trailer drift. **DO NOT regress** (per fresh forward-binding lesson #7 Phase 12 C.B 2026-05-15: no `Co-Authored-By: Claude Opus 4.7 (1M context) <noreply@anthropic.com>` (or any other) footer on ANY commit).
- **`python -m swing.cli`** at worktree-side gates (per memory entry `feedback_worktree_cli_invocation.md` BINDING).
- **ASCII-only on runtime CLI paths** (Windows cp1252 stdout gotcha).
- **TDD discipline** per task.
- **Pre-Codex orchestrator-side review** per C.C lesson #6 BINDING — 12th cumulative validation expected (validated 11x; CLEAN at T1.SB0).
- **Operator-witnessed gate**: S1 inline pytest+ruff; S2 `python -m swing.cli patterns label-exemplars --help` (post T-A.1.2) + production-readiness check (post T-A.1.8); S3 operator-paired exemplar bootstrap at T-A.1.7 (BINDING operator-paired pause).

---

## §5 Adversarial review watch items

1. **Plan §G.1 per-task structure integrity** — 9 tasks executed verbatim; no bundling.
2. **T-A.1.1 strict migration-only commit** — NO repo CRUD bundled (per Codex R1 M#1 + R2 M#2 closure); T-A.1.1b lands repos AFTER T-A.1.1.
3. **Record T-A.1.1 first-commit SHA** for T3.SB1 worktree branch-base coordination — operator relays.
4. **§A.14 constant-placement LOCK** — ALL v20 enum constants in `swing/data/models.py`; `swing/patterns/__init__.py` re-exports `DETECTOR_PATTERN_CLASSES` for namespace; later modules IMPORT.
5. **§B.4 atomic-landing roster** — all 10 items land in T-A.1.1 (atomic per Phase 12 C.A T-A.2 LOCK).
6. **5 cross-column CHECK invariants on `pattern_exemplars`** — schema-defended + Python `__post_init__` validators mirrored (paired discipline).
7. **Migration backup-gate strict equality** — `pre_version == 19` not `<=`.
8. **`executescript()` implicit-COMMIT gotcha** — migration runner explicit BEGIN/COMMIT/ROLLBACK with foreign_keys=OFF.
9. **NO `INSERT OR REPLACE`** on any of 5 NEW audit-trail tables.
10. **OQ-5 phased Codex policy** — T2.SB1 is random-15%-only; do NOT activate high-stakes disagreement clause (that activates at T2.SB3+/SB4 retroactively).
11. **T-A.1.7 operator-paired pause** — implementer signals operator + waits for resume signal + does NOT auto-proceed.
12. **Cassette URI/path + body sanitization** — `before_record_request` + `before_record_response` filters installed.
13. **Standalone recording scripts** — `record_pattern_labeler_cassettes.py` + `record_codex_mcp_pattern_review_cassettes.py` are scripts (not @pytest.mark.vcr(record_mode='new_episodes')).
14. **HTMX gotcha trinity** at T-A.1.6 web route.
15. **Base-layout VM banner pin** at `PatternExemplarsVM`.
16. **Test fixture USERPROFILE+HOME monkeypatch** for any test touching user-config.toml write paths.
17. **Phase 13 T1.SB0 NEW gotchas honored** — session-anchor inequality discipline + hook fallback window-completeness.
18. **Implementer self-report accuracy gate** — return report cites file:line evidence + test counts pre/post + commit SHAs verbatim.

---

## §6 Done criteria

1. Branch `phase13-t2-sb1-dev-time-labeling-infra` at `.worktrees/phase13-t2-sb1-dev-time-labeling-infra/`; 9 task-commits + optional Codex-fix commits + 1 return report commit.
2. 9 tasks T-A.1.1..T-A.1.8 + T-A.1.1b executed per plan §G.1 per-step instructions verbatim.
3. ≥3 Codex rounds → NO_NEW_CRITICAL_MAJOR (3-5 rounds expected).
4. T-A.1.1 is MIGRATION-ONLY commit (per OQ-12 Option E); first-commit SHA recorded.
5. T-A.1.1b NEW repo CRUD lands AFTER T-A.1.1 (separate commit).
6. v20 migration atomic landing (per §B.4 roster); `EXPECTED_SCHEMA_VERSION == 20`.
7. 6 v20 atomic-landing discriminating tests pass.
8. T-A.1.7 operator-paired pause executed (operator runs labeling + commits exemplar corpus; implementer resumes).
9. Cross-bundle pins planted (3 pins per §H.3 at T-A.1.1).
10. Cassette infrastructure shipped with URI/path + body sanitization.
11. `.claude/agents/pattern-labeler.md` Claude Code project-local subagent definition.
12. HTMX gotcha trinity honored at T-A.1.6 web route.
13. Base-layout VM banner pin honored at `PatternExemplarsVM`.
14. Operator-witnessed gate: S1 inline pytest+ruff PASS; S2 + S3 operator-paired session.
15. Return report at `docs/phase13-t2-sb1-return-report.md` per §7.
16. ZERO Co-Authored-By footer trailer drift across all commits (verified via `git log --pretty=format:"%(trailers:key=Co-Authored-By)"`).

---

## §7 Return report format

```
## Return report — Phase 13 T2.SB1

### Sub-bundle location
Worktree branch: `phase13-t2-sb1-dev-time-labeling-infra` at `.worktrees/phase13-t2-sb1-dev-time-labeling-infra/`
Commits on branch (per task; verbatim plan-provided commit messages):
- {sha} T-A.1.1 — v20 migration atomic landing (MIGRATION-ONLY commit per OQ-12 Option E)
  **CRITICAL: this SHA must be recorded for T3.SB1 worktree branch-base coordination.**
- {sha} T-A.1.1b — NEW repo CRUD modules
- ... (T-A.1.2 through T-A.1.8)
- (optional) {sha} Codex R<N> fix bundles
- {sha} Return report

### Codex review history
- Pre-Codex (orchestrator-side review per C.C lesson #6 BINDING): {N findings absorbed; 12th cumulative validation}
- R1..RN: ... (3-5 rounds expected)
- Final verdict: NO_NEW_CRITICAL_MAJOR

### v20 atomic landing
- All 10 items per §B.4 landed in T-A.1.1: {confirm}
- 6 discriminating tests pass: {confirm}
- T-A.1.1 first-commit SHA: {SHA}  ← T3.SB1 worktree branch base

### Operator-paired pause results (T-A.1.7)
- Exemplar corpus committed by operator: {N exemplars; corpus SHA}
- Selective Codex 15% random firing: {N exemplars reviewed by Codex; M agreements / K disagreements}

### Test count pre/post
- Pre-baseline: 4935 fast (HEAD dc0cfea)
- Post-T2.SB1: {fast count} (delta: +{N}; within +50-90 projection)

### Operator-witnessed gate results
- S1 (inline pytest+ruff): {PASS/FAIL}
- S2 (CLI surface check): {PASS/FAIL}
- S3 (operator-paired exemplar bootstrap at T-A.1.7): {PASS/FAIL}

### Cross-bundle pins planted
- `test_schema_version_v20_invariant` at {file:line}; un-skips at T3.SB1 merge.
- `test_pattern_exemplars_schema_shape_invariant` at {file:line}; un-skips at T2.SB3 + T2.SB5.
- `test_v20_atomic_landing_python_constants_validators_paired` at {file:line}; un-skips at T4.SB closer.

### V2.1 §VII.F amendment candidates banked
### Forward-binding lessons for downstream sub-bundles
### Capture-needs for next sub-bundle dispatch
### Outstanding capture-needs that DEFER
```

---

## §8 If you get stuck

- If plan §G.1 per-step instructions conflict with reality, STOP + escalate.
- If T-A.1.1 reveals schema work beyond plan §G.1 + spec §3, STOP — §B.6 escalation rule.
- If you find yourself bundling NEW repo CRUD into T-A.1.1, STOP — that violates OQ-12 Option E migration-only boundary.
- If Codex finds an issue that requires SCHEMA changes beyond spec §3, ACCEPT-with-rationale + escalate.
- If operator doesn't return from T-A.1.7 pause within 4 hours, prompt them again; do NOT auto-proceed.
- If you find yourself proposing run-time AI inferencing, STOP — L1 LOCK violated.

---

*End of brief. Phase 13 T2.SB1 executing-plans dispatch — 9 tasks (T-A.1.1 migration-only + T-A.1.1b NEW repo CRUD + T-A.1.2..T-A.1.8 dev-time labeling infra) per plan §G.1; v20 migration atomic landing per OQ-12 Option E; operator-paired exemplar bootstrap at T-A.1.7; CONCURRENT with T3.SB1 (T3.SB1 branches off T-A.1.1's first-commit SHA). Worktree branch `phase13-t2-sb1-dev-time-labeling-infra` from main HEAD `dc0cfea`. Expected 3-5 Codex rounds; ZERO ACCEPT-WITH-RATIONALE preferred. Pre-Codex orchestrator-side review BINDING per C.C lesson #6 (12th cumulative validation).*
