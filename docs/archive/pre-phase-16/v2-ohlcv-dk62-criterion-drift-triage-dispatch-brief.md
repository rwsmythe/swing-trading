# V2 OHLCV DK:62 CRITERION DRIFT Triage — Investigation Dispatch Brief

**Audience:** Fresh Claude Code instance dispatched as the DK:62 CRITERION DRIFT investigation implementer. No prior conversation context.

**Mission:** Root-cause the V1↔V2 baseline parity divergence on Delek US Holdings (DK) at `eval_run_id=62` surfaced by V2 OHLCV harness partial implementer smoke at `exports/diagnostics/aplus-sensitivity-v2-20260523T230131Z.{csv,md}`. Identify (a) which side is correct (V1 persisted OR V2 recomputed); (b) drift scope (DK:62 isolated OR systemic across other tickers/eval_runs); (c) remediation recommendation (re-run V1 evaluation / fix V2 reader / document drift as expected / other).

**Workflow:** `superpowers:systematic-debugging` skill (investigation; NOT full TDD/copowers executing-plans). Adversarial Codex review OPTIONAL — invoke if proposed code changes land; skip if investigation is diagnostic-only with return report deliverable.

**Branch:** `applied-research-v2-dk62-criterion-drift-triage` — branches from main HEAD after this brief lands.

**Worktree:** `git worktree add .worktrees/applied-research-v2-dk62-criterion-drift-triage applied-research-v2-dk62-criterion-drift-triage`. Work from that cwd; invoke `python -m swing.cli` (NOT bare `swing`).

**Expected duration:** ~2-6 hours operator-paced (investigation + return report; code changes if needed extend scope).

---

## §0 Read first (in this order)

1. **`exports/diagnostics/aplus-sensitivity-v2-20260523T230131Z.md`** — the smoke artifact that surfaced the drift. Note the CRITERION DRIFT section reports `DK:62` 3 times (one per per-variable drill-down emit; deduplication of `affected_tickers` list shipped at `8bc577f` may not have fully propagated to ALL emit paths; verify if cosmetic OR signal).

2. **`exports/diagnostics/aplus-sensitivity-v2-20260523T230131Z.csv`** — sensitivity matrix CSV companion. Inspect for DK-specific rows + per-variable flips.

3. **`docs/superpowers/specs/2026-05-23-v2-ohlcv-criterion-evaluator-design.md`** §E.4 (baseline parity invariant) — the BINDING contract V2 implements:
   - **Tier-1 (non-risk-gated buckets)**: V2 invoked with no substitution MUST produce the same bucket distribution as V1's persisted-bucket pass — EXACT match required.
   - **Tier-2 (risk-gate-dependent buckets)**: CONDITIONAL match via `current_equity` surrogate per OQ-15 — non-blocking; surrogate-flagged.
   - DK:62 hit Tier-1 FAIL → V2 recomputed bucket ≠ V1 persisted bucket for DK at eval_run 62.

4. **`docs/v2-ohlcv-criterion-evaluator-executing-plans-return-report.md`** §2.1 — Codex caught REAL defects against actual production code at implementation time (5 defects listed). Reference for the hypothesis space.

5. **`research/harness/aplus_v2_ohlcv_evaluator/sweep.py`** + **`research/harness/aplus_v2_ohlcv_evaluator/context_builder.py`** + **`research/harness/aplus_v2_ohlcv_evaluator/ohlcv_reader.py`** — V2 source.

6. **`swing/evaluation/scoring.py`** (`bucket_for`) + **`swing/evaluation/criteria/*.py`** (8 trend_template + 9 vcp + 1 risk criteria) + **`swing/evaluation/evaluator.py`** (`evaluate_one`) — V1 production source.

7. **`swing/data/repos/candidates.py`** + **`swing/data/migrations/0001_phase1_initial.sql`** — `candidates` + `candidate_criteria` + `evaluation_runs` schema; `candidates` keyed on `evaluation_run_id`.

8. **CLAUDE.md** gotchas — ESPECIALLY relevant to this investigation:
   - **#21 NEW Expansion #13 candidate: cumulative regression cascade audit** — if proposed fix restructures V2 control flow, apply imagined-Codex-next-round audit.
   - **`current_equity` surrogate per OQ-15** — V2's tier-2 use of `account_equity_snapshots` may not match V1 persisted; expected non-blocking but check whether DK:62 was tier-1 (BLOCKING) vs tier-2 (CONDITIONAL).
   - **OHLCV cache scope per Codex R1.M3** — V2's `build_eval_run_cohort` was rewired to inject `ohlcv_getter` through dependency injection; verify the per-ticker cache fires correctly for DK at eval_run 62 asof_date.

---

## §1 Hypothesis space (4 root-cause candidates)

Investigation MUST evaluate each hypothesis explicitly + cite evidence for/against.

### §1.1 H1: Criterion implementation drift between V1 ship time + V2 invocation

**Evidence to gather**:
- `git log --all --oneline swing/evaluation/scoring.py swing/evaluation/criteria/ swing/evaluation/evaluator.py` between eval_run 62's `data_asof_date` + today's V2 invocation timestamp
- Identify any per-criterion implementation change (e.g., threshold rounding, branch order, default value) that would flip DK:62's bucket
- Cross-check against `candidate_criteria` rows persisted at eval_run 62 (compare per-criterion `status` + `evidence_value` vs V2 recomputed values for DK)

**Falsification**: if no production criterion code changed between eval_run 62 + today, H1 is ruled out.

### §1.2 H2: cfg drift (`bucket_for` thresholds or downstream cfg changed)

**Evidence to gather**:
- `git log --all --oneline swing.config.toml swing/config.py` between eval_run 62 date + today
- Identify any cfg-bound threshold change (e.g., `trend_template.min_passes`, `vcp.watch_max_fails`, `rs.rs_rank_min_pass`) that would flip DK:62's bucket
- Compare V1's persisted `bucket` for DK:62 vs `bucket_for(...)` recomputed with CURRENT cfg

**Falsification**: if no cfg-bound threshold changed (or changed thresholds don't affect DK:62), H2 is ruled out.

### §1.3 H3: Bug in V2 (OHLCV slicing or context_builder or cfg_substitution issue)

**Evidence to gather**:
- Reproduce V2 invocation against DK alone at eval_run 62: synthetic fixture with DK's Shape A parquet bytes + V2 invocation with `--variables-filter=<one variable>` `--eval-runs=1` (anchored at eval_run 62)
- Inspect intermediate state: BatchContext for DK at eval_run 62 asof_date; OHLCV slice; cfg substitution applied; `evaluate_one(ctx)` per-criterion output
- Compare V2 recomputed `tier` + `bucket` to V1 persisted for DK:62
- Check edge cases: (a) OHLCV `asof_date` boundary inclusive vs exclusive per cumulative gotcha "Session-anchor inequality discipline depends on anchor directionality"; (b) OHLCV `<200 bars` coverage skip path; (c) `current_equity` surrogate fallback path
- L2 LOCK reinforcement: verify V2's OHLCV read for DK uses `{DK}.yfinance.parquet` ONLY (NOT `{DK}.schwab_api.parquet`) — file-open mock pattern from `tests/research/test_aplus_v2_ohlcv_reader.py:182` may need to be invoked in investigation

**Falsification**: if V2 reproduces V1 persisted bucket exactly when given V1's persisted inputs (criterion thresholds + OHLCV bars + current_equity), H3 is ruled out for DK:62.

### §1.4 H4: Bug in V1 persisted state (race condition / partial write / stale OHLCV at original eval_run 62)

**Evidence to gather**:
- Inspect `pipeline_runs` row for eval_run 62: `started_ts`, `finished_ts`, `state`, `notes`. Any anomalies (very short duration; failure trailer; partial write)?
- Inspect `evaluation_runs` for eval_run 62: timing, any error notes
- Check OHLCV archive freshness at eval_run 62 timestamp — was DK's Shape A parquet stale OR partial at the time of original eval_run?
- Cross-reference `candidate_criteria` for DK:62: any criterion with `status='error'` or anomalous `evidence_value`?

**Falsification**: if V1 persisted state for DK:62 is fully consistent (no error markers, no anomalous timing), H4 is unlikely.

### §1.5 Other candidates (banked at investigation discretion)

If H1-H4 all falsify, document a residual candidate (e.g., yfinance Shape A archive corruption since eval_run 62 — would invalidate L2 LOCK reproducibility claim; OR criterion-implementation edge case not exercised by existing tests).

---

## §2 Drift scope investigation

After identifying root cause for DK:62, investigate scope:

- **Same-eval_run scope**: Does eval_run 62 affect OTHER tickers? Query `candidate_criteria` for eval_run 62; run V2 with `--eval-runs=1` anchored at eval_run 62 + check Tier-1 parity for ALL candidates.
- **Same-ticker scope**: Does DK drift across OTHER eval_runs? Run V2 with `--variables-filter=<none>` + check DK's V2 vs V1 across eval_runs 1-63.
- **Systemic scope**: Is this a class of tickers/eval_runs OR a one-off? If multiple drifts, identify pattern (e.g., all weekend pipeline runs; all small-cap tickers; all tickers with `<some criterion failure>`).

---

## §3 Deliverables

The investigation MUST produce:

1. **Investigation findings document** at `docs/v2-dk62-criterion-drift-investigation-2026-MM-DD.md` covering:
   - Per-hypothesis evidence summary (H1, H2, H3, H4, H5+)
   - Root cause identification (with code:line citation)
   - Drift scope (DK:62 isolated OR pattern across N tickers/eval_runs)
   - Remediation recommendation (one of: re-run V1 evaluation for affected eval_runs / fix V2 reader / document drift as expected per `current_equity` surrogate / other)
   - Forward-binding lessons for future research-branch arcs

2. **Optional**: if a V2 code fix is needed (e.g., reader bug found), implement + test on the same branch:
   - Mirror plan §G TDD discipline (test → impl → commit per TDD slice)
   - L2 LOCK 5 BINDING tests MUST remain green
   - `git diff swing/` MUST remain ONLY `swing/cli.py` (no NEW production writes per OQ-17 invariant)
   - If V1 code fix needed (rare; would violate the production-read-only invariant): SURFACE in findings + DEFER to operator-paired triage; do NOT ship V1 changes in this dispatch.

3. **Optional**: if drift is broader than DK:62, surface affected-ticker list + recommend whether full operator 63-eval-run reproduction proceeds OR is paused pending fix.

4. **Return report** at `docs/v2-dk62-criterion-drift-investigation-return-report.md` (per cumulative precedent shape; commit chain + Codex chain if invoked + per-expansion verdict if invoked + cumulative streaks preserved).

---

## §4 Watch items + cumulative discipline (BINDING)

### §4.1 Pre-Codex 7-expansion + 5 NEW candidate refinements + 2 NEW sub-refinements + 3 NEW sub-promotions

If investigation surfaces code changes warranting Codex review (e.g., V2 reader bug fix), apply ALL of:
- 7 expansions (#1-#7) + Expansion #8 + #9 + #10 + #11 + #12 candidates
- 2 NEW sub-refinements: #19 cascade-call-graph + #20 runtime-binding-shape + empty-result-set
- 3 NEW from V2 executing-plans: #21 cumulative regression cascade + #22 per-counter-accumulation + #23 dataclass attribution metadata

20 cumulative gotchas (1-20) + 3 NEW (21+22+23) = 23 BINDING for any 34th cumulative C.C lesson #6 validation.

### §4.2 Cumulative process discipline

- **NO Co-Authored-By footer** — ~493+ cumulative streak through housekeeping `25efdb5`. Cite per fresh forward-binding lesson #7 (Phase 12 Sub-sub-bundle C.B 2026-05-15) in every commit message.
- **`python -m swing.cli` from worktree cwd**, NOT bare `swing`
- **ASCII-only on runtime CLI paths** + markdown narrative text (Windows cp1252 stdout safety)
- **TDD per task** via `superpowers:test-driven-development` if code changes land
- **Edit tool for per-file edits**

### §4.3 Schema discipline (LOCK)

Schema v21 LOCKED. Investigation MUST NOT touch migrations. If a schema change is hypothesized, SURFACE in findings + DEFER to operator-paired triage (would become a new dispatch).

### §4.4 L2 LOCK preservation (BINDING)

ZERO new Schwab API calls. ZERO reads of `{ticker}.schwab_api.parquet`. If investigation needs DK OHLCV data, use `{DK}.yfinance.parquet` from the existing Shape A archive — DO NOT trigger yfinance fetch via production helpers (`read_or_fetch_archive` actively fetches per CLAUDE.md gotcha #17).

### §4.5 Read-only invariant for V1 persisted state

DO NOT modify `candidate_criteria` rows for eval_run 62 OR any other eval_run during investigation. If V1 persisted state is determined to be wrong (H4 confirmed), surface in findings + recommend re-run path (which requires operator-paired triage; out of scope for THIS investigation).

---

## §5 Pre-investigation context (operator-side gathered)

- **DK ticker**: Delek US Holdings (oil refiner; sector: Energy)
- **eval_run_id=62**: one of the 63 eval_runs in operator's S3 universe (5681 candidates / 63 eval_runs); date depends on eval_run dates (query `evaluation_runs` for `id=62` `data_asof_date`)
- **V2 partial smoke**: 5 eval_runs (ids 60..64) / 120s cap / 516 universe / 351 candidates evaluated; DK:62 drift surfaced; AESI + PL + DK both-exist warning surfaced (16 tickers total)
- **V2 source**: `research/harness/aplus_v2_ohlcv_evaluator/` (5 NEW modules + tests; SOLE production write `swing/cli.py` +71 lines per OQ-17 carve-out)
- **V2 baseline parity test**: `tests/research/test_aplus_v2_ohlcv_sweep.py::test_baseline_recompute_matches_persisted_bucket_distribution_exactly` (Tier-1 invariant test). Investigation may extend this test or add a DK:62-specific regression test.

---

## §6 NON-scope

- ZERO Phase 14 commissioning consideration (DEFERRED per Path B sequencing)
- ZERO promotion of V2 method-record from `research` → `shadow` (DEFERRED per OQ-8 ladder; gated on DK CRITERION DRIFT resolution)
- ZERO full 63-eval-run operator reproduction (that's the SEPARATE operator-paired next action; this investigation is the prerequisite)
- ZERO V1 production code changes (production read-only invariant; if H1 confirms criterion drift, surface in findings + DEFER to operator-paired triage)
- ZERO Schwab API calls (L2 LOCK preserved per §4.4)
- ZERO new schema migrations (schema v21 LOCKED per §4.3)
- ZERO modification of V1 persisted candidate_criteria / pipeline_runs / evaluation_runs rows (read-only per §4.5)

---

## §7 Post-investigation handback

When investigation findings + recommendation are documented:

1. Write findings document at `docs/v2-dk62-criterion-drift-investigation-2026-MM-DD.md` per §3.1
2. Write return report at `docs/v2-dk62-criterion-drift-investigation-return-report.md` per §3.4
3. Inline self-verification: ruff check; schema unchanged; ZERO new Schwab API calls; ZERO Co-Authored-By footer
4. Hand back to operator with:
   - Root cause + code:line citation
   - Drift scope (isolated / systemic / pattern)
   - Remediation recommendation
   - Any V2 candidates banked for follow-up dispatches

Orchestrator-side next steps post-investigation:
- QA findings per `feedback_orchestrator_qa_implementer_product`
- Merge investigation branch `--no-ff` to main; push (only if findings + return report committed)
- Post-merge housekeeping if NEW gotchas surfaced
- Operator-paired decision on remediation path
- IF remediation requires re-run V1 evaluation: SEPARATE dispatch
- IF remediation requires V2 reader fix: continue in same branch OR new dispatch per scope
- IF drift is non-blocking (documented as expected per current_equity surrogate or similar): unblock research → shadow promotion gate + proceed to full 63-eval-run reproduction

---

*End of V2 OHLCV DK:62 CRITERION DRIFT triage dispatch brief. Investigation scope only (NOT full executing-plans dispatch). 4 root-cause hypotheses enumerated; deliverable = findings + remediation recommendation. ~493+ ZERO Co-Authored-By footer streak preserved through this brief commit. Applied Research Tranche 1 arc COMPLETE; investigation unblocks research→shadow promotion gate + full 63-eval-run operator reproduction.*
