# Pipeline-Step Silent-Skip Warnings_JSON Visibility Fix — Dispatch Brief (Option A)

**Audience:** Fresh Claude Code instance dispatched as the pipeline-step silent-skip warnings_json visibility patch implementer. No prior conversation context.

**Mission:** Implement the **Option A operational hygiene fix** per the `_step_pattern_detect` silent no-op investigation (merge `54bd9c6`; findings doc at `docs/phase13-pattern-detect-step-silent-noop-investigation-2026-05-24.md`). Emit a `warnings_json` entry whenever a pipeline step's early-return guard fires (e.g., empty pool / no targets / nothing to do). Operator monitoring then surfaces "step X processed 0 items (expected non-zero)" as a soft warning instead of the current invisible silent-skip.

This is a **small operator-approved production code change** (~10-15 lines per step modified) gated on operator approval at QA. Generalization scope per gotcha #27: audit ALL existing pipeline steps in `swing/pipeline/runner.py` for early-return paths + apply the same discipline.

**Workflow:** `superpowers:test-driven-development` skill (TDD; test-first → impl → commit per slice). Codex MCP review OPTIONAL — invoke only if scope expands beyond ~50 lines or introduces a new schema column.

**Branch:** `swing-pipeline-pattern-detect-warnings-json-visibility-fix` — branches from main HEAD `92915c0` (or later).

**Worktree:** `git worktree add .worktrees/swing-pipeline-pattern-detect-warnings-json-visibility-fix swing-pipeline-pattern-detect-warnings-json-visibility-fix`. Work from that cwd; invoke `python -m swing.cli` (NOT bare `swing`).

**Expected duration:** ~2-4 hours operator-paced.

---

## §0 Read first

1. **`docs/phase13-pattern-detect-step-silent-noop-investigation-2026-05-24.md`** — predecessor investigation findings. Especially §6 banked Option A remediation candidate.
2. **`swing/pipeline/runner.py:1485-1490`** — the empty-pool early-return at `_step_pattern_detect`. The canonical fix site.
3. **`swing/pipeline/runner.py`** full file — locate ALL pipeline-step early-return paths (not just pattern_detect). Audit list goes in findings.
4. **`swing/data/repos/pipeline_runs.py`** (or equivalent) — locate the existing `warnings_json` write helper. Pattern existing usage for style consistency.
5. **CLAUDE.md gotcha #27** — the binding discipline this fix implements; canonical lesson + discriminating-test pattern.

---

## §1 Scope

### §1.1 Primary fix at `_step_pattern_detect:1485-1490`

When the empty-pool early-return fires, emit a `warnings_json` entry with:
- `step`: `'pattern_detect'`
- `condition`: `'empty_pool'`
- `pool_predicate`: `"bucket == 'aplus'"`
- `total_candidates_evaluated`: N (count of candidates pre-filter)
- `pool_size_post_filter`: 0
- `eval_run_id`: the current eval_run

Pattern: append to existing `pipeline_runs.warnings_json` array (per existing helper precedent).

### §1.2 Generalization audit per gotcha #27

Walk every `_step_*` function in `runner.py` + identify each early-return path. For EACH such path, determine whether the early-return represents:
- (a) Genuine "nothing to do" condition (e.g., no open trades for an open-trades-only step) → MAY skip warnings_json entry (no operator-actionable signal)
- (b) Unexpected empty condition where operator monitoring would benefit from visibility (e.g., empty pool because of upstream pipeline state) → ADD warnings_json entry per the discipline

Document the per-step disposition in findings. Implement warnings_json emission for cases matching (b).

### §1.3 Discriminating-test pattern (TDD)

Per gotcha #27 binding test pattern:
- Plant a pipeline run state with deliberately empty pool conditions (e.g., zero aplus candidates).
- Run the affected step.
- Assert the step's silent-skip path emits a `warnings_json` entry with the expected fields.
- Assert the test FAILS pre-fix (current state: no warnings_json entry) + PASSES post-fix.

### §1.4 NON-fix scope

- Do NOT widen the pool predicate (that's Option C; separate scope).
- Do NOT build a cohort-detection harness (that's Option D; separate dispatch).
- Do NOT backfill historical 78 pipeline_runs with retrospective warnings_json (banked V2 candidate).
- Do NOT modify the broad except / log.warning best-effort pattern itself (that's the canonical step-failure shape).

---

## §2 Deliverables

1. **Fix commits** (TDD slices) on `swing-pipeline-pattern-detect-warnings-json-visibility-fix` branch:
   - One commit per step modified (primary fix at `_step_pattern_detect` + each additional step from the §1.2 audit that qualifies).
   - Each commit follows the TDD slice (failing test → minimal impl → commit).

2. **Discriminating tests** in `tests/pipeline/` (or similar) per §1.3.

3. **Findings document** at `docs/swing-pipeline-warnings-json-visibility-fix-findings-<DATE>.md`:
   - Per-step audit table (which steps modified; which left as-is; rationale per step).
   - Sample warnings_json payload for each step modified.
   - Pre-fix vs post-fix smoke comparison (if a verification pipeline run lands).

4. **Verification re-run** (optional; operator-paired): single pipeline run post-fix to confirm warnings_json populates correctly. Smoke artifact path documented.

5. **Return report** at `docs/swing-pipeline-warnings-json-visibility-fix-return-report.md`.

---

## §3 Watch items + cumulative discipline (BINDING)

### §3.1 Cumulative discipline

27 cumulative CLAUDE.md gotchas (1-27) BINDING for any 37th cumulative C.C lesson #6 validation if Codex invoked.

### §3.2 Process discipline

- **NO Co-Authored-By footer** — ~514+ cumulative streak through `92915c0`; preserve
- **`python -m swing.cli` from worktree cwd**, NOT bare `swing`
- **ASCII-only on runtime CLI paths + markdown narrative**
- **TDD per task** (each step modified gets its own discriminating-test slice)
- **Edit tool for per-file edits**

### §3.3 Schema discipline (LOCK)

Schema v21 LOCKED. Fix MUST NOT touch migrations. `warnings_json` is an existing column on `pipeline_runs`; just write to it.

### §3.4 L2 LOCK preservation (BINDING)

ZERO new Schwab API calls. Fix is in `swing/pipeline/` step orchestration; no integration calls.

### §3.5 V1 persisted state read-only EXCEPT pipeline_runs.warnings_json

Fix writes to `pipeline_runs.warnings_json` (the WHOLE POINT — making silent-skip visible). ZERO modification of `candidates` / `candidate_criteria` / `evaluation_runs` / `trades` / other V1 persisted state.

### §3.6 Production swing/ — APPROVED scope

Fix lands in `swing/pipeline/runner.py` (the early-return sites). ALLOWED. Other `swing/` directories MUST stay read-only.

---

## §4 NON-scope

- ZERO Option C (widen pool predicate; separate substantive dispatch)
- ZERO Option D (cohort-detection harness; separate V2 candidate dispatch)
- ZERO backfill of historical pipeline_runs warnings_json
- ZERO Phase 14 commissioning consideration
- ZERO schema migrations
- ZERO new Schwab API calls
- ZERO modification of V1 persisted state beyond `pipeline_runs.warnings_json` writes

---

## §5 Post-fix handback

When fix shipped:

1. Inline self-verification: ruff check; schema unchanged; ZERO new Schwab API calls; ZERO Co-Authored-By footer; V1 persisted state otherwise unchanged; TDD tests green.
2. Write findings document per §2.3.
3. Write return report per §2.5.
4. Hand back to operator with: per-step audit table; sample warnings_json payloads; pre-fix-vs-post-fix smoke comparison if verification re-run landed; total fix scope (line count + step count).

Orchestrator-side next steps post-handback:
- QA findings per `feedback_orchestrator_qa_implementer_product`
- Merge fix branch `--no-ff` to main; push
- Post-merge housekeeping (sub-event scale; in-place amendments)
- Option D dispatch sequencing (independent; can run in parallel or after Option A)

---

*End of pipeline-step silent-skip warnings_json visibility fix dispatch brief. Operator-approved production code change scoped to small operational hygiene improvement implementing CLAUDE.md gotcha #27. Mirrors investigation §6 banked Option A. ~514+ ZERO Co-Authored-By footer streak preserved through this brief commit.*
