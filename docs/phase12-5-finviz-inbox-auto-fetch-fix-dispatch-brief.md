# Phase 12.5 — Empty Finviz Inbox Auto-Fetch Fix — Dispatch Brief

**Audience:** Fresh Claude Code instance with no prior conversation context.

**Mission:** Close the pre-existing bug at `docs/phase3e-todo.md:940-958` (operator-reported 2026-05-15 during Phase 12 Sub-bundle A S5 gate; now 3rd gate-blocker occurrence at Phase 12.5 #1 S6 2026-05-18). On empty `data/finviz-inbox/` (common in fresh worktrees), `swing pipeline run` errors at `select_csv` with `NoFilesError` BEFORE `_step_finviz_fetch` has a chance to auto-populate the inbox via the Finviz Elite API. Fix: when `select_csv` raises `NoFilesError`, invoke `_step_finviz_fetch` inline + retry `select_csv` once; if retry still fails → fail with combined error message. Single-task polish dispatch.

**Expected duration:** ~1-2 hr implementation + ~30-60 min Codex (1-2 rounds expected; small surface). Total **~3-4 hr operator-paced**.

**Skill posture:** Invoke `copowers:executing-plans` with the inline acceptance below as the plan substrate (this brief IS the plan for a 1-task dispatch).

---

## §0 Bug anchor + scope

### §0.1 Pre-existing known bug

- **Source:** `docs/phase3e-todo.md` lines 940-958 (entry dated 2026-05-15; banked during Phase 12 Sub-bundle A S5 gate; not yet shipped).
- **Symptom:** `swing pipeline run` against an empty `data/finviz-inbox/` (folder exists per 2026-05-15 `6ea94f7` missing-folder fix but contains no CSV) errors with `No CSV files in <dir>` + state=failed. Should auto-trigger `_step_finviz_fetch` to populate the inbox + then proceed.
- **Operational impact:** has blocked Phase 12 Sub-bundle A S5 + Sub-bundle D + Phase 12.5 #1 S6 gates (3 occurrences). Every fresh-worktree gate involving `swing pipeline run` hits this.
- **Architectural root cause:** at `swing/pipeline/runner.py:run_pipeline_internal`, `select_csv(cfg.paths.finviz_inbox_dir)` runs at line 524 (BEFORE the pipeline step iteration). `_step_finviz_fetch` (which DOES auto-fetch via Finviz API) is invoked as a pipeline step at line 598 (AFTER `select_csv` has already errored). The architectural intent appears to have been "pipeline reads existing CSV from prior `swing finviz fetch` invocation" — but on first-run empty-inbox state, there's no prior CSV.

### §0.2 Fix specification

**File:** `swing/pipeline/runner.py`

**Site 1:** lines 524-528 (the existing `NoFilesError` / `AmbiguousInboxError` catch).

**Current code:**
```python
try:
    csv_path = select_csv(cfg.paths.finviz_inbox_dir)
except (NoFilesError, AmbiguousInboxError) as exc:
    log.error("Finviz inbox: %s", exc)
    lease.release(state="failed", error_message=str(exc))
    return RunResult(run_id=lease.run_id, state="failed", error_message=str(exc))
```

**Fix:** split the catch so `NoFilesError` triggers inline auto-fetch + retry; `AmbiguousInboxError` continues to fail-fast as before.

**Proposed shape** (implementer chooses exact form):
```python
finviz_fetched_inline = False
try:
    csv_path = select_csv(cfg.paths.finviz_inbox_dir)
except AmbiguousInboxError as exc:
    log.error("Finviz inbox: %s", exc)
    lease.release(state="failed", error_message=str(exc))
    return RunResult(run_id=lease.run_id, state="failed", error_message=str(exc))
except NoFilesError as exc_initial:
    log.info("Finviz inbox empty; attempting inline auto-fetch via _step_finviz_fetch")
    try:
        _step_finviz_fetch(cfg=cfg, lease=lease)
        finviz_fetched_inline = True
    except LeaseRevokedError:
        raise
    except Exception as exc_fetch:
        msg = f"inbox empty + auto-fetch failed: {type(exc_fetch).__name__}: {exc_fetch} (initial: {exc_initial})"
        log.error("Finviz inbox auto-fetch: %s", msg)
        lease.release(state="failed", error_message=msg)
        return RunResult(run_id=lease.run_id, state="failed", error_message=msg)
    try:
        csv_path = select_csv(cfg.paths.finviz_inbox_dir)
    except (NoFilesError, AmbiguousInboxError) as exc_retry:
        msg = f"inbox empty + auto-fetch did not produce a CSV: {exc_retry} (initial: {exc_initial})"
        log.error("Finviz inbox auto-fetch: %s", msg)
        lease.release(state="failed", error_message=msg)
        return RunResult(run_id=lease.run_id, state="failed", error_message=msg)
```

**Site 2:** lines 596-606 (the existing pipeline-step `_step_finviz_fetch` invocation). Skip the double-fire when `finviz_fetched_inline=True`:

```python
lease.step("finviz_fetch")
if finviz_fetched_inline:
    log.info("finviz_fetch step skipped (already ran inline pre-select_csv)")
else:
    try:
        _step_finviz_fetch(cfg=cfg, lease=lease)
    except LeaseRevokedError:
        raise
    except Exception as exc:
        log.warning("finviz_fetch programming error (continuing): %s", exc)
```

### §0.3 BINDING contracts

1. **`AmbiguousInboxError` catch stays fail-fast** — only `NoFilesError` triggers the inline retry. AmbiguousInboxError is operator's manual-override misconfiguration; auto-fetch wouldn't help.
2. **One inline auto-fetch attempt; no exponential retry** — if the inline `_step_finviz_fetch` fails OR retry still finds no CSV → fail with combined error message preserving both causes.
3. **No double-fire** — when inline auto-fetch fires, the pipeline-step `_step_finviz_fetch` at line 596+ MUST be skipped. Local flag `finviz_fetched_inline: bool` is the recommended mechanism.
4. **Lease semantics preserved** — `_step_finviz_fetch` already accepts `lease` kwarg + uses `lease.fenced_write()` for audit-row insert; same call signature for inline invocation. `lease.step("finviz_fetch")` at line 596 still fires (defense-in-depth lease-step tracking) even when the inner body skips.
5. **Audit-row contract** — when inline auto-fetch runs, exactly 1 `finviz_api_calls` audit row is written (by `_step_finviz_fetch`'s internal `with lease.fenced_write() as conn: insert_call(...)` at line 2143). The flag-based skip at site 2 ensures we don't write a 2nd row on the same pipeline run.
6. **No NEW Codex Major findings expected** — the fix is mechanical + bounded; surface area is ~30 LOC; pattern mirrors existing AmbiguousInboxError discipline.

### §0.4 Discriminating regression test

**File:** `tests/pipeline/test_run_pipeline_internal_empty_finviz_inbox_auto_fetch.py` (NEW)

**Pattern:**
1. Set up a tmp-path-based Config with empty `finviz_inbox_dir`.
2. Monkeypatch `_step_finviz_fetch` to write a known canonical 13-column CSV at `cfg.paths.finviz_inbox_dir / f"finviz{action_session_date_str}.csv"` (matches the actual `_finviz_fetch_core` output shape).
3. Invoke `run_pipeline_internal(cfg=cfg, trigger="test")`.
4. Assert:
   - Inline auto-fetch fired (monkeypatch call count >= 1).
   - CSV present in inbox post-call.
   - Pipeline state NOT "failed" on the empty-inbox cause (may still fail later on yfinance / Schwab / etc. — that's fine; this test asserts the empty-inbox cause is the SPECIFIC axis cleared).
   - `_step_finviz_fetch` pipeline-step body at site 2 was SKIPPED (only 1 invocation across the run).

**Defense-in-depth second test:** `test_run_pipeline_internal_empty_inbox_auto_fetch_also_fails_combined_error_message`:
1. Set up empty inbox.
2. Monkeypatch `_step_finviz_fetch` to RAISE (simulate Finviz API rate-limited or credentials missing).
3. Invoke `run_pipeline_internal`.
4. Assert state == "failed" + error_message contains both "auto-fetch failed:" AND the initial empty-inbox cause substring.

**Third test:** `test_run_pipeline_internal_ambiguous_inbox_still_fails_fast`:
1. Plant 2 CSVs in inbox (triggers `AmbiguousInboxError`).
2. Invoke `run_pipeline_internal`.
3. Assert state == "failed" + error_message contains the AmbiguousInboxError substring + `_step_finviz_fetch` was NOT invoked (no auto-fetch triggered on this error path).

### §0.5 Files touched (canonical roster)

| File | Lines | Action |
|---|---|---|
| `swing/pipeline/runner.py` | 524-528 (split catch) + 596-606 (double-fire skip) | MODIFY |
| `tests/pipeline/test_run_pipeline_internal_empty_finviz_inbox_auto_fetch.py` | NEW | CREATE |

**Surfaces explicitly NOT touched:**
- `_step_finviz_fetch` body (no signature change; no internal-skip-if-CSV-exists added — that broader-scope refactor is V2).
- `_finviz_fetch_core` body.
- `select_csv` / `NoFilesError` / `AmbiguousInboxError` in `swing/pipeline/finviz_select.py`.
- Lease / heartbeat / `_step_*` other pipeline steps.

---

## §1 Worktree + binding conventions

### §1.1 Worktree

- **Branch:** `phase12-5-finviz-inbox-auto-fetch-fix` (matches cleanup-script regex `phase\d+[-_]`).
- **Worktree directory:** `.worktrees/phase12-5-finviz-inbox-auto-fetch-fix/`
- **BASELINE_SHA:** current `main` HEAD (resolve via `git rev-parse main` at worktree-creation time; expected `d9ac13c` plus this brief commit).

### §1.2 Marker-file workflow

- After worktree creation: `New-Item -ItemType File c:\Users\rwsmy\swing-trading\.copowers-subagent-active`
- After fix lands + tests GREEN + before invoking adversarial-critic: `Remove-Item c:\Users\rwsmy\swing-trading\.copowers-subagent-active`

### §1.3 Commits

- Commit message stems:
  - `fix(pipeline): auto-fetch finviz CSV on empty-inbox NoFilesError (phase12-5-finviz-inbox-auto-fetch-fix)`
  - `fix(phase12-5-finviz-inbox-fix): Codex RN <severity> #N — <description>` for any Codex fixes
- **NO `Co-Authored-By` footer on ANY commit message.** ~112+ cumulative ZERO drift streak preserved across Phase 11/12/post-Phase-12/Phase-12.5-brainstorm/writing-plans/executing-plans chains. **DO NOT REGRESS.** The Bash tool's default footer template is NOT authoritative for this project — CLAUDE.md is.
- **NO `--no-verify`**, **NO `--amend`** (prefer `git add <specific-files>` over `git add -A`).
- **TDD:** failing test first → minimal implementation → pass → commit.

### §1.4 Verify command (PowerShell from inside worktree)

```powershell
git log --oneline HEAD~5..HEAD
python -m pytest -m "not slow" -q -n auto
python -m pytest tests/pipeline/test_run_pipeline_internal_empty_finviz_inbox_auto_fetch.py -v
ruff check swing/ --statistics
python -c "from swing.pipeline.runner import run_pipeline_internal; print('runner OK')"
```

---

## §2 Adversarial review (Codex)

Invoked automatically by `copowers:executing-plans` after task lands + tests GREEN + after pre-Codex orchestrator-side reviewer subagent pass (C.C lesson #6 — cheap; absorbs LOCK divergences pre-Codex).

**Expected chain shape:** 1-2 substantive Codex rounds. Small surface; well-scoped fix; pattern mirrors existing `AmbiguousInboxError` discipline.

**Adversarial review watch items:**
1. **Double-fire guard discipline** — `finviz_fetched_inline` flag flows correctly through to site 2; pipeline-step body skipped when flag True; `lease.step("finviz_fetch")` still fires for defense-in-depth lease tracking.
2. **Combined error message preserves both causes** — when inline auto-fetch fails, the final error_message includes BOTH the initial `NoFilesError` cause AND the auto-fetch failure cause (per `phase3e-todo:940` recommendation).
3. **`AmbiguousInboxError` stays fail-fast** — split-catch correctly routes only `NoFilesError` to the retry path; AmbiguousInboxError continues to fail without auto-fetch attempt.
4. **`LeaseRevokedError` propagation** — inner `try` around `_step_finviz_fetch(...)` re-raises `LeaseRevokedError` (matches existing pipeline-step handling at line 599-601).
5. **No regression in normal-case flow** — when inbox HAS a CSV at L524 entry, no behavioral change; `finviz_fetched_inline` stays False; pipeline-step body fires at site 2 as before.
6. **NO `Co-Authored-By` footer drift** — ~112+ cumulative ZERO drift; do NOT regress.

---

## §3 Operator-witnessed verification gate (2 surfaces)

| Surface | Type | Acceptance |
|---|---|---|
| **S1** | Inline `pytest -m "not slow" -q -n auto` + ruff | ALL fast tests pass (target baseline + 3 new tests = ~4708 fast). 4 pre-existing failures unchanged. Ruff 18 E501 unchanged. |
| **S2** | Empty-inbox pipeline run in fresh worktree | From the EXECUTING-PLANS worktree (which starts with empty `data/finviz-inbox/`): `python -m swing.cli pipeline run` → expect SUCCESS (or at minimum, failure NOT on `No CSV files` cause). Inspect: `data/finviz-inbox/` populated with today's `finviz<DD><Mmm><YYYY>.csv` post-call. |

**SKIPPED-with-test-coverage candidate:** S2 may be skipped if S1's 3 discriminating tests cover the auto-fetch invocation, double-fire skip, and combined-error-message paths. Operator preference.

---

## §4 OUT OF SCOPE (do not do)

- Modifying `_step_finviz_fetch` body or signature (V2 broader refactor; CAN bank skip-if-CSV-exists discipline for that).
- Modifying `_finviz_fetch_core` body or signature.
- Modifying `select_csv` / `NoFilesError` / `AmbiguousInboxError` in `swing/pipeline/finviz_select.py`.
- Adding exponential-backoff retry (single retry only; if the inline auto-fetch fails, fail-fast with combined error message).
- Adding a configurable `cfg.pipeline.auto_fetch_on_empty_inbox: bool` setting (out of scope; this is unconditional bug fix, not feature toggle).
- Refactoring the pipeline-step ordering (architectural change; out of scope for this 1-task polish).
- ANY behavioral change beyond the empty-inbox auto-fetch path.

---

## §5 Return report shape

After task lands + Codex chain converges + before final return-report commit, draft a return report at `docs/phase12-5-finviz-inbox-auto-fetch-fix-return-report.md` (mirroring Phase 12.5 #1 return-report shape, but smaller given 1-task scope):

1. Final HEAD on branch + commit count breakdown (1 task-impl + N Codex-fix + 1 return-report).
2. Codex round chain summary table.
3. Test count delta + ruff baseline unchanged + schema unchanged (v19).
4. Operator-witnessed verification surfaces (PENDING orchestrator-driven gate; 2 surfaces).
5. Per-task deviations from this brief (if any).
6. Codex Major findings ACCEPTED with rationale (target: ZERO).
7. CLAUDE.md status-line refresh draft text.
8. Composition-surface verification (`^def ` grep on `swing/pipeline/runner.py` near touched lines confirms no signature drift).
9. NEW phase3e-todo entry: mark the 940-958 entry as SHIPPED with this commit reference + remove from active backlog.

---

## §6 Dispatch metadata

- **Subagent type:** `general-purpose`.
- **Foreground vs background:** foreground.
- **Worktree:** YES — per §1.1.
- **Model:** defer to harness default.
- **Expected duration:** ~1-2 hr implementation + ~30-60 min Codex + 2-surface gate. Total **~3-4 hr operator-paced**.

---

## §7 If you get stuck

- If Codex pushes back on the double-fire guard (e.g., "just remove the pipeline-step `_step_finviz_fetch` invocation entirely"), HOLD THE LINE — the pipeline-step invocation at line 596+ is the canonical fetch in NORMAL operation (when inbox starts populated by a prior `swing finviz fetch` CLI invocation). Removing it would break the prior workflow.
- If Codex suggests refactoring `_step_finviz_fetch` to add internal skip-if-CSV-exists logic — defer to V2; out of scope per §4.
- If you encounter a need for schema change, STOP + escalate (no schema change expected for this fix).
- If the discriminating-test fixture setup proves complex (e.g., `_step_finviz_fetch` monkeypatch is tricky due to its dependence on `_finviz_fetch_core` + `lease.fenced_write()` + audit-insert flow), prefer monkeypatching at a higher level (e.g., monkeypatch `_finviz_fetch_core` to return a synthetic result dict + let `_step_finviz_fetch`'s real flow execute). Surface any monkeypatch-discipline questions as deviation in return report.
- DO NOT add `Co-Authored-By` footer to any commit message (per §1.3; ~112+ cumulative ZERO drift; CLAUDE.md governs).
- **Pre-Codex orchestrator-side review (NEW C.C lesson #6 — BINDING)**: before invoking `copowers:adversarial-critic`, dispatch a focused reviewer subagent with this brief's §0.3 BINDING contracts + §2 watch items as anchors; ask for a deviation list ≤300 words.

---

*End of brief. Single-task polish dispatch closing pre-existing `phase3e-todo:940-958` bug. Branch `phase12-5-finviz-inbox-auto-fetch-fix` matches cleanup-script regex. Schema unchanged (v19); ruff baseline 18 unchanged expected. Expected duration ~3-4 hr operator-paced including 2-surface gate.*
