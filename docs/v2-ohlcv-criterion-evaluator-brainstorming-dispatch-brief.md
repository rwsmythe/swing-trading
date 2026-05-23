# V2 OHLCV Criterion-Evaluator Harness — Brainstorming Dispatch Brief

**Audience:** Fresh Claude Code instance dispatched as the V2 OHLCV criterion-evaluator harness brainstorming implementer. No prior conversation context.

**Mission:** Brainstorm a design spec for the V2 OHLCV criterion-evaluator harness — the first method-record under the `aplus-criteria-calibration` lineage per OQ-CL.3 LOCK. The harness's PURPOSE: lift the V1 sensitivity-harness limitation where 15 of 17 threshold variables report `delta_aplus = delta_watch = 0` (because V1 returns the persisted bucket without recomputing criterion outcomes against substituted thresholds). The V2 harness must consume original OHLCV bars at each candidate's `data_asof_date`, substitute per-criterion thresholds, recompute `bucket_for` end-to-end, and emit a richer sensitivity matrix that identifies which threshold variable(s) (if any) are binding at the watch→A+ promotion boundary.

**This is the FIRST Applied Research arc post-Phase-13-FULLY-CLOSED**, dispatched per operator decision 2026-05-23 PM locking Path B (Applied Research focus) at `docs/phase13-closer-next-phase-triage.md` commit `b4d7719`. V2.1 §V branch posture: lives under `research/`, NOT production `swing/` code. V2.1 §IV.D + §VII.C lifecycle posture: method-record starts at `status='research'`; promotion to `shadow` / `production` requires operator-paired evidence summary post-output review.

**Brief:** `docs/v2-ohlcv-criterion-evaluator-brainstorming-dispatch-brief.md` (this file).

**Branch:** `applied-research-v2-ohlcv-criterion-evaluator-brainstorm` — branches from main HEAD after this brief lands.

**Worktree:** `git worktree add .worktrees/applied-research-v2-ohlcv-criterion-evaluator-brainstorm applied-research-v2-ohlcv-criterion-evaluator-brainstorm`. Work from that cwd; invoke `python -m swing.cli` (NOT bare `swing`).

**Workflow:** `copowers:brainstorming` skill (wraps `superpowers:brainstorming` with adversarial Codex MCP review). Expected 2-5 Codex rounds.

**Expected duration:** ~3-5 hours operator-paced. Spec target: ~600-1000 lines (V1 aplus-sensitivity method-record at 72 lines + V1 earnings-proximity at 46 lines is the BANKED-METHOD-RECORD format; the V2 OHLCV harness SPEC will be larger because it covers per-criterion evaluator design + OHLCV archive reconstruction + cfg-override interface + per-class bucket recompute semantics).

---

## §0 Read first (in this order)

1. **`research/method-records/aplus-criteria-calibration.md`** at main HEAD — PRIMARY SUBSTRATE. 72 lines; V1 method-record with V2 dependencies enumerated explicitly. The V2 OHLCV criterion-evaluator harness is the lifted-limitation deliverable. **READ END-TO-END before designing.**

2. **`docs/phase13-closer-next-phase-triage.md`** at HEAD `b4d7719` — operator-paired triage decision-record with locked Path B disposition + findings summary. Contains the headline interpretation of S3 sensitivity-harness output:
   - 15 of 17 threshold variables show ZERO delta in V1 — that is the V2 unblock target
   - 2 gate variables (`trend_template.min_passes`, `vcp.watch_max_fails`) are **non-binding** at the A+ tier
   - The 5-A+-candidates-across-63-eval_runs constraint is in the inert 15 OR market conditions OR other gates not enumerated as `kind=gate` in V1

3. **`exports/diagnostics/aplus-sensitivity-20260523T065514Z.md`** — operator's actual S3 output (134 lines; 118 sensitivity-matrix rows). The 15 inert threshold variables are enumerated explicitly with sweep ranges. Verify the V2 design covers each.

4. **`research/studies/aplus-criterion-sensitivity-2026-05-22.md`** — V1 study writeup. Contains the established study format precedent + the per-variable disposition table.

5. **`research/harness/aplus_sensitivity/`** — V1 implementation. Read end-to-end:
   - `variables.py` — variable enumeration logic. V2 extends OR replaces this enumeration; gate variables stay; threshold variables get LIVE bucket recompute.
   - `sweep.py` — `_bucket_for_substituted` for gate variables (mirror of `swing.evaluation.scoring.bucket_for`). V2 must do something analogous BUT for threshold variables, replacing the persisted-bucket passthrough with a LIVE per-criterion bucket recompute.
   - `output.py` — sensitivity matrix CSV + markdown formatter. V2 likely extends OR replaces this for richer per-criterion output.
   - `run.py` — CLI entrypoint stub.

6. **`research/harness/earnings_proximity/`** — predecessor research-branch precedent. Mirror its directory shape + script convention. Its `study.md` is the model for V2's first study writeup.

7. **`research/method-records/_template.md`** + **`research/method-records/earnings-proximity-exclusion.md`** — method-record format references.

8. **`swing/evaluation/scoring.py`** — `bucket_for` production implementation. V2 harness must invoke this end-to-end (with substituted threshold cfg) per candidate per sweep point. Understand the call signature, dependencies (cfg shape; candidate_criteria input format), and side-effect semantics.

9. **`swing/data/ohlcv_archive.py`** + **`swing/web/ohlcv_cache.py`** + **`swing/data/repos/candidate_criteria.py`** — OHLCV archive read path + criterion persistence. V2 must reconstruct OHLCV bars at each candidate's historical `data_asof_date`; identify the read path + scope of currently-available historical data.

10. **`swing/data/migrations/0001_phase1_initial.sql`** + **`swing/data/migrations/*.sql`** — schema reference for `candidate_criteria` shape (cited in method-record §"Inputs"). Verify what fields each row carries + what the V2 harness can SELECT from.

11. **CLAUDE.md** at repo root — 16 cumulative gotchas. ESPECIALLY relevant for V2 harness:
    - **Expansion #10 sub-disciplines (gotcha #14)** — apply architecture-location audit; verify which module the V2 harness lives in vs depends on
    - **Expansion #11 (gotcha #15)** — taxonomy propagation audit; if V2 introduces a new dataclass enum (e.g., `evaluator_kind` for per-criterion-type evaluators), apply propagation discipline
    - **Expansion #4 refinement (gotcha #9 family)** — SQL skeleton column verification against actual migration files; verify every `candidate_criteria` column reference is correct
    - **`date.fromisoformat()` discipline (gotcha #12)** — for any cross-type-boundary call (TEXT `data_asof_date` → `date` parameter)
    - **Schema-CHECK vs Python-constant paired discipline (cumulative)** — V2 SHOULD NOT touch schema; if it must, paired discipline applies
    - **External-API empty-result transient defense (cumulative F6)** — OHLCV reconstruction may hit yfinance / Schwab boundaries; empty-result transient defense MUST apply

12. **`docs/orchestrator-context.md`** "Currently in-flight work" — Phase 13 FULLY CLOSED; T4.SB closer arc COMPLETE; Path B selected.

13. **V2.1 governance docs** at `reference/Future Work/2026-04-23-bifurcated-strategic-implementation-proposal-v2.1.md` + `reference/Future Work/2026-04-23-rebuttal-response-for-implementors.md` — V2.1 §IV.B minimum viable method-record field list + §IV.D + §VII.C lifecycle posture + §V branch posture. Required reading for any research-branch dispatch.

---

## §1 Mission scope

Brainstorm the V2 OHLCV criterion-evaluator harness design. Deliverable is a SPEC document, NOT an implementation. Per `copowers:brainstorming` workflow + cumulative precedent (T4.SB brainstorming spec at `4299340` per `docs/superpowers/specs/2026-05-22-phase13-t4-sb-closer-design.md` — 1045 lines, 13 sections §A-§M), the output spec MUST cover the following architectural questions explicitly:

### §1.1 Core questions to resolve

1. **OHLCV reconstruction scope** — V2 needs OHLCV bars at each candidate's historical `data_asof_date`. Three candidate strategies:
   - **(a) Limit to recent asof_dates** where OHLCV archive is known to have coverage; document scope reduction
   - **(b) Fetch-on-demand** via yfinance / Schwab (slow; rate-limit-bound)
   - **(c) Piggyback** on existing OhlcvArchive write path + accept gaps with explicit per-candidate skip
   - Spec must analyze each; recommend one; surface as OQ.
2. **Per-criterion evaluator interface** — V2 needs to evaluate ONE criterion at a time with a substituted threshold. Two candidate designs:
   - **(a) Mutate cfg dataclass** + invoke production criterion evaluator (high fidelity; per-cfg-instance cost)
   - **(b) Explicit override-dict** + per-criterion evaluator that consumes (bars, threshold, ...) (lower fidelity; flexible)
   - Spec must analyze; recommend one; surface as OQ.
3. **Sweep range strategy per variable** — V1 used 5-point heuristics keyed off variable kind. V2 has more freedom because LIVE recompute is possible. Three candidate strategies:
   - **(a) Inherit V1 5-point grid** — minimal change
   - **(b) Adaptive bisection** — find the threshold boundary that flips Watch→A+ for each candidate
   - **(c) Full-range fine-grained** — e.g., 20 points per variable across a defensible range
   - Spec must analyze; recommend one; surface as OQ.
4. **Output format** — V1 was 9-column CSV `(variable_name, kind, sweep_point, aplus_count, watch_count, skip_count, excluded_count, delta_aplus, delta_watch)` + markdown matrix. V2 has richer signal (per-candidate per-sweep-point flip). Three candidate formats:
   - **(a) Same shape as V1** + non-zero deltas for the 15 threshold rows
   - **(b) Per-candidate row format** showing which candidates flip at which thresholds
   - **(c) Hybrid** — V1 matrix at top + per-criterion drill-down sections
   - Spec must analyze; recommend one; surface as OQ.
5. **Scope discipline** — does V2 cover ALL 15 inert variables in one dispatch OR phased delivery? E.g., VCP variables first (8 of 15)? Spec must propose + surface as OQ.
6. **Validation universe** — V2 reuses the 5681 candidates / 63 eval_runs from S3 OR fresh fetch? Mention reproducibility implications.
7. **Cross-coupling** — V1 was 1D. V2 stays 1D (per cumulative V2.1 §IV.B parsimony) OR introduces pair-wise variables? Recommend (likely 1D; multi-D is V3+).
8. **Method-record promotion criteria** — what evidence is needed to promote `aplus-criteria-calibration` method-record from `status='research'` → `shadow` per V2.1 §IV.D? Spec MUST propose criteria.

### §1.2 Forward-binding from Path B disposition

- The first study output should answer the operator's motivating question: **"which of the 15 inert threshold variables are binding at the watch→A+ promotion boundary, ranked by marginal A+ count per loosening unit?"** Spec MUST design output to answer this directly.
- Downstream: if a binding threshold(s) is identified, the next research-branch dispatch drafts a cfg-policy method-record + operator-paired threshold-loosening evaluation against retained validation universe. Spec should ENABLE that downstream work via the output format chosen.

---

## §2 Substrate context

### §2.1 Research-branch posture

Per V2.1 §V:
- All V2 harness code lives under `research/` — NEW module under `research/harness/aplus_v2_ohlcv_evaluator/` (or operator-paired-named equivalent).
- Tests under `tests/research/` mirroring T-T4.SB.1 precedent.
- New study writeup at `research/studies/<date>-v2-ohlcv-criterion-evaluator.md` (companion to the existing `aplus-criterion-sensitivity-2026-05-22.md`).
- Method-record extension at `research/method-records/aplus-criteria-calibration.md` (NOT a new method-record; the V2 work LIVES UNDER the existing record per OQ-CL.3 LOCK).
- Production `swing/` code is READ-ONLY through this dispatch.

### §2.2 Schema discipline

V2 SHOULD NOT touch schema (per banked V2 dependency #2 — "Structured threshold columns on `candidate_criteria` for the 15 threshold variables" — that's V3+ work to push value substitution into SQL). If brainstorming surfaces an absolute necessity, §A.14 paired discipline applies + backup-gate strict-equality + migration runner discipline all apply per cumulative precedent.

### §2.3 V1 harness extension vs replacement

The V1 aplus_sensitivity harness at `research/harness/aplus_sensitivity/` stays as the GATE-VARIABLE assessment surface. V2 is a SEPARATE harness for THRESHOLD-VARIABLE assessment. The CLI `swing diagnose aplus-sensitivity` continues to invoke V1 for gate-only quick assessment; V2 ships under a NEW CLI (`swing diagnose aplus-sensitivity-v2` OR similar; spec proposes naming). Spec must surface the V1-vs-V2 dispatch surface design as an OQ.

### §2.4 Operator's V2.1 §VII.C lifecycle posture for the method-record

The existing method-record `aplus-criteria-calibration` is at `status='research'`. V2 OHLCV harness output is the evidence summary that operator + research branch evaluate for promotion to `shadow` (= produces shadow-tier proposals for cfg-policy without operator action) and eventually `production` (= cfg-policy automatically updated based on harness output). Spec must propose the evidence threshold for each promotion step.

---

## §3 Watch items + cumulative discipline (BINDING for brainstorming phase)

### §3.1 Pre-Codex 7-expansion + 5 NEW candidate refinements (31st cumulative C.C lesson #6 validation expected)

Brainstorming-phase pre-Codex review applies ALL 7 expansions + 5 NEW candidate refinements (last refinement is Expansion #12 candidate banked at T4.SB executing-plans):

1. **Expansion #1** — hardcoded-duplicate audit
2. **Expansion #2** — brief-vs-spec + brief-vs-actual schema verification
3. **Expansion #3** — schema-CHECK vs semantic-contract gap
4. **Expansion #4** — specific-scenario gotcha trace + SQL skeleton column verification
5. **Expansion #5** — cross-section spec inventory grep
6. **Expansion #6** — content-completeness audit
7. **Expansion #7** — cross-row semantic SCOPE audit + scope-vs-unit boundary
8. **Expansion #8 candidate** — per-aggregation-function UNIT audit on SQL skeletons
9. **Expansion #9 candidate** — form-render anchor lifecycle 4-dimension audit (LIKELY N/A; no web routes in V2 harness scope)
10. **Expansion #10 candidate** — Architecture-location audit + 5 sub-disciplines (apply to NEW `research/harness/aplus_v2_ohlcv_evaluator/` module placement + per-criterion evaluator architecture)
11. **Expansion #11 candidate** — Taxonomy propagation audit (apply if V2 introduces NEW enum-typed dataclass field; e.g., `evaluator_kind` or `bucket_recompute_path`)
12. **Expansion #12 candidate (NEW BINDING for 31st cumulative validation onwards)** — Sibling-route audit when introducing single-anchor-binding discipline (LIKELY N/A; no route handlers in V2 harness scope)

### §3.2 Cumulative gotcha set (16 cumulative)

Per CLAUDE.md updates through `2a56158`+`f1044ee` (gotchas #9-#16):
- (9) SQL aggregation UNIT audit
- (10) Existing-field reuse audit
- (11) Template-rendering surface audit (N/A; no templates)
- (12) `date.fromisoformat()` cross-type-boundary discipline (DIRECTLY APPLIES — `candidate_criteria.data_asof_date` is TEXT)
- (13) Form-render anchor lifecycle (N/A; no forms)
- (14) Architecture-location 5-sub-discipline (DIRECTLY APPLIES — new module + per-criterion evaluator)
- (15) Taxonomy propagation (apply if introducing NEW enum)
- (16) Sibling-route audit (N/A; no routes)

### §3.3 Cumulative process discipline

- **NO Co-Authored-By footer** — ~433+ cumulative streak through `b4d7719`. Cite per fresh forward-binding lesson #7 (Phase 12 Sub-sub-bundle C.B 2026-05-15) in every commit message.
- **`python -m swing.cli` from worktree cwd**, NOT bare `swing`
- **ASCII-only on runtime CLI paths**
- **TDD per task** via `superpowers:test-driven-development` (for tests planted in brainstorming spec)
- **Edit tool for per-file edits**
- **Cite the discipline in commit messages**

### §3.4 Research-branch tests live under tests/research/

Mirror T-T4.SB.1 precedent: `tests/research/test_aplus_sensitivity_*.py` exists; V2 tests at `tests/research/test_aplus_v2_ohlcv_*.py` (or similar).

### §3.5 Schema is LOCKED

v21 is the locked schema. V2 SHOULD NOT touch migrations. If brainstorming surfaces absolute necessity, surface as OQ + apply paired discipline.

### §3.6 OHLCV archive coverage is a real constraint

S3 used 5681 candidates across 63 eval_runs (~3 months of trading-day eval_runs). V2 needs OHLCV bars at each candidate's `data_asof_date`. The OhlcvArchive write path at `swing/data/ohlcv_archive.py` writes per-ticker parquet files keyed on `(ticker, source)` per the existing F6 transient-empty defense. Spec must address: (a) is archive coverage validated for the candidate universe? (b) what's the failure mode if a ticker is missing OR has gaps? (c) is per-criterion evaluation robust to incomplete bar windows (e.g., needs 200+ bars for MA200 but only 150 available)?

---

## §4 Done criteria for brainstorming output

The spec at `docs/superpowers/specs/<date>-v2-ohlcv-criterion-evaluator-design.md` (or operator-paired-named equivalent; suggested name: `2026-05-23-v2-ohlcv-criterion-evaluator-design.md`) MUST cover:

- [ ] **§A Status + scope** — research-branch positioning (V2.1 §V) + first deliverable under existing `aplus-criteria-calibration` method-record (NOT new method-record) per OQ-CL.3 LOCK
- [ ] **§B Research question + S3 findings inheritance** — 15 inert threshold variables enumerated verbatim from S3; operator motivating question; per-variable hypothesis for which might be binding
- [ ] **§C V2 OHLCV evaluator architecture** — module placement (new `research/harness/aplus_v2_ohlcv_evaluator/`); per-criterion evaluator interface; integration with `bucket_for` end-to-end
- [ ] **§D Per-criterion evaluator design** — one evaluator per criterion class (trend_template / vcp / risk / rs); cfg-substitution interface decision (mutate vs override-dict per OQ-2); bars input + threshold input → criterion outcome
- [ ] **§E Bucket_for recomputation end-to-end** — how the harness invokes `bucket_for` with substituted threshold cfg; preserves `allowed_miss_names` + `min_passes` invariants; produces bucket-redistribution counts mirror to V1 gate-row semantics
- [ ] **§F OHLCV archive reconstruction strategy** — decision on OQ-1 (limit-to-recent vs fetch-on-demand vs piggyback); coverage validation approach
- [ ] **§G Output format** — decision on OQ-4; sensitivity-matrix shape; per-criterion drill-down (if applicable); CSV + markdown structure
- [ ] **§H Test scope projection** — per-task test budget; mirror T-T4.SB.1 budget of ~30-40 tests; baseline 5778 + V2-test bump; pin un-skip schedule if any
- [ ] **§I OQs surfaced** — all 8+ open questions enumerated for operator-paired triage between brainstorming + writing-plans phases
- [ ] **§J Forward-binding lessons inherited** — T4.SB executing-plans Lesson #1-5; 16 cumulative gotchas; pre-Codex 7-expansion + 5 candidate refinements (#10 + #11 + #12 most relevant)
- [ ] **§K Method-record extension to `aplus-criteria-calibration.md`** — propose new sections to add (V2-shipped semantics; promotion-evidence criteria for research→shadow→production lifecycle per V2.1 §VII.C)
- [ ] **§L Cross-references + V2.1 governance citations** — §V branch posture; §IV.D + §VII.C lifecycle posture; §IV.B minimum viable method-record fields
- [ ] **§M Dispatch sequence** — propose number of sub-bundles for executing-plans phase (e.g., per-criterion-class batches: trend_template + vcp + risk + rs); concurrent-dispatch potential

Plan-phase Codex chain expected 2-5 rounds. Pre-Codex 7-expansion + 5 NEW candidate refinements + 16 cumulative gotchas discipline BINDING; verdict per expansion captured in plan-phase return report. **31st cumulative C.C lesson #6 validation expected.**

---

## §5 References

- **Method-record (PRIMARY substrate)**: [`research/method-records/aplus-criteria-calibration.md`](research/method-records/aplus-criteria-calibration.md) at main HEAD
- **Triage agenda (Path B LOCKED)**: [`docs/phase13-closer-next-phase-triage.md`](docs/phase13-closer-next-phase-triage.md) at `b4d7719`
- **S3 sensitivity-harness output**: `exports/diagnostics/aplus-sensitivity-20260523T065514Z.md` + `.csv`
- **V1 study writeup**: [`research/studies/aplus-criterion-sensitivity-2026-05-22.md`](research/studies/aplus-criterion-sensitivity-2026-05-22.md)
- **V1 harness implementation**: [`research/harness/aplus_sensitivity/`](research/harness/aplus_sensitivity/) (4 files)
- **Research-branch precedent**: [`research/harness/earnings_proximity/`](research/harness/earnings_proximity/) + [`research/studies/earnings-proximity-exclusion.md`](research/studies/earnings-proximity-exclusion.md) + [`research/method-records/earnings-proximity-exclusion.md`](research/method-records/earnings-proximity-exclusion.md)
- **Method-record template**: [`research/method-records/_template.md`](research/method-records/_template.md)
- **Production `bucket_for`**: `swing/evaluation/scoring.py`
- **OHLCV archive**: `swing/data/ohlcv_archive.py` + `swing/web/ohlcv_cache.py`
- **candidate_criteria repo**: `swing/data/repos/candidate_criteria.py` + migrations `0001_phase1_initial.sql`
- **CLAUDE.md** at repo root (16 cumulative gotchas; #14 + #15 most relevant to V2 design)
- **V2.1 governance**: [`reference/Future Work/2026-04-23-bifurcated-strategic-implementation-proposal-v2.1.md`](reference/Future Work/2026-04-23-bifurcated-strategic-implementation-proposal-v2.1.md) + [`reference/Future Work/2026-04-23-rebuttal-response-for-implementors.md`](reference/Future Work/2026-04-23-rebuttal-response-for-implementors.md)
- **T4.SB return reports** (cumulative discipline lineage):
  - `docs/phase13-t4-sb-brainstorm-return-report.md` (T4.SB brainstorming)
  - `docs/phase13-t4-sb-writing-plans-return-report.md` (T4.SB writing-plans)
  - `docs/phase13-t4-sb-executing-plans-return-report.md` (T4.SB executing-plans; 5 forward-binding lessons banked)

---

## §6 NON-scope (V3+ / future arc; explicitly out of V2 OHLCV harness)

- **Schema changes** — `candidate_criteria` structured threshold columns is V3+ work per existing method-record V2 dependency #2
- **Multi-D sensitivity sweep** — pair-wise variable interaction is V3+ per V2.1 §IV.B parsimony
- **cfg-policy automation** — automatic cfg updates based on harness output is post-promotion-to-`production` lifecycle work; V2 ships at `status='research'` per V2.1 §IV.D
- **Phase 14 commissioning** — deferred per OQ-CL.2 LOCK until V2 outputs inform operational scope
- **V2.G1-G4 operator gate bug investigations** — deferred per operator decision 2026-05-23 PM (worked AFTER Applied Research tasking per operator direction; banked at `docs/phase3e-todo.md` §"Post-T4.SB-SHIPPED operator gate feedback")
- **Production swing/ code changes** — V2 harness is research-branch only; production stack stable through V2 dispatch

---

## §7 Post-brainstorming handback

When brainstorming Codex chain converges to NO_NEW_CRITICAL_MAJOR:

1. **Write return report** at `docs/v2-ohlcv-criterion-evaluator-brainstorm-return-report.md` per cumulative precedent. Cover:
   - Commit chain shape (1 initial spec + N Codex fix bundles + 1 return report)
   - Per-task Codex chain shape per round (C/M/m counts; resolution commits)
   - 31st cumulative C.C lesson #6 validation result per-expansion (7 expansions + 5 NEW candidate refinements)
   - Forward-binding lessons banked (for future research-branch arcs OR future writing-plans phase)
   - V1 simplifications + V2/V3 candidates banked (with V2/V3 dependency cited)
   - Cumulative streaks preserved (ZERO Co-Authored-By; schema v21 LOCKED; baseline 5778 fast tests UNCHANGED through brainstorming docs-only phase)
   - OQ enumeration ready for operator-paired triage
2. **Inline self-verification**:
   - Ruff check returns clean (research/ + new files)
   - Schema unchanged at v21
   - Test baseline matches pre-brainstorming (5778 fast tests; brainstorming is docs-only)
3. **Hand back to operator** with summary + OQ list ready for triage.

### §7.1 Orchestrator-side next steps post-brainstorming

- QA implementer product per `feedback_orchestrator_qa_implementer_product` BINDING (verify file:line + shipped-behavior + cumulative gotcha citations against reality on disk)
- Merge `applied-research-v2-ohlcv-criterion-evaluator-brainstorm` `--no-ff` to `main`; push
- Post-merge housekeeping bundle (CLAUDE.md line 3 refresh — Applied Research arc IN-FLIGHT pivot post-Phase-13-closed + any NEW gotchas if any + phase3e-todo.md NEW top entry + orchestrator-context.md current state refresh + Prior demote + archive-split per size-check trigger)
- **Operator-paired OQ triage session** (8+ OQs surfaced per §1.1)
- Draft writing-plans dispatch brief consuming the operator-affirmed brainstorming spec + OQ dispositions
- Provide inline implementer dispatch prompt for writing-plans phase

---

*End of V2 OHLCV criterion-evaluator harness brainstorming dispatch brief. First Applied Research arc post-Phase-13-FULLY-CLOSED. Path B LOCKED per operator decision 2026-05-23 PM. Banked V2 dependency #1 from existing `aplus-criteria-calibration` method-record is the deliverable target. ~433+ ZERO Co-Authored-By footer streak preserved through triage-agenda update at `b4d7719`. 31st cumulative C.C lesson #6 validation expected at brainstorming handback with all 7 expansions + 5 NEW candidate refinements + 16 cumulative gotchas BINDING.*
