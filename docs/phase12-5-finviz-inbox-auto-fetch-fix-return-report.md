# Phase 12.5 Empty Finviz Inbox Auto-Fetch Fix — Return Report

**Branch:** `phase12-5-finviz-inbox-auto-fetch-fix`
**Final HEAD:** `f7ee069`
**Baseline:** `379a675` (main HEAD at dispatch time)
**Dispatch brief:** `docs/phase12-5-finviz-inbox-auto-fetch-fix-dispatch-brief.md`

---

## §1 Final HEAD + commit breakdown

| SHA | Author-classification | Summary |
|---|---|---|
| `400bee7` | Task implementation | Site-1 split catch + Site-2 double-fire skip + 3 new discriminating tests + 1 pre-existing test update |
| `85ebe22` | Codex R1 fix bundle (Major #1 + #2 + #3) | Diagnostic enrichment helper + audit-row contract test + early `lease.step("finviz_fetch")` |
| `bc4b458` | Codex R2 fix bundle (Major #1 + Minor #2) | Causal-scope diagnostic via `MAX(call_id)` snapshot + 512-char fetch_err cap + causal-scoping discriminating test |
| `f7ee069` | Codex R3 polish (Minor #2) | Newline/CR normalization in embedded audit error text |

**Total:** 4 commits = 1 task-impl + 3 Codex-fix.
**Co-Authored-By footer drift:** **ZERO across all 4 commits** (verified via `git log | grep -i co-authored` → no matches). Maintains the project's ~112+ commit cumulative ZERO-drift streak.

---

## §2 Codex round chain summary

| Round | Critical | Major | Minor | Verdict | Outcome |
|---|---|---|---|---|---|
| R1 | 0 | 3 | 2 | ISSUES_FOUND | All 3 Major resolved in-tree; both Minor banked as accepted-with-rationale (stale-CSV out of scope per brief §4; comment verbosity is project convention) |
| R2 | 0 | 1 | 2 | ISSUES_FOUND | 1 Major resolved (causal-scope diagnostic); Minor #1 wording fixed in-tree; Minor #2 partially resolved (defensive 512-char cap; full token-redaction out of scope — Finviz wrapper classes already bound) |
| R3 | 0 | 0 | 2 | **NO_NEW_CRITICAL_MAJOR** | Minor #1 banked as no-op (already correctly handled by `_read_finviz_call_max_id_snapshot` empty-table→0 path + exercised by existing test); Minor #2 resolved in-tree (CR/LF normalization) |

**Total Codex rounds:** **3** (within brief's projected 1-2; over by 1 round driven by R1 Major #2 audit-row contract test gap + R2 Major #1 multi-surface concurrency causal-tie).

**Convergent monotonic-Major taper:** 3 → 1 → 0 (clean shape; no R3 surface bump above R2).

**ZERO Critical findings entire chain.**

---

## §3 Test count delta + ruff baseline + schema baseline

| Metric | Baseline | Final | Delta |
|---|---|---|---|
| Fast tests passing | 4575 | **4581** | **+6** (3 brief-locked + 1 audit-row pin + 1 silent-error diagnostic + 1 causal-scoping) |
| Pre-existing failures | 3 (phase8 walkthrough) | 3 | unchanged |
| Skipped | 5 | 5 | unchanged |
| Ruff E501 | 18 | 18 | unchanged |
| Schema version | v19 | v19 | unchanged |

**Test overshoot from brief projection (+3 → actual +6):** driven by Codex R1 Major #2 + R2 Major #1 adding 2 new discriminating tests that were not in the brief's §0.4 roster. Each is a brief-derived pin (audit-row contract per brief §0.3 #5; causal-scoping covers a multi-surface concurrency hole not in the brief's adversarial-watch §2 list).

---

## §4 Operator-witnessed verification surfaces (orchestrator-driven gate — PENDING)

Brief §3 enumerated 2 surfaces. Recommend orchestrator-driven gate post-merge:

| Surface | Type | Acceptance per brief |
|---|---|---|
| **S1** | Inline `pytest -m "not slow" -q -n auto` + ruff | ALL fast tests pass (4581 target = 4575 baseline + 6 new). 3 pre-existing phase8 walkthrough failures unchanged. Ruff 18 E501 unchanged. |
| **S2** | Empty-inbox pipeline run in fresh worktree | From this worktree (which starts with empty `data/finviz-inbox/`): `python -m swing.cli pipeline run` → expect SUCCESS (or at minimum, failure NOT on `No CSV files` cause). Inspect: `data/finviz-inbox/` populated with today's `finviz<DD><Mmm><YYYY>.csv` post-call + `finviz_api_calls` table shows exactly 1 fresh audit row. |

**S2 SKIPPED-with-test-coverage candidate** (brief §3): the 5 discriminating tests at `tests/pipeline/test_run_pipeline_internal_empty_finviz_inbox_auto_fetch.py` cover the auto-fetch invocation (test 1), double-fire skip (test 1 invocation_count==1), combined-error-message paths (tests 2 + 5), audit-row contract (test 4), causal-scope diagnostic (test 5). Plus `tests/pipeline/test_runner_inbox_bootstrap.py` continues to cover the dir-bootstrap regression path.

---

## §5 Per-task deviations from brief

1. **DEVIATION (§0.5 file roster)** — `tests/pipeline/test_runner_inbox_bootstrap.py` modified. **Necessity:** post-fix this pre-existing test's `state='failed'` + `"no csv files"` assertions stop holding because the new auto-fetch retry path consumes the operator's REAL Finviz token leaked through `apply_overrides` + `USERPROFILE` pollution → pipeline ran end-to-end against real API → state='complete'. Resolved by monkeypatching `_step_finviz_fetch` to raise (preserves test's original mkdir-on-first-run regression coverage; brief §7 explicitly mentions this monkeypatch pattern as a "If you get stuck" hint). Banked.

2. **DEVIATION (§0.4 test roster — 3 cases brief-locked; shipped 5 cases)** — added 2 additional discriminating tests beyond the brief-locked 3:
   - `test_empty_inbox_inline_auto_fetch_writes_exactly_one_audit_row` (Codex R1 Major #2 — pins brief §0.3 contract #5 verbatim by monkeypatching `_finviz_fetch_core` instead of `_step_finviz_fetch` so the real audit-row insert path runs end-to-end).
   - `test_empty_inbox_silent_fetch_error_surfaces_audit_detail_in_combined_message` (Codex R1 Major #1 — pins the diagnostic-enrichment behavior where `_step_finviz_fetch` returns silently with status='error').
   - `test_empty_inbox_diagnostic_is_causally_scoped_to_this_pipeline_call` (Codex R2 Major #1 — pins multi-surface concurrency causal-tie via `MAX(call_id)` snapshot scoping).

3. **DEVIATION (§0.2 surface area: ~30 LOC vs actual ~+115 LOC code + ~+440 LOC tests)** — driven by Codex R1 + R2 adding 2 new module-level helpers (`_read_latest_finviz_call_diagnostic` + `_read_finviz_call_max_id_snapshot`) + diagnostic enrichment threading at the retry-failed catch path + 2 new ~100-line discriminating tests. Brief's "~30 LOC" estimate was for the minimal split-catch shape only; the Codex chain expanded scope through 3 binding-contract gaps.

4. **DEVIATION (§2 adversarial watch list missed 2 axes)** — brief §2's 6-item watch list did not enumerate: (a) audit-row contract verification via lower-level monkeypatch pattern (R1 M#2); (b) multi-surface concurrency causal-tie for diagnostic reads (R2 M#1). Both surfaced during Codex chain; both resolved in-tree with discriminating tests.

5. **NO DEVIATION** on §0.3 BINDING contracts (all 6 honored verbatim per pre-Codex orchestrator-side reviewer + Codex R1/R2/R3 verification).

---

## §6 Codex Major findings ACCEPTED with rationale

**TARGET: ZERO. ACTUAL: ZERO.**

All 4 Critical+Major findings across 3 Codex rounds (0 Critical + 4 Major = R1 #1, #2, #3 + R2 #1) resolved with code-content fixes + discriminating regression tests. ZERO ACCEPT-WITH-RATIONALE positions banked. Matches the project's recent clean-record precedent (Phase 12 Sub-bundle C.D + post-Phase-12 Sub-bundle 1 + Sub-bundle 1.5 + Sub-bundle 2 + Phase 12.5 #1 brainstorm + writing-plans).

---

## §7 CLAUDE.md status-line refresh draft text

Append to CLAUDE.md status line:

> **Phase 12.5 #1 finviz-inbox-auto-fetch-fix SHIPPED 2026-05-18** at `<integration-merge-sha>` (integration merge of `phase12-5-finviz-inbox-auto-fetch-fix` via `--no-ff`; 4 commits = 1 task-impl + 3 Codex-fix; **3 Codex rounds → NO_NEW_CRITICAL_MAJOR** convergent monotonic-Major taper (R1 0C/3M/2m → R2 0C/1M/2m → R3 0C/0M/2m); **ZERO ACCEPT-WITH-RATIONALE banked** — all 4 Major resolved with code-content fixes (matches Phase 12 Sub-bundle C.D + post-Phase-12 Sub-bundle 1/2 + Phase 12.5 #1 brainstorm/writing-plans clean-record precedent); ZERO Co-Authored-By footer drift across 4 commits (~116+ arc-cumulative); **+6 fast tests** (4575 → 4581); ruff 18 unchanged; schema v19 unchanged; closes pre-existing bug `docs/phase3e-todo.md:940-958` (3rd gate-blocker occurrence). Site-1 (`swing/pipeline/runner.py:524`): split combined NoFilesError/AmbiguousInboxError catch so NoFilesError triggers ONE inline `_step_finviz_fetch` attempt + retry; AmbiguousInboxError stays fail-fast. Site-2 (line 596+): gated on `not finviz_fetched_inline` to avoid double-fire (would persist 2 `finviz_api_calls` audit rows per run). **2 new helpers** at runner.py: `_read_finviz_call_max_id_snapshot(cfg)` (captures `MAX(call_id)` before inline call; returns 0 for empty-table case, None on read failure) + `_read_latest_finviz_call_diagnostic(cfg, *, after_call_id)` (scoped read of FIRST row inserted AFTER snapshot; surfaces silent-status='error' returns from `_finviz_fetch_core` in retry-failed combined message). **5 new discriminating tests** at `tests/pipeline/test_run_pipeline_internal_empty_finviz_inbox_auto_fetch.py` (3 brief-locked + 2 Codex-surfaced for audit-row contract + causal-scope). **1 pre-existing test update** at `tests/pipeline/test_runner_inbox_bootstrap.py` monkeypatches `_step_finviz_fetch` to raise (prevents operator's real Finviz token leakage via `apply_overrides` + `USERPROFILE` pollution from making a live API call during fast-suite test; preserves original mkdir-bootstrap regression coverage).

---

## §8 Composition-surface verification

Grep on `^def ` definitions in `swing/pipeline/runner.py` confirms NO signature drift:

```
$ grep -n "^def " swing/pipeline/runner.py | head -20
457:def run_pipeline_internal(*, cfg: Config, trigger: str) -> RunResult:
1849:def _finviz_fetch_core(cfg) -> dict:
1933:def _read_finviz_call_max_id_snapshot(cfg) -> int | None:    # NEW
1962:def _read_latest_finviz_call_diagnostic(cfg, *, after_call_id: int | None) -> tuple[str | None, str | None]:    # NEW
2008:def _finviz_cleanup_stale_shadows(inbox_dir: Path) -> None:
2023:def _assert_no_active_pipeline_run(conn: sqlite3.Connection) -> None:
2042:def _step_finviz_fetch(*, cfg, lease) -> None:    # UNCHANGED signature
2109:def _perform_finviz_fetch_no_lease(*, cfg, conn: sqlite3.Connection) -> None:    # UNCHANGED signature
```

`_step_finviz_fetch(*, cfg, lease)` signature preserved verbatim per brief §4 OUT OF SCOPE. `_finviz_fetch_core(cfg) -> dict` signature preserved. `run_pipeline_internal(*, cfg, trigger) -> RunResult` signature preserved. Only ADDITIONS to module-level surface: 2 new private helpers (`_read_finviz_call_max_id_snapshot` + `_read_latest_finviz_call_diagnostic`).

Import smoke: `python -c "from swing.pipeline.runner import run_pipeline_internal, _read_latest_finviz_call_diagnostic, _read_finviz_call_max_id_snapshot; print('OK')"` → `OK`.

---

## §9 NEW phase3e-todo entry: mark 940-958 as SHIPPED

The pre-existing `docs/phase3e-todo.md:940-958` entry that this dispatch closed is now SHIPPED. Recommended `docs/phase3e-todo.md` action post-merge:

1. Move the 940-958 entry from the active backlog section to the archive companion file `docs/phase3e-todo-archive.md` (per CLAUDE.md retention discipline §"Maintenance: retention discipline").
2. Add a SHIPPED-marker line referencing this dispatch's integration-merge SHA + the new commit chain HEAD `f7ee069`.

Suggested archive-section entry:

> **SHIPPED 2026-05-18** at `<integration-merge-sha>` (HEAD `f7ee069` on branch `phase12-5-finviz-inbox-auto-fetch-fix`): empty-inbox NoFilesError now triggers ONE inline `_step_finviz_fetch` retry at `swing/pipeline/runner.py:524`; combined error message preserves both initial NoFilesError cause + diagnostic-enriched audit-row status/error_message when retry fails. AmbiguousInboxError stays fail-fast. 4 commits = 1 task-impl + 3 Codex-fix; 3 Codex rounds → NO_NEW_CRITICAL_MAJOR; +6 fast tests; ruff 18 unchanged; schema v19 unchanged. Closes 3rd gate-blocker occurrence (Phase 12 Sub-bundle A S5 + Sub-bundle D + Phase 12.5 #1 S6).

---

## §10 Forward-binding lessons for future dispatches

1. **Brief §0.4 test roster should include the audit-row contract pattern when contract #5 binds.** Brief §0.3 #5 ("exactly 1 finviz_api_calls audit row when inline fires") was not surfaced as a discriminating test in §0.4 — the brief's 3 tests all monkeypatch `_step_finviz_fetch` ENTIRELY which bypasses the audit-row insert path. Future dispatches where a contract binds a low-level invariant should enumerate a discriminating test that exercises the REAL code path (monkeypatch at the lower-level helper, not the wrapper). C.C lesson #6 pre-Codex orchestrator-side review didn't catch this — the pre-Codex reviewer also accepted the brief-roster at face value. Mitigation candidate: pre-Codex review checklist should include "for each binding contract X, verify at least one discriminating test that does NOT depend solely on monkeypatching the function-under-test."

2. **"Read latest" helpers in multi-surface concurrent code must scope by causal anchor (PK snapshot), not global ORDER BY.** Codex R2 M#1 caught the `list_recent_calls(limit=1)` misattribution risk. Pattern: capture an `id`-class snapshot BEFORE the operation that inserts; scope subsequent reads to `WHERE id > <snapshot>`. Applies to any future read-latest-row-after-operation surface (Schwab audit row reads; reconciliation_corrections lookups; cash_movements after fill insert). Forward-binding rule: any helper named `_read_latest_*` triggers an automatic adversarial-watch item for "is this scoped to THIS operation or to globally-latest?"

3. **Operator's real `USERPROFILE`/`HOME` env var pollution leaks into fast-suite tests via `apply_overrides`'s cfg-cascade.** Existing CLAUDE.md gotcha ("Tests that exercise `swing/config_user.py:write_user_overrides` MUST monkeypatch BOTH `USERPROFILE` AND `HOME`") covers writes; this dispatch surfaced the symmetric READ-side hazard — `apply_overrides(cfg)` reads from `_user_home()` at every pipeline invocation. Pre-existing test `test_runner_inbox_bootstrap.py` started failing post-fix because the operator's REAL Finviz token leaked through. Fix: monkeypatch `_step_finviz_fetch` to raise (test's intent preserved). Forward-binding rule for future fast-suite tests touching `apply_overrides`-consuming code paths: either monkeypatch the leaking integration entry point OR monkeypatch `USERPROFILE` + `HOME` to tmp paths.

---

*End of return report. Single-task polish dispatch closing pre-existing `phase3e-todo:940-958` bug. Branch ready for operator-witnessed gate (S1+S2) + integration merge to main. Worktree husk at `.worktrees/phase12-5-finviz-inbox-auto-fetch-fix/` matches cleanup-script regex `phase\d+[-_]` — pending operator's cleanup-script `-DeregisterFirst` pass.*
