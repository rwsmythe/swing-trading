# Commissioning Brief — 19-A: coverage_gaps CALIBRATION-C trailing-delisting fix

**From:** CHARC. **To:** the Phase-19 orchestrator. **Arc:** 19-A (Phase 19, first arc — [`phase19-scope-charc.md`](phase19-scope-charc.md)). **Committed:** 2026-07-02, operator-approved scope. **Design status:** SETTLED (RD-proposed, CHARC-verified on disk, operator-approved) — start at `copowers:writing-plans`; do NOT re-open brainstorming.

## §0 References (read before planning)

- **RD's diagnosis mail** (the founding artifact): `comms/charc/read/20260702T044056Z-rd-coverage-gaps-calibration-c-gap-my-desig.md` (thread `coverage-gaps-calibration`). RD owns the CALIBRATION-C design and this gap; RD reviews the refinement's measurement semantics.
- **Fix locus:** `swing/monitoring/research_health.py` — `_calibration_c_partition` (:1063-1105; the gate at :1091-1093). Supporting reads: `_observe_skip_index` (:934-996), `_OBSERVE_SKIP_REASONS` (:916), the module comment block (:895-916), the never-observed call-site (:1268-1295), the observed-arm call-site immediately below it, `_graced_missing_count` usage (:1289).
- **Skip-warning emitter:** `swing/pipeline/runner.py:3081` (`"reason": "no bar for observation_date"`) — the production shape fixtures MUST mirror.
- **Live evidence:** run 116/117 `pipeline_runs.warnings_json` (30 + 35 CNTA skip-warnings); the live coverage_gaps RED (60 gaps, run 117, real leased run).
- **Existing tests:** the coverage_gaps monitor tests under `tests/` mirroring `swing/monitoring/` (incl. the DINO interior skip-warning case — must stay green unchanged).

## §1 Problem (CHARC-verified on disk 2026-07-02)

CNTA was delisted/acquired after 2026-06-29 (yfinance: flat O=H=L=C=40.50 pinned at deal price 06-26/06-29, then no bars). The observe step CORRECTLY recorded `no bar for observation_date` skip-warnings for CNTA in completed runs 116/117. But `_calibration_c_partition` evaluates `if not clause1: continue` (:1092) **before** either acceptance clause — so clause-1 (an observed session strictly AFTER the hole, i.e. the drumbeat moved PAST it) gates BOTH clause-2a (whole-session-miss) AND clause-2b (skip-warning-explained). A delisted ticker's skip-warning holes are TRAILING — no later observation is possible — so clause-1 is False, 2b is never consulted, and the holes are COUNTED → false-RED (60 gaps; ~2/3 are CNTA's 06-30 + 07-01 across ~40 detections; the rest are other tickers at ~5 detections each — the fix should explain those too or the triage names them). The docstring (:1074-1077) documents trailing-never-accepted as intended — the design didn't anticipate delisting. The RED **persists** (trailing holes are permanent until age-out) and **recurs on every future delisting** in the watch universe — the cry-wolf class CALIBRATION C exists to kill.

## §2 The fix (small, single-function)

Restructure the `_calibration_c_partition` loop so **clause-2b (`skip_explained`) is evaluated INDEPENDENT of clause-1; clause-1 continues to gate ONLY clause-2a (`is_whole_session_miss`)**. A skip-warning is DIRECT per-(ticker, session) evidence of a benign no-bar — legitimate whether the hole is interior OR trailing. Safety (RD's argument, CHARC-verified against `_observe_skip_index`): the index admits only warnings from `state='complete'` runs whose `data_asof_date` equals the warning's `observation_date` (:940-994) — a real drumbeat-behind trailing failure has no completed run for those sessions → no skip-warnings → 2b false → **still counted**. The discriminator "skip-warning present" correctly separates a delisting (accept) from a drumbeat-behind failure (RED).

**Documentation updates in the same change** (they currently document the OLD contract): the function docstring (:1071-1086, esp. "a TRAILING hole … is never accepted here"), the module comment block (:895-916 acceptance formula), and the never-observed call-site comment (:1275-1279, "clause-1 is FALSE for every session -> nothing accepted" — no longer true).

**Three explicit semantic consequences for RD's plan-stage review** (state them in the plan; do not bury them):
1. Trailing skip-explained holes are now accepted (the intended fix).
2. **A NEVER-observed detection with fully-skip-explained expected sessions is now accepted** (empty `observed` → clause-1 false for every S, but 2b can now fire) — the immediate-delisting-after-detection case. CHARC reads this as CORRECT (each hole individually evidence-explained); RD blesses or bounds it.
3. The 2b-trust caveat (RD's own): a FALSE "no bar" skip on a ticker that HAS bars would be masked — an accepted low-probability observe-integrity concern, out of scope here.

**Out of scope:** RD's alternative (truncate a delisted detection's expected-session window at its last-bar session) — held as v2 if evidence demands; do NOT implement both. No `runner.py`/observe-step changes. No CALIBRATION-A/grace changes. No conservative-degrade changes (the `run_observed_sessions is None` handling, the schema-unavailable paths). The monitor stays read-only.

## §3 Discriminating tests (arithmetic computed under BOTH paths — `feedback_regression_test_arithmetic`)

> **Fixture-count constraint:** `_graced_missing_count` graces a single newest-session trailing hole (the #3 trailing-≤1 grace, applied to the residual at :1289) — so every discriminating fixture below uses **≥2 trailing sessions** or the grace masks the pre-fix count and the test fails to discriminate. (CNTA's real shape is exactly 2: 06-30 + 07-01.)

- **T1 — trailing delisting (the fix):** a detection observed through S_k; sessions S_k+1, S_k+2 missing; both (ticker, S) pairs skip-warning-explained via `state='complete'` runs with matching `data_asof_date`. PRE-fix: clause-1 false → both counted → missing=2. POST-fix: 2b accepts both → missing=0, `accepted` grows by 2. **Discriminates.**
- **T2 — trailing drumbeat-behind (the safety lock):** same shape, NO skip-warnings (no completed runs for those sessions). Counted (=2) under BOTH pre- and post-fix. Proves the fix cannot mask a real trailing failure.
- **T3 — clause-2a stays clause-1-gated (the over-eager-fix lock):** a TRAILING whole-session miss (S absent from global observations AND from the completed-run ledger, no skip-warning). Counted under BOTH paths. FAILS an implementation that un-gates both clauses instead of only 2b.
- **T4 — regression:** the existing interior skip-warning (DINO) test and all other coverage_gaps tests pass UNCHANGED (interior + skip-warning: clause-1 true, 2b true → accepted under both paths).
- **T5 — never-observed + fully-skip-explained (consequence #2, made explicit):** a mature never-observed detection whose every expected session carries a skip-warning → PRE: all counted; POST: all accepted. Locks the semantics RD blesses at plan review.
- **Fixture shape discipline** (the synthetic-fixture-vs-production-emitter gotcha family): derive `warnings_json` entries from the REAL emitter shape at `runner.py:~3070-3090` (`step='pattern_observe'`, `reason` from `_OBSERVE_SKIP_REASONS`, `ticker`, `observation_date`), cross-checked against the LIVE run-116/117 rows. A warning not tied to a completed run with `data_asof_date == observation_date` is dropped by the index (:940-994) — fixtures must satisfy that tie or they silently test nothing.

## §4 Scope + locks

Single production file (`swing/monitoring/research_health.py`) + its tests. **NO schema** (v31 holds). **NO §3 tripwire** (no new module/dep/standing process/carve-out) — orchestrator self-certifies in the plan. Conventional commits, trailer-free (the 3774-streak), no `--no-verify`, pathspec hygiene.

## §5 Gates (in order)

1. **Plan-stage RD review (REQUIRED before executing):** after your plan QA, post the plan pointer to RD via `role_mail` (from the MAIN repo dir) — RD designed CALIBRATION C, explicitly requested semantics review, and consequence #2 needs an explicit bless. Operator resolves per the standing convention.
2. Codex adversarial review to convergence (review-strong; zero new crit/major) + **codex-auto-review** (production-code arc).
3. Merged-head fast suite, no-false-green (read the actual result); ruff clean.
4. **Live-DB gate (binding — the symptom is live):** run the research-health monitor against the live DB post-merge; `coverage_gaps` must flip GREEN with the CNTA holes 2b-accepted (the `accepted` counters/sample reflect them) and T2-class behavior demonstrably preserved. Operator witnesses.
5. **RD merge-blocking QA at the return** (measurement semantics).
6. **The ORCHESTRATOR posts the return report to `charc,rd` AFTER its own QA** — the implementer reports in chat to the orchestrator only and never posts to director mailboxes.

## §6 Sizing + dispatch recommendation

Tiny: one function restructure + comment/docstring updates + ~5 tests. CHARC recommendation: **`implementer-opus-high`** (locked-plan TDD of a small change; the measurement-semantics risk is carried by the RD plan-stage + merge gates, not implementer reasoning depth). The orchestrator owns the final cell selection + announces it before spawn per the recipe.
