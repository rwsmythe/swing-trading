# Phase 17 — 17-D.3: `review_log_cadence` swallows `LeaseRevokedError` (FIX-DIRECT)

**Audience:** A fresh Claude Code instance, no prior context. A one-line production fix + a coupled characterization-test flip. Known mechanism (CHARC-found, orchestrator-verified on disk); no investigation phase.

**Mission:** The pipeline's final auxiliary step (`review_log_cadence`, under the `complete` breadcrumb) is wrapped in a **bare `except Exception`** with no preceding `except LeaseRevokedError: raise`. Every other guarded step re-raises revoke first; this one swallows it → a `LeaseRevokedError` raised at the cadence step is eaten and the run proceeds to `lease.release(state="complete")` on a lease that was force-cleared mid-run. Make it behave like every other step.

**Expected duration:** ~20–30 min.

---

## §0 Read first
- [`swing/pipeline/runner.py`](../swing/pipeline/runner.py) **lines 1018–1029** — the `lease.step("complete")` block (the fix site). Note the `shadow_expectancy` block immediately above (L1002–1016) is the exact pattern to mirror: `except LeaseRevokedError: raise` THEN `except Exception as exc: log.warning(...)`.
- [`tests/pipeline/test_step_failure_characterization.py`](../tests/pipeline/test_step_failure_characterization.py) — the 17-B Phase-0 matrix. The `Site("review_log_cadence", ...)` entry (≈L112-114) currently sets `revoke_propagates=False` with the comment "bare except swallows it"; `test_planted_lease_revoked_propagation` (≈L264) is data-driven off `site.revoke_propagates` and its docstring + `else`-branch (≈L266-296) name review_log_cadence as the swallow exception.
- [`tests/pipeline/test_review_log_cadence_step.py`](../tests/pipeline/test_review_log_cadence_step.py) — verify nothing here pins the OLD swallow-on-revoke behavior (it shouldn't — it tests the cadence pre-create logic, not revoke handling — but confirm).
- 17-D.3 entry in [`docs/phase17-todo.md`](phase17-todo.md) — the full provenance + the cross-arc coupling note.

**Skill posture:** TDD. After the fix, a light standalone `copowers:review` (one-line behavior change + a test flip — minimal blast radius) to convergence; persist responses to a gitignored `.copowers-findings.md`. No brainstorm/writing-plans.

---

## §1 The coupling (governs the change — both land together)
17-B's characterization PINS review_log_cadence as the one site where revoke is swallowed (`Site(..., revoke_propagates=False, ...)`). This fix flips that fact, so the SAME change must update the characterization, or the suite goes red for the right reason in the wrong place. The data-driven `test_planted_lease_revoked_propagation` is the natural failing-test-first lever: flip the Site's `revoke_propagates` to `True` and the test now expects `state=="force_cleared"` for review_log_cadence — which FAILS against today's swallow-it code (it returns `state=="complete"`). That red → apply the runner fix → green is your TDD cycle.

## §2 The fix
**(a) `swing/pipeline/runner.py` (≈L1019-1025)** — add the re-raise before the bare except:
```python
lease.step("complete")
try:
    _step_review_log_cadence(lease=lease)
except LeaseRevokedError:
    raise
except Exception as exc:
    # Cadence pre-create is auxiliary — its failure must NOT roll back the
    # primary value chain (briefing emission). Log + continue. Brief §6.2
    # watch item 13. (17-D.3: revoke now propagates like every other step.)
    log.warning("review_log cadence step failed (continuing): %s", exc)
```
(`LeaseRevokedError` is already imported at runner.py top — confirm.)

**(b) `tests/pipeline/test_step_failure_characterization.py`** — flip the review_log_cadence `Site` field `revoke_propagates` from `False` → `True`, and update the now-stale prose: the inline `# revoke_propagates=False: bare except swallows it` comment, the `test_planted_lease_revoked_propagation` docstring (which lists review_log_cadence as an EXCEPT-this-site case alongside finviz_fetch_site1), and the `else`-branch comment. After the flip, review_log_cadence routes through the `if site.revoke_propagates:` branch (asserts `force_cleared`) automatically — confirm it's in `_REVOKE_SITES` so the parametrization actually exercises it.

**Do NOT:** refactor review_log_cadence to use `step_guard` (out of scope — minimal fix is the re-raise line); touch any other step; change the swallow-on-ordinary-Exception behavior (that stays — only revoke now propagates).

## §3 Binding conventions
- Conventional commit `fix(pipeline): 17-D.3 — re-raise LeaseRevokedError in review_log_cadence (stop swallowing revoke)`; NO `Co-Authored-By`, NO `--no-verify`, NO amend; `git log -1 --format='%(trailers)'` empty.
- TDD as in §1 (flip the assertion first, see the red, then fix). Fast suite `python -m pytest -m "not slow" -q` green on the merged head; ruff clean.
- Frozen-clock (R2): not applicable unless you add a NEW date-touching test (you shouldn't — reuse the existing characterization harness).

## §4 Done criteria + GATE
- The runner re-raise + the characterization flip land together; `test_planted_lease_revoked_propagation[review_log_cadence]` now asserts `force_cleared` and passes; the rest of the characterization matrix + `test_review_log_cadence_step.py` stay green; ruff clean; trailers `[]`.
- `copowers:review` converged (responses persisted).
- **Gate (pipeline smoke):** a real `swing pipeline run` (or the existing pipeline smoke/integration test) completes normally — the fix does not change the no-revoke happy path (the only behavior change is on a force-cleared lease, which the characterization test already exercises synthetically). Note for the operator: no UI/visual gate needed here; the smoke + the planted-revoke characterization test are the confidence.

## §5 Return report (final chat message ONLY)
Report: the commit SHA; the runner diff; the exact characterization edits (Site field + which comments/docstrings); confirmation `_REVOKE_SITES` includes review_log_cadence and the test now asserts force_cleared; the `copowers:review` verdict + persisted-findings path; the smoke result. Do NOT post to the mailbox or any director.
