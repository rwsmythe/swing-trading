# Return Report - Phase 13 `_step_pattern_detect` Silent No-Op Triage Investigation

**Branch:** `applied-research-pattern-detect-step-silent-noop-triage`
**Worktree HEAD at start:** main `eb48729`
**Investigator:** Implementer (dispatched per `docs/phase13-pattern-detect-step-silent-noop-triage-dispatch-brief.md`)
**Date:** 2026-05-24
**Outcome:** **DIAGNOSTIC-ONLY ship**. Root cause identified; remediation options enumerated; no production code change committed. Operator-paired decision required on Options A/B/C/D (see findings doc §5).

---

## 1. Headline result

**Root cause: empty-pool early-return** at [`swing/pipeline/runner.py:1485-1490`](../swing/pipeline/runner.py#L1485-L1490). The pool predicate `bucket = 'aplus'` matches **zero candidates in 7/7 pipeline runs since T2.SB3 shipped 2026-05-20**. The step is operating per spec. Detector code is fully functional (decisive counter-test reproducer 2 shows `BULZ.high_tight_flag = 0.667` on a watch-bucket ticker). Brief's framing of "78 runs since T2.SB3 landed" was inaccurate - only 7 are post-ship.

Findings doc at [`docs/phase13-pattern-detect-step-silent-noop-investigation-2026-05-24.md`](phase13-pattern-detect-step-silent-noop-investigation-2026-05-24.md).

---

## 2. Hypothesis disposition vs brief §1

| Hyp | Brief framing | Disposition | Evidence section |
|:---:|:---|:---|:---|
| H1 | per-ticker exception swallowed | FALSIFIED | findings §1.1 |
| H2 | config gate disabled | FALSIFIED | findings §1.2 |
| H3 | min-exemplars-per-class threshold | FALSIFIED | findings §1.3 |
| H4 | pattern_class CHECK enum mismatch | FALSIFIED | findings §1.4 |
| H5 | outer exception swallowed with no audit | **CONFIRMED as CONTRIBUTING** | findings §1.5 + §4.1 |
| H6 | detector OHLCV / min-bar-count | FALSIFIED | findings §1.6 |
| **H7** (NEW per superpowers Phase 1.4 evidence-expansion) | pool predicate over-restricts; current candidate distribution has zero aplus | **CONFIRMED ROOT CAUSE** | findings §1.7 + §2 |

---

## 3. Remediation options enumerated for operator (findings §5)

| Opt | Scope | Behavioral change | Operator-approval gate | Recommendation |
|:---:|:---|:---|:---:|:---|
| **A** | ~10-15 line `warnings_json` audit write on empty-pool skip | NONE (operational visibility only) | YES (this dispatch) | **DEFAULT** |
| **B** | findings-only; defer fix | NONE | N/A | Acceptable; risks gotcha-class recurrence |
| **C** | widen pool predicate `bucket IN ('aplus','watch')` | YES (~10x detector invocations/run) | YES (separate dispatch) | NOT in this scope |
| **D** | separate cohort-detection harness (mirrors V2 OHLCV evaluator pattern) | NONE (research-branch addition) | YES (separate dispatch) | Banked V2 candidate |

If operator picks **A**, the implementer is ready to land it via a follow-up dispatch with:
- 1 helper function `_append_step_warning` (~10 lines)
- 1 modified early-return block (~5 lines)
- 1 TDD discriminating test (asserts empty-pool invocation appends a structured `pattern_detect` entry to `pipeline_runs.warnings_json`)
- Optional Codex MCP review per cumulative discipline if fix scope > 30 lines (not anticipated)

---

## 4. Deliverables shipped

1. **Investigation findings document** at [`docs/phase13-pattern-detect-step-silent-noop-investigation-2026-05-24.md`](phase13-pattern-detect-step-silent-noop-investigation-2026-05-24.md) (255 lines; 9 sections per brief §3.1)
2. **This return report** at [`docs/phase13-pattern-detect-step-silent-noop-investigation-return-report.md`](phase13-pattern-detect-step-silent-noop-investigation-return-report.md)
3. **NO production code fix** committed this dispatch. Operator approval required per brief §4.6 before Option A code change ships.

---

## 5. Investigation evidence summary

Key facts (full evidence trail in findings §8):

- `pattern_evaluations`: 0 rows (matches brief)
- `pipeline_runs`: 78 total; 7 post-ship (since T2.SB3 commit `2300dd4` 2026-05-20)
- 7/7 post-ship runs have `aplus_count = 0`
- 0/78 runs have non-empty `warnings_json`
- Detector code: confirmed operational via direct invocation against watch tickers (BULZ HTF 0.667)
- Pre-ship historical aplus runs: only 2 (37 + 39, both YOU, 2026-05-01/04, before T2.SB3 wired)
- Pattern_exemplars: 5 classes all have >= 1 valid (confirmed/watch) exemplar (vcp=5, cup=3, flat=1, htf=3, dbw=3); template matching would soft-skip when zero; doesn't gate INSERT

---

## 6. Discipline compliance per brief §4

| Discipline | Status |
|:---|:---|
| ZERO Co-Authored-By trailer | PRESERVED (no commits made; ~512+ cumulative streak through `eb48729` untouched) |
| `python -m swing.cli` not bare `swing` | N/A (no CLI invocations needed; direct module reproducer used) |
| ASCII-only on CLI paths + markdown | YES (findings + return report ASCII-only) |
| TDD per task | N/A this dispatch (no code change committed; Option A would add TDD test if landed) |
| Schema v21 LOCKED | PRESERVED (zero migration touches) |
| L2 LOCK (zero new Schwab calls) | PRESERVED (zero Schwab API surface touched; investigation read OHLCV via `OhlcvCache.get_or_fetch` per V1 read path) |
| V1 persisted state READ-ONLY beyond pattern_evaluations | PRESERVED (zero writes to any V1 table; pattern_evaluations also untouched - operator-approval gate for any write) |
| Production swing/ RELAXED for small fix < 30 lines | N/A (no production code change made; Option A is well under 30 lines and queued for operator approval) |
| Backfill of historical 78 runs NON-scope | PRESERVED (no backfill considered) |
| Adversarial Codex MCP review OPTIONAL | NOT INVOKED (diagnostic-only; no code change to review; threshold criterion not met) |

---

## 7. Forward-binding observations for orchestrator

1. **Brief framing correction**: orchestrator dispatch brief stated "78 completed pipeline runs since Phase 13 T2.SB3 detector landed". Only 7 of those 78 post-date T2.SB3 commit `2300dd4` (2026-05-20). Future orchestrator briefs should grep `git log --oneline` for the commit-of-interest + count post-commit runs explicitly.

2. **Operator decision required** before any production code ship. The investigation is diagnostic-complete; the remediation pathway is operator-paired.

3. **NEW gotcha-class candidate** banked at findings §6: "Silent-skip-without-audit pattern in pipeline steps". If operator concurs, promote to CLAUDE.md cumulative gotcha #27 at housekeeping.

4. **Research-question pathway**: the operator's actual research question ("do Phase 13 detectors over-filter the +75 cohort?") needs Option D (separate cohort-detection harness) regardless of Options A/B/C choice for the silent-no-op visibility. V1 `pattern_evaluations` will remain empty until aplus reappears in production OR the pool predicate is widened OR a separate harness is built.

5. **Process audit**: superpowers:systematic-debugging Phase 1 evidence-driven hypothesis-expansion correctly added H7 (the actual root cause) which was NOT in the brief's enumerated 6-hypothesis space. Pre-Codex orchestrator-side audit on the brief did not anticipate the empty-pool hypothesis. Banked observation for future investigation-dispatch briefs: when a step has an early-return on an empty-predicate guard, list that as a first-class hypothesis (Hα at top of enumeration), not buried under "audit operator-monitored fields".

6. **Investigation duration**: ~30 minutes wall-time (brief estimated 2-4 hours). The empty-pool hypothesis was decisive once the candidate-bucket DB query ran; the bisection counter-test (Reproducer 2) and the historical-cross-check (commit dates vs run timestamps) sealed the diagnosis without need for deeper code-walk or Codex review.

7. **Cumulative C.C lesson #6 validation**: NOT TRIGGERED this dispatch (no Codex invoked; no production-code-fix delivered). Will trigger as the 36th cumulative validation if Option A is approved + Codex invoked at follow-up dispatch (current count: 35th = full-reproduction-investigation per CLAUDE.md current state).

---

## 8. Open questions / handback to orchestrator

1. **Q1**: Operator decision Option A vs B vs C vs D (or combination A + D).
2. **Q2**: If Option A approved, should the warnings_json shape mirror existing project conventions, or introduce a Phase-13-specific structured envelope? (Implementer recommendation: project-wide convention with `kind` discriminator field for forward extensibility.)
3. **Q3**: NEW gotcha-class candidate (findings §6) promotion to CLAUDE.md #27 - operator concur?
4. **Q4**: V2-candidate Option D harness scope (cohort-detection at past eval_runs) - sequence vs Phase 14 commissioning consideration per Path B?

---

*End of return report. Awaiting orchestrator QA + operator-paired decision on remediation pathway. No commits made; branch ready for either (a) merge of findings-only via fast-forward + operator-paired follow-up dispatch for Option A, or (b) drop branch + ship findings via main commit.*
