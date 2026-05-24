# Phase 13 `_step_pattern_detect` Silent No-Op Triage — Investigation Dispatch Brief

**Audience:** Fresh Claude Code instance dispatched as the `_step_pattern_detect` silent no-op investigation implementer. No prior conversation context.

**Mission:** Root-cause why **`pattern_evaluations` table is EMPTY (0 rows)** despite **78 completed pipeline runs** since Phase 13 T2.SB3 detector landed. `_step_pattern_detect` is wired in the pipeline at `swing/pipeline/runner.py:842`, runs inside a broad `except Exception` (line 850-853; logs warning + continues), and silently produces zero output. Sibling Phase 13 tables ARE populated (`pipeline_pattern_classifications` 579 rows from the legacy single-class flag detector; `pipeline_chart_targets` 594 rows; `pattern_exemplars` 34 labeled rows across 5 classes). The 5-class Phase 13 detector is silently no-op'ing.

This investigation gates the operator's research question — "do Phase 13 detectors over-filter loosened-A+ candidates?" — which cannot be tested while `pattern_evaluations` is empty. Path A scope per orchestrator triage 2026-05-24 PM.

**Workflow:** `superpowers:systematic-debugging` skill (investigation; mirrors DK:62 + DHC/UCO/VSAT + full-reproduction investigation pattern). Adversarial Codex MCP review OPTIONAL — invoke only if a non-trivial code fix lands (>50 lines or a new architectural surface).

**Branch:** `applied-research-pattern-detect-step-silent-noop-triage` — branches from main HEAD `4e10450` (or later).

**Worktree:** `git worktree add .worktrees/applied-research-pattern-detect-step-silent-noop-triage applied-research-pattern-detect-step-silent-noop-triage`. Work from that cwd; invoke `python -m swing.cli` (NOT bare `swing`).

**Expected duration:** ~2-4 hours operator-paced. Diagnostic scope; small fix likely.

---

## §0 Read first (in this order)

1. **`swing/pipeline/runner.py:838-853`** — the pipeline step invocation site. Note the broad `except Exception` at line 850-853 that swallows all detector errors with only `log.warning` — no DB audit row. This is the silent-failure mode.

2. **`swing/pipeline/runner.py:1396+`** — `_step_pattern_detect` implementation. Walk the full function to identify all early-return conditions + all internal try/except blocks.

3. **`swing/pipeline/runner.py:1268-1395`** — `_pattern_detect_registry` + supporting helpers. Identifies WHICH detectors are registered + their interface contract.

4. **`swing/patterns/`** — individual detector modules. Walk each detector for assumptions about input shape, fixture requirements, threshold conditions, etc.

5. **`swing/data/migrations/0020_phase13_charts_patterns_autofill_usability.sql`** — `pattern_evaluations` schema (15 columns; pattern_class CHECK enum 5 values; FK pipeline_run_id ON DELETE CASCADE). Verify any NOT NULL columns the detector may be failing to populate.

6. **Prior-investigation precedents** for shape:
   - `docs/v2-dk62-criterion-drift-investigation-2026-05-23.md`
   - `docs/v2-dhc-uco-vsat-drift-investigation-2026-05-24.md`
   - `docs/v2-full-reproduction-drift-investigation-2026-05-24.md`

7. **CLAUDE.md** gotchas — especially:
   - Gotcha "Per-row failure isolation in pipeline step runners" (project precedent for best-effort step pattern)
   - Gotcha "yfinance / yfinance Ticker.history regressions" (silent-failure mode pattern; relevant if detector reads OHLCV)
   - Gotchas #21-23 (Phase 13 cumulative regression cascade family)

8. **Stage 2 reconnaissance script** at `tmp/stage2_detector_confirmation_query.py` — orchestrator-side query that surfaced this finding. The 67-candidate cohort is enumerated; the query confirms `pattern_evaluations` is empty.

---

## §1 Narrowed hypothesis space (6 candidates)

### §1.1 H1: Per-ticker exception swallowed inside `_step_pattern_detect`

The outer try/except at `runner.py:850-853` catches step-level exceptions, but `_step_pattern_detect` likely has its OWN per-ticker try/except inside (per the existing "Per-row failure isolation" CLAUDE.md gotcha). If EVERY ticker raises (e.g., signature mismatch with detector callable; missing dependency; bad fixture path), the per-ticker except logs + continues + the outer step completes "successfully" with zero rows written.

**Evidence to gather:**
- Run a pipeline step in isolation (one ticker; minimal candidate set) via `python -m swing.cli pipeline run` OR a direct invocation of `_step_pattern_detect` from a REPL with logging set to DEBUG.
- Capture per-ticker log output; identify the exception class + traceback.
- Check whether detector callables are imported correctly (e.g., `swing.patterns.<module>.detect()` signature matches expected).

**Falsification:** if a direct invocation produces at least one `pattern_evaluations` row, H1 ruled out.

### §1.2 H2: Config gate / feature flag disabled

`_step_pattern_detect` may have an early-return guard tied to `cfg.<some>.enabled = False` or similar. Pipeline runs with that flag false silently skip detector writes.

**Evidence to gather:**
- Grep `_step_pattern_detect` body for any `if not cfg.X:` / `if not enabled:` / `return` early-exit pattern.
- Check `swing/config.py` for any `patterns.detect_enabled` / `phase13.enabled` / etc. cfg field with default `False`.
- Inspect operator's `~/swing-data/user-config.toml` for any pattern-detection-disabling override.

**Falsification:** if no config gate exists OR config gate is True, H2 ruled out.

### §1.3 H3: Min-exemplars-per-class threshold not met

The 5 detector classes require labeled exemplars for template matching (Phase 13 T2.SB5 template matching shipped). Current state: vcp 17, cup_with_handle 6, flat_base 4, high_tight_flag 4, double_bottom_w 3. If the detector requires e.g., 5+ exemplars per class, the underrepresented classes (flat_base, high_tight_flag, double_bottom_w) would fail to run — and a strict "all-or-nothing" failure mode would cause the entire step to no-op.

**Evidence to gather:**
- Grep `swing/patterns/` for any `min_exemplars` / `MIN_EXEMPLARS_PER_CLASS` / similar threshold constant.
- Check template-matching code path (`swing/patterns/template_matching.py` or similar) for empty-exemplar-class guards.
- Cross-reference exemplar counts per class against any documented minimum.

**Falsification:** if no per-class minimum threshold exists OR all 5 classes have ≥ threshold exemplars, H3 ruled out.

### §1.4 H4: Detector version mismatch with schema CHECK enum

`pattern_evaluations.pattern_class` has a 5-value CHECK enum. `detector_version` is a free-text column. If the detector emits a `pattern_class` value outside the CHECK enum (e.g., 'none' from the legacy classifier code path being reused), the INSERT raises CHECK violation, caught by per-ticker except, logged + lost.

**Evidence to gather:**
- Grep `swing/patterns/` + `swing/pipeline/runner.py` for the actual pattern_class values being emitted (look for return values / dataclass field assignments).
- Check whether the legacy `pipeline_pattern_classifications.pattern` value 'none' (per Stage 2 sample) is leaking into the new pattern_evaluations write path.

**Falsification:** if emitted pattern_class values are all in {'vcp', 'flat_base', 'cup_with_handle', 'high_tight_flag', 'double_bottom_w'}, H4 ruled out.

### §1.5 H5: Outer-step exception swallowed with no audit (operational + diagnostic gap)

`runner.py:850-853` is the canonical "best-effort" pattern shape, but the failure ARTIFACT is only `log.warning` (stderr). There's no `pipeline_step_audits` table; no `pattern_detect_status` column on `pipeline_runs`. Even if a non-silent exception fires, it leaves no DB trace.

This is partly a diagnostic limitation (we can't reconstruct what failed from the DB) and partly a contributing cause (the silent failure mode is invisible to operator monitoring).

**Evidence to gather:**
- Check pipeline_runs.warnings_json for any pattern_detect warnings (orchestrator already searched — none found, but verify against more runs).
- Look for any stderr/stdout log files the pipeline writes (`swing-data/logs/` or similar).

**Falsification:** if log files reveal exceptions per run, H5 is the CONTRIBUTING cause; root cause is identified at H1-H4.

### §1.6 H6: Detector requires OHLCV data not available / cached at run time

Phase 13 detectors operate on OHLCV bars. If they read via a different code path than the standard `swing/data/ohlcv_archive.py` OR have a min-bar-count requirement higher than what's cached, the detector may silently fail per-ticker.

**Evidence to gather:**
- Check detector OHLCV read path; verify cache coverage at typical pipeline run asof_dates.
- Look for any min-bar-count guards (`if len(bars) < N: return None`).

**Falsification:** if detectors successfully read OHLCV in a direct invocation test, H6 ruled out.

### §1.7 Decisive counter-test (MUST run regardless of which hypothesis falsifies)

**Direct invocation reproducer:** invoke `_step_pattern_detect` (or its key callees) from a Python REPL OR a one-off script in `tmp/` with logging set to DEBUG, against a known recent eval_run (e.g., eval_run_id=64 = most recent). Capture:
- Number of detectors invoked.
- Number of tickers iterated.
- Per-ticker outcome (success / exception class / no-op).
- Pre-INSERT pattern_evaluations row count vs post-INSERT count.

If the reproducer writes at least 1 pattern_evaluations row → the pipeline-time invocation has a wiring bug. If it writes 0 → the detector itself is the bug. Bisects code path vs detector code.

---

## §2 Investigation surface — root cause pinpoint

After identifying the root cause hypothesis-bucket, walk the specific code path:

1. Identify the EXACT line where execution silently exits OR the exception is raised.
2. Verify the failure mode against pre-existing CLAUDE.md gotchas (does this match a known anti-pattern?).
3. If H5 (operational gap) is confirmed as CONTRIBUTING, propose a minimal logging/audit improvement (e.g., write pattern_detect outcome to `pipeline_runs.warnings_json` per the existing precedent for other steps).

---

## §3 Deliverables

1. **Investigation findings document** at `docs/phase13-pattern-detect-step-silent-noop-investigation-<DATE>.md`:
   - Per-hypothesis evidence summary (H1-H6).
   - Root cause identification with code:line citation.
   - Decisive counter-test reproducer result.
   - Drift class characterization (per-ticker failure vs whole-step failure).
   - Remediation recommendation.
   - Operational-gap diagnostic findings (logging/audit improvements for future detection).

2. **Optional V1 production code fix** if the bug is small + safely scoped:
   - Allowed: `swing/patterns/<module>.py` or `swing/pipeline/runner.py` _step_pattern_detect modifications IF the fix is < 30 lines + has TDD discriminating tests + preserves all existing invariants.
   - PRODUCTION-CODE-CHANGE LOCK preserved by requesting OPERATOR approval BEFORE shipping (small fix; not a research-branch one-off). Implementer documents proposed fix in findings + return report; OPERATOR ratifies via orchestrator before merge.
   - Disallowed: schema migrations, large refactors, changes to other pipeline steps, V1 persisted-state mutations.

3. **Verification re-run** (if fix lands): operator-paired single pipeline run to confirm `pattern_evaluations` populates correctly post-fix. Capture row count + sample rows. Smoke artifact at `exports/diagnostics/pattern-detect-step-postfix-<ISO>.md`.

4. **Return report** at `docs/phase13-pattern-detect-step-silent-noop-investigation-return-report.md`.

---

## §4 Watch items + cumulative discipline (BINDING)

### §4.1 Cumulative discipline

If code fix lands AND Codex review is invoked, ALL 26 CLAUDE.md cumulative gotchas (1-26) BINDING for any 37th cumulative C.C lesson #6 validation.

### §4.2 Process discipline

- **NO Co-Authored-By footer** — ~511+ cumulative streak through `4e10450`; preserve
- **`python -m swing.cli` from worktree cwd**, NOT bare `swing`
- **ASCII-only on runtime CLI paths** + markdown narrative
- **TDD per task** if code changes land
- **Edit tool for per-file edits**

### §4.3 Schema discipline (LOCK)

Schema v21 LOCKED. Investigation MUST NOT touch migrations.

### §4.4 L2 LOCK preservation (BINDING)

ZERO new Schwab API calls. Detectors may read OHLCV via `swing/data/ohlcv_archive.py` (V1 read path; L2 LOCK irrelevant for production code; only V2 research code is L2-locked from yfinance/schwab imports).

### §4.5 Read-only invariant for V1 persisted state — RELAXED for pattern_evaluations write path

This investigation MAY result in writes to `pattern_evaluations` if a fix lands + a verification pipeline run is invoked. That's the WHOLE POINT — `pattern_evaluations` was supposed to be populated and isn't. ZERO modification of `candidate_criteria` / `candidates` / `evaluation_runs` / `trades` / other V1 persisted state.

### §4.6 Production swing/ — RELAXED if small fix is proposed

If H1-H4 root cause requires a small production code fix (<30 lines) in `swing/patterns/` or `swing/pipeline/runner.py:_step_pattern_detect`, the investigation MAY produce such a fix. **OPERATOR APPROVAL REQUIRED before merging the production code change** — the implementer documents the proposed fix in findings + return report; orchestrator-paired ratification happens during QA.

If H5 (operational gap; logging/audit improvement) is the proposed scope, that's also a small production code change — same operator-approval gate.

If the fix is non-trivial (>30 lines OR architectural surface change), the investigation stops at findings + return report; a SEPARATE dispatch lands the fix.

### §4.7 Backfill consideration (NON-scope)

If the fix lands + `pattern_evaluations` populates correctly going forward, BACKFILLING the 78 historical pipeline runs is OUT OF SCOPE for this investigation. Banked V2 candidate for separate dispatch (would require re-evaluating all historical eval_runs against current detector state; significant scope; possibly L4-style temporal-mutation considerations).

---

## §5 Pre-investigation context (Stage 2 reconnaissance findings)

- **`pattern_evaluations` row count**: 0
- **`pipeline_runs` count**: 78 (most recent: id=78, 2026-05-22 21:36:12 complete, all visible step statuses 'ok')
- **`pipeline_pattern_classifications` (legacy single-class flag detector)**: 579 rows — IS WRITING
- **`pipeline_chart_targets`**: 594 rows — IS WRITING
- **`pattern_exemplars` (labeled training data)**: 34 rows across 5 classes (vcp 17 / cup_with_handle 6 / flat_base 4 / high_tight_flag 4 / double_bottom_w 3)
- **schema_version**: 21
- **DB path**: `%USERPROFILE%/swing-data/swing.db`
- **No `pipeline_step_audits` table exists**; no `pattern_detect_status` column on `pipeline_runs`; failure mode is silent + invisible to DB inspection.

The legacy classifier (`pipeline_pattern_classifications`) writes successfully across 78 runs; the new 5-class detector (`pattern_evaluations`) writes ZERO rows. The failure is isolated to the NEW detector + does not affect other Phase 13 pipeline steps.

---

## §6 NON-scope

- ZERO Phase 14 commissioning consideration (DEFERRED per Path B sequencing)
- ZERO backfill of historical pipeline_evaluations rows (banked V2 candidate)
- ZERO schema migrations (schema v21 LOCKED)
- ZERO modification of `candidate_criteria` / `candidates` / `evaluation_runs` / `trades` / V1 persisted state beyond `pattern_evaluations` write (the latter is the WHOLE POINT)
- ZERO refactor of `_step_pattern_detect` architecture beyond the minimal fix
- ZERO changes to the legacy `pipeline_pattern_classifications` write path (it's working; don't touch)
- ZERO new Schwab API calls
- ZERO operator-paired V2.5/V3 architectural decisions (immutable archive snapshot; new detector classes; etc.)

---

## §7 Post-investigation handback

When investigation findings + remediation are documented:

1. Write findings document at `docs/phase13-pattern-detect-step-silent-noop-investigation-<DATE>.md` per §3.1
2. Write return report at `docs/phase13-pattern-detect-step-silent-noop-investigation-return-report.md` per §3.4
3. If a fix is proposed: document the proposed fix in findings + return report + AWAIT operator approval BEFORE merging the production code change
4. If a fix lands + verification re-run succeeds: capture post-fix smoke artifact + commit alongside the fix
5. Inline self-verification: ruff check (if code changes); schema unchanged; ZERO new Schwab API calls; ZERO Co-Authored-By footer; V1 persisted state otherwise unchanged
6. Hand back to operator with: root cause + code:line citation; remediation recommendation (proposed fix code if small; OR separate dispatch if non-trivial); operational-gap diagnostic findings; backfill consideration enumeration.

Orchestrator-side next steps post-handback:
- QA findings per `feedback_orchestrator_qa_implementer_product`
- If a fix landed + operator-approved: merge investigation branch `--no-ff` to main; push
- If a fix is proposed but not yet shipped: surface to operator for approval; if approved, ship via inline edit OR new mini dispatch
- Post-merge housekeeping (sub-event scale; in-place amendments; NEW gotcha if a discipline gap is surfaced — likely YES given the silent-failure-without-audit pattern is itself a banked-class gotcha candidate)
- Operator-paired decision on backfill (separate dispatch) + return to Stage 2 detector-confirmation query with fresh data

---

*End of Phase 13 `_step_pattern_detect` silent no-op triage dispatch brief. Investigation scope only by default; production code fix conditionally allowed if small + operator-approved. Root-causes why `pattern_evaluations` has zero rows after 78 pipeline runs. Unblocks Stage 2 detector-confirmation query for the +75 cohort (operator's earlier hypothesis on pattern-detector over-filtering). ~511+ ZERO Co-Authored-By footer streak preserved through this brief commit. Investigation gates the V2 sensitivity arc's third research stage (AI second-opinion on winners-without-detection cell; deferred until detector produces data).*
