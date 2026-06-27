# Broad-Watch-Baseline Hypothesis — Writing-Plans Dispatch Brief

**Audience:** Fresh Claude Code instance, no prior conversation context.
**Mission:** Produce the implementation PLAN (copowers:writing-plans) for the Codex-converged broad-watch-baseline
hypothesis design spec. The spec is BINDING — the plan implements it, it does not re-open settled design decisions.
**Prepared:** 2026-06-09 by the research-director/evaluator instance, after QA-PASS of the brainstorm return
(spec verified against the live DB + shipped code; see QA notes in `docs/research-director-context.md` §7).
**Phase:** copowers:writing-plans. Output → a TDD implementation plan → (later) executing-plans as a separate dispatch.

---

## 0. Read first

1. `CLAUDE.md` — conventions (conventional commits; NO co-author footer; NO `--no-verify`; TDD) + the gotchas this
   arc touches directly: **#9** (executescript autocommit → explicit `BEGIN;…COMMIT;` in the migration), **#11**
   (schema/constant/validator atomicity + the hardcoded-enum sweep), the **migration backup-gate strict-equality**
   shape, and `feedback_regression_test_arithmetic` (compute expected test values under BOTH pre- and post-0026
   states so each assertion distinguishes).
2. **The BINDING spec** — `docs/superpowers/specs/2026-06-09-broad-watch-baseline-hypothesis-design.md`
   (committed `99e0608f`, Codex-converged R3 `NO_NEW_CRITICAL_MAJOR`, 1 crit/8 maj/5 min all resolved). Every design
   decision in it is settled: the frozen §2 pre-registration SQL, the §3.1 two-phase fallback matcher, the §3.2
   opt-in containment (NO `measurement_only` column), the §5 consumer split (progress/process ACCEPT; tier/deviation
   AUTO-EXCLUDE — tier.py is NOT touched), §7 migration mechanics + the #11 sweep table, §7.2 testkit bump +
   `test_no_match_returns_empty` flip, §9 acceptance fixtures 1–6 + the real-shape fixture mandate.
3. The commissioning brief `docs/broad-watch-baseline-hypothesis-brainstorming-dispatch-brief.md` (context only; the
   spec supersedes it where they differ).
4. The code the plan edits: `swing/recommendations/hypothesis.py` (matcher), `swing/data/db.py` (gates ~L218-228 +
   the version-gate short-circuit pattern), `swing/data/migrations/0008_…` + `0017_…` (the seed shapes 0026 mirrors),
   `research/harness/shadow_expectancy/attribution.py`, `tests/research/shadow_expectancy/testkit.py` +
   `test_attribution.py`, and the §7.1 test files.

**Skill posture:** invoke `copowers:writing-plans` (wraps superpowers:writing-plans + adversarial Codex review run to
convergence; 5-round cap suspended).

---

## 1. What the plan must cover (the spec's §8 carve-out, exactly)

1. **Migration `0026_broad_watch_baseline.sql`** — the spec §2 SQL verbatim (frozen literal text; single-line or
   `||`-wrapped per the spec's formatting note): `BEGIN;` + registry `INSERT OR IGNORE` + the
   `hypothesis_status_history` open-interval seed + `UPDATE schema_version SET version = 26;` + `COMMIT;`.
2. **`swing/data/db.py`** — `EXPECTED_SCHEMA_VERSION` 25→26; `_broad_watch_baseline_backup_gate` (STRICT
   `current_version == 25 AND target_version >= 26`); the corrected expected-tables constant
   (`PHASE16_PRE_MIGRATION_EXPECTED_TABLES | {"pipeline_step_timings"}` = the true v25 set — verified: the PHASE16
   constant aliases the v24/B7 set); gate registration in `run_migrations`.
3. **`swing/recommendations/hypothesis.py`** — `H_BROAD_WATCH_BASELINE` constant; `_broad_watch_baseline_match`
   predicate; keyword-only `include_baseline: bool = False` on `match_candidate_to_hypotheses`; the two-phase
   structure with the baseline gate on `if include_baseline and not matches:` (order-robust, NOT list-position).
4. **`research/harness/shadow_expectancy/attribution.py`** — pass `include_baseline=True` (the ONLY opt-in caller).
5. **Tests** — the spec §9.1 golden fixtures 1–6 (baseline prices end-to-end; H2/H4 anti-cannibalization; the H3
   active-status flip with an H3-*eligible* set; `include_baseline=False` containment; migrate-twice no-op;
   name-safety both directions), the §7.1 sweep (each assertion resolved **version-aware AND active-vs-all-aware** —
   a fresh head-built DB has H3 *active*, 5 active rows; the live DB has H3 closed; tests pinned below v26 stay at
   4), the §7.2 testkit bump to `target_version=26` + the `test_no_match_returns_empty` flip + a preserved
   true-no-match non-watch fixture + direct matcher-level containment tests.

**NOT in the plan (spec §8 NOT-touched list — treat as locks):** `swing/metrics/tier.py` (allowlist auto-excludes;
its `== 4` tests STAY 4), `swing/data/models.py`, `swing/data/repos/hypothesis.py`, the live recommendation call
sites, all Family-2 surface code (tests only), the four frozen registry rows, `DOCTRINE_DEFENSIBLE_MISS_SET`, the
engine's simulator/bracket/funnel/scorecard/`constants.py`, and no new production dependency (the engine's
forbidden-import L2 test stays green).

---

## 2. Plan-quality requirements

- **TDD per task:** failing test → minimal implementation → pass → commit; the plan specifies the exact test
  assertions and the expected pre-fix/post-fix values (per `feedback_regression_test_arithmetic`).
- **Fixtures from REAL emitter shapes (spec §9.2, non-negotiable):** candidate fixtures carry the live
  `criterion_name` vocabulary + real non-pass sets (the verified composition: `{proximity_20ma,tightness}`=110,
  `{adr,tightness}`=61, `{tightness,vcp_volume_contraction}`=60, `{tightness}`=36, H2-exact=1, H4-exact=0 of 400).
  The H2/H4 overlap fixtures (§9.1.2–3) are MANDATORY — a plan that only exercises the broad rule recreates the
  cannibalization bug.
- **Task ordering must respect the schema dependency:** migration + db.py gates land before (or with) the testkit
  bump; the matcher change and the attribution opt-in land with their tests in the same task to keep #11 atomicity.
- **Verification tail:** full fast suite + ruff + the migrate-twice no-op + a live-DB-shaped smoke assertion
  (a fixture DB at v26 where a watch candidate with a dominant real non-pass set attributes to the baseline under
  `include_baseline=True` and to NOTHING under the default).

---

## 3. Codex transport + review mandate (this machine)

The MCP `codex` tools are dead in the VS Code extension. Drive Codex via the WSL CLI:
```
wsl -e bash -c 'export PATH="$HOME/.local/node22/bin:$PATH"; codex exec -s read-only --skip-git-repo-check -C "<repo root>" - < "<repo root>/.copowers-review-prompt.txt"'
```
PATH-prefix export REQUIRED; liveness probe `codex --version` → `codex-cli 0.135.0`; round 2+ via
`codex exec resume --last -c sandbox_mode="read-only" --skip-git-repo-check`. Run to convergence
(`NO_NEW_CRITICAL_MAJOR`); the 5-round cap is suspended.

- **Persist EVERY round's full RESPONSE** (findings + verdict line) to the gitignored findings file — **including
  Round 1.** (QA flag from the brainstorm return: Round 1's response section was left empty in
  `.copowers-findings.md`; prompt-only persistence does not satisfy the discipline. Do not repeat that slip.)
- **Mandate Codex verify the plan's edits against the SHIPPED code signatures** (the matcher's current rules-list
  shape, the db.py gate registration pattern, the testkit pin, the §7.1 test files' actual current assertions) and
  the spec's data claims against the supplied live-query output — the standing
  `feedback_adversarial_review_verify_data_shapes` mandate.

---

## 4. Done criteria + handoff

- A TDD implementation plan at `docs/superpowers/plans/<date>-broad-watch-baseline-hypothesis.md`, self-reviewed and
  **Codex-converged**, with responses persisted (all rounds).
- The plan covers §1 exactly, honors the §1 locks, and meets §2 quality requirements.
- **Do NOT implement.** Return for research-director QA, then executing-plans as a separate dispatch.
- Commit the plan (conventional; no co-author footer; verify `git log -1 --format='%(trailers)'` is `[]`). Return a
  short summary: task list shape, any spec ambiguities you resolved (with the spec-faithful reading), Codex
  convergence verdict, and anything you pushed back on.
