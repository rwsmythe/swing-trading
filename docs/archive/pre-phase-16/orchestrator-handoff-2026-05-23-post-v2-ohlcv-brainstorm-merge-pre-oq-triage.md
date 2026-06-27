# Orchestrator handoff — 2026-05-23 (post-V2-OHLCV-brainstorming-merge + post-housekeeping; pre-18-OQ-triage)

You are taking over as orchestrator (Turn D) for the Swing Trading project at the **post-V2-OHLCV-brainstorming-merge + post-housekeeping + pre-18-OQ-operator-paired-triage** breakpoint. Context-limit transition from Turn C (which exited after completing housekeeping bundle; Turn C absorbed Turn B's full sequence + V2 OHLCV brainstorming handback + merge + 4-file housekeeping).

**main HEAD AT HANDOFF**: `bd08644` (post-V2-OHLCV-brainstorming-merge housekeeping bundle committed + pushed). Pending: this handoff-brief commit itself, which becomes the new HEAD before Turn D reads this.

**WORKING DIRECTORY**: `c:\Users\rwsmy\swing-trading`

**CRITICAL FIRST TASKS** (in order):
1. Read this brief end-to-end + `CLAUDE.md` line 3 + `docs/orchestrator-context.md` "Currently in-flight work" section + V2 OHLCV brainstorming spec at `docs/superpowers/specs/2026-05-23-v2-ohlcv-criterion-evaluator-design.md` §I (lines 731-865; the 18 OQs Turn D must drive through operator-paired triage).
2. **Operator-paired 18-OQ triage session via AskUserQuestion** (chunked across 4-5 rounds since AskUserQuestion supports max 4 questions per call). Each OQ disposition LOCKED becomes a binding constraint for the writing-plans dispatch brief.
3. **Draft V2 OHLCV writing-plans dispatch brief** at `docs/v2-ohlcv-criterion-evaluator-writing-plans-dispatch-brief.md` (12 sections §0-§8 mirroring T4.SB writing-plans precedent) consuming operator-affirmed brainstorming spec + 18 OQ dispositions.
4. **Commit brief BEFORE inline prompt** per `feedback_commit_brief_before_inline_prompt` BINDING memory + provide inline implementer dispatch prompt as fenced code block per `feedback_always_provide_inline_dispatch_prompt` BINDING.
5. **Context-budget watch**: V2 OHLCV writing-plans dispatch is the SECOND of three Applied Research arcs; if Turn D's context exhausts mid-OQ-triage OR mid-brief-drafting, author Turn E handoff brief BEFORE letting context exhaust.

---

## §0 Critical bootstrap framing (memory entries; ALL BINDING)

- `feedback_pause_means_pause.md`
- `feedback_worktree_cli_invocation.md` — `python -m swing.cli` from worktree cwd, NOT bare `swing`
- `feedback_time_estimates_overstated.md` — divide by 3-5x for operator-paced wall-clock
- `feedback_orchestrator_qa_implementer_product.md` — QA every implementer product against reality on disk
- `feedback_orchestrator_performs_merge.md` — merge + push + post-merge housekeeping = orchestrator action
- `feedback_orchestrator_vs_implementer_execution.md` — default to implementer-dispatch for context budget
- `feedback_always_provide_inline_dispatch_prompt.md` — every brief gets inline dispatch prompt as fenced code block
- `feedback_commit_brief_before_inline_prompt.md` — commit brief BEFORE providing inline prompt
- `feedback_regression_test_arithmetic.md`

**Operator dispatches implementers themselves** (durable). Orchestrator drafts brief + provides inline dispatch prompt as fenced code block.

**NO Claude co-author footer**. Cumulative streak **~438+ commits ZERO trailer drift** through housekeeping `bd08644`. Cite per fresh forward-binding lesson #7 (Phase 12 Sub-sub-bundle C.B 2026-05-15) in every commit message.

---

## §1 Cumulative state at handoff

### Test + schema baseline
- **5778 fast tests** / 1 skipped / 0 failed (main HEAD at handoff `bd08644`; UNCHANGED since T4.SB executing-plans SHIPPED at `2a56158`; V2 OHLCV brainstorming + housekeeping are docs-only)
- Ruff clean (0 E501) / **schema v21** UNCHANGED (V2 OHLCV is research-branch; SHOULD NOT touch schema)
- ZERO new Schwab API calls (L2 LOCK preserved + REINFORCED via spec's `ohlcv_reader.py` file-open mock discriminating test)
- **~438+ cumulative ZERO `Co-Authored-By` trailer drift** through these dispatches

### Recent commits on main (last 8)

| SHA | Purpose |
|---|---|
| (TBD) | Orchestrator handoff brief (this file's commit) |
| `bd08644` | Post-V2-OHLCV-brainstorming-merge housekeeping bundle (4 files; CLAUDE.md line-3 pivot + 2 NEW gotchas #17+#18 + phase3e-todo + orchestrator-context pivot + archive-split) |
| `362fe18` | Merge applied-research-v2-ohlcv-criterion-evaluator-brainstorm --no-ff (7 implementer commits; spec 1086 lines NEW + return report 221 lines NEW) |
| `acaf305` | V2 OHLCV criterion-evaluator harness brainstorming dispatch brief (263 lines; first Applied Research arc dispatch) |
| `b4d7719` | Phase 13 closer triage agenda RESOLVED — Path B (Applied Research focus) LOCKED per operator decision 2026-05-23 PM |
| `edbf4af` | V2.G1-G4 operator gate feedback banked in phase3e-todo (deferred per operator decision 2026-05-23 PM until Applied Research tasking completes) |
| `f1044ee` | Post-T4.SB-executing-plans-merge orchestrator-side housekeeping bundle (3 files; gotcha #16 + Prior #11 archive-split) |
| `2a56158` | Merge phase13-t4-sb-executing-plans --no-ff (T4.SB EXECUTING-PLANS SHIPPED — Phase 13 FULLY CLOSED, 12 of 12 sub-bundles) |

### Applied Research Tranche 1 dispatch sequence remaining
```
V2 OHLCV brainstorming SHIPPED (362fe18; THIS pass) → housekeeping (bd08644; THIS pass) → handoff (this commit) → Turn D (YOU): 18-OQ operator-paired triage → V2 OHLCV writing-plans dispatch brief → writing-plans implementer ships → Turn E (maybe separate from D per context-budget watch): QA + merge + housekeeping + draft executing-plans brief + inline prompt → V2 OHLCV executing-plans implementer ships → Turn F (maybe separate): QA + merge + housekeeping + V2 harness output review → operator review of harness output → optional cfg-policy method-record + Phase 14 commissioning consideration
```

**Phase 13 FULLY CLOSED at `2a56158` 2026-05-22 PM #4**; Applied Research Tranche 1 arc IN-FLIGHT (brainstorming SHIPPED `362fe18` 2026-05-23; writing-plans + executing-plans remain).

---

## §2 What just shipped (V2 OHLCV brainstorming this orchestrator session)

### §2.1 V2 OHLCV brainstorming SHIPPED at `362fe18`

- **Spec**: `docs/superpowers/specs/2026-05-23-v2-ohlcv-criterion-evaluator-design.md` (1086 lines; 14 sections §A-§N)
- **Return report**: `docs/v2-ohlcv-criterion-evaluator-brainstorm-return-report.md` (221 lines)
- **7-commit dispatch**: 1 initial spec at `dd6beac` + 5 Codex MCP fix bundles at `c7f2a3c` + `5bb2640` + `5be32d2` + `c9e540e` + `1efec56` + 1 return report at `8532949`
- **Codex chain converged R5 NO_NEW_CRITICAL_MAJOR after 5 rounds** (R1: 2C/6M/1m; R2: 1C/6M/2m; R3: 0C/2M/3m; R4: 0C/3M/3m; R5: 0C/0M/2m doc-drift; **3 CRITICAL + 17 MAJOR + 13 MINOR ALL RESOLVED in-place**; ZERO accepted-as-rationale)
- **31st cumulative C.C lesson #6 validation NOTABLE** (Expansions #10 + #11 CLEAN; NEW Expansion #2 + #4 refinements banked → CLAUDE.md gotchas #17 + #18 appended this housekeeping)
- **5 architectural recommendations LOCKED** (see §2.2 below)
- **18 OQs surfaced** (see §2.3 below — Turn D drives operator-paired triage)

### §2.2 5 architectural recommendations LOCKED in spec

1. **OHLCV reader** = NEW read-only `research/harness/aplus_v2_ohlcv_evaluator/ohlcv_reader.py` bypasses `read_or_fetch_archive`; reads Shape A `{ticker}.yfinance.parquet` directly (legacy `{ticker}.parquet` fallback); NEVER opens `schwab_api` parquet (L2 LOCK preserved + REINFORCED by file-open mock discriminating test)
2. **Interface** = cfg-substitution via `dataclasses.replace` + production `evaluate_one(ctx)` end-to-end; `vcp.watch_max_fails` special-case mirrors V1
3. **Sweep** = V1 5-point grid inherited; 1D per V2.1 §IV.B parsimony
4. **Output** = hybrid V1 12-col matrix + headline + per-variable drill-down + V1↔V2 parity section + both-exist diagnostic banner
5. **Scope** = ALL 15 inert threshold variables in one dispatch; reuse S3's 5681/63 universe

These are LOCKED; do NOT re-litigate in OQ triage. They are the foundation upon which the 18 OQs build.

### §2.3 18 OQs surfaced (Turn D drives operator-paired triage)

Per spec §I (lines 731-865); enumerated headers:

| # | Spec line | OQ header |
|---|---|---|
| OQ-1 | 735 | OHLCV reconstruction scope |
| OQ-2 | 741 | Per-criterion evaluator interface |
| OQ-3 | 747 | Sweep range strategy per variable |
| OQ-4 | 753 | Output format |
| OQ-5 | 759 | Scope discipline |
| OQ-6 | 765 | Validation universe |
| OQ-7 | 771 | Cross-coupling |
| OQ-8 | 777 | Method-record promotion criteria |
| OQ-9 (NEW substrate) | 787 | Performance budget cap |
| OQ-10 (NEW substrate) | 793 | V2 CLI surface name |
| OQ-11 (NEW substrate) | 799 | `vcp.watch_max_fails` hardcode handling |
| OQ-12 (NEW substrate) | 805 | Schwab API L2 LOCK preservation |
| OQ-13 (NEW substrate) | 811 | OHLCV coverage failure attribution mode |
| OQ-14 (Codex C1 NEW) | 817 | RS universe reconstruction strategy at historical asof_date |
| OQ-15 (Codex C2 NEW) | 827 | `current_equity` surrogate for risk gate recompute |
| OQ-16 (Codex M1+M2 NEW) | 837 | OHLCV archive read strategy — fetch path vs read-only |
| OQ-17 (Codex M6 NEW) | 847 | CLI subcommand registration as the read-only carve-out |
| OQ-18 (Codex R3.M1 NEW) | 853 | Both-exist legacy/Shape A archive read policy |

**Turn D MUST read spec §I end-to-end** to understand each OQ's disposition options + recommended-default before driving AskUserQuestion. Some OQs have orchestrator-recommendations the operator may simply concur with; some have multiple competing options. Several depend on each other (e.g., OQ-14 RS universe interacts with OQ-15 current_equity surrogate; OQ-16 OHLCV strategy interacts with OQ-18 both-exist policy).

### §2.4 NEW CLAUDE.md gotchas appended this housekeeping (#17 + #18)

- **#17 — Expansion #2 refinement: brief-vs-actual-production-function-signature verification**. Surfaced via Codex R1.M1 + R1.M2 catching the `read_or_fetch_archive(prefer_source=...)` kwarg-doesn't-exist + active-fetch-vs-read-only mismatch. Pre-empt: any brief/spec proposing a production function invocation MUST grep the function definition + verify signature + side-effect contract + error semantics.
- **#18 — Expansion #4 refinement: SQL skeleton JOIN-cardinality + downstream-sufficiency audit**. Surfaced via Codex R1.C1 + R4.M2 catching candidate-only-universe-vs-RS-full-universe + post-cleanup re-check missing. Pre-empt: any SQL skeleton MUST enumerate consumer's required row-set scope + JOIN-cardinality 1:1 vs 1:N + downstream-sufficiency + post-mutation re-check semantics.

Both BINDING for 32nd cumulative C.C lesson #6 validation onwards. Turn D should apply both in pre-Codex review of the writing-plans dispatch.

---

## §3 What YOU (Turn D orchestrator) MUST do

### §3.1 Operator-paired 18-OQ triage session

**Strategy**: chunk via AskUserQuestion 4-Q-per-call max. Likely 5 rounds:
- Round 1: OQ-1 + OQ-2 + OQ-3 + OQ-4 (4 core architecture questions inherited from dispatch brief §1.1)
- Round 2: OQ-5 + OQ-6 + OQ-7 + OQ-8 (4 remaining core questions)
- Round 3: OQ-9 + OQ-10 + OQ-11 + OQ-12 (4 NEW substrate-surfaced)
- Round 4: OQ-13 + OQ-14 + OQ-15 + OQ-16 (4 mixed substrate + Codex-surfaced)
- Round 5: OQ-17 + OQ-18 (2 final Codex-surfaced)

Per AskUserQuestion best-practice: include **orchestrator recommendation as first option labeled "(Recommended)"** for each OQ. The spec §I has the recommendations + tradeoffs enumerated; Turn D extracts each OQ's recommendation + 2-3 competing options for the AskUserQuestion options[] array.

**LOCK each OQ disposition** as it's answered — these become the binding constraints for the writing-plans dispatch brief §1 OQ dispositions section (mirror T4.SB writing-plans brief §1 structure).

### §3.2 Draft V2 OHLCV writing-plans dispatch brief

Target path: `docs/v2-ohlcv-criterion-evaluator-writing-plans-dispatch-brief.md`. Target structure (12 sections §0-§8) mirroring T4.SB writing-plans precedent at `docs/phase13-t4-sb-writing-plans-dispatch-brief.md` (295 lines):
- §0 Read first (spec at HEAD `362fe18` is PRIMARY substrate; CLAUDE.md 18 gotchas including #17 + #18; method-record `aplus-criteria-calibration.md` with 3-tier promotion ladder + baseline parity discipline shipped at brainstorming; V2.1 governance docs)
- §1 18 OQ dispositions verbatim (LOCKED per Turn D's operator-paired triage session)
- §1.5 amendments if operator surfaces any during triage (§1.5.1+ per cumulative T2.SB6c + T4.SB precedent)
- §2 Scope inheritance from brainstorming spec (15 inert threshold variables; cfg-substitution interface; output format; OHLCV reader carve-out; etc.)
- §3 Watch items: pre-Codex 7 expansions + 5 NEW candidate refinements + Expansion #2 + #4 refinements BINDING + 18 cumulative gotchas BINDING for 32nd cumulative validation
- §4 Per-task acceptance criteria (writing-plans phase target = plan §G in spec at `2026-05-23-v2-ohlcv-criterion-evaluator-design.md` — likely 4-6 sub-bundle tasks per spec §M dispatch sequence proposal)
- §5 Done criteria for writing-plans output
- §6 References
- §7 NON-scope (V3+; Phase 14; V2.G1-G4 still deferred)
- §8 Post-writing-plans handback (Turn E orchestrator: QA + merge + housekeeping + draft executing-plans brief)

### §3.3 Commit brief BEFORE inline prompt

Per `feedback_commit_brief_before_inline_prompt` BINDING memory.

### §3.4 Provide inline implementer dispatch prompt

Per `feedback_always_provide_inline_dispatch_prompt` BINDING. Fenced code block; operator copy/pastes into fresh implementer session.

### §3.5 Context-budget watch

V2 OHLCV writing-plans implementer dispatch will be operator-side; when handback arrives, Turn E (or Turn D continuation if context allows) does QA + merge + housekeeping. If Turn D's context drops below ~30% during OQ triage OR brief drafting, author Turn E handoff brief at `docs/orchestrator-handoff-<date>-post-v2-ohlcv-writing-plans-dispatch-pre-handback.md` BEFORE letting context exhaust.

---

## §4 Operator-pending items (NOT orchestrator-blocking; surface in operator update post-OQ-triage-LOCK)

- **V2.G1-G4 operator gate bug investigations** — STILL DEFERRED per operator decision 2026-05-23 PM (work AFTER Applied Research tasking completes). Banked at `docs/phase3e-todo.md` §"Post-T4.SB-SHIPPED operator gate feedback (V2 backlog; 2026-05-23)".
- **Phase 14 commissioning** — DEFERRED until V2 OHLCV harness output informs operational scope per Path B sequencing.
- **Worktree husks**: `.worktrees/applied-research-v2-ohlcv-criterion-evaluator-brainstorm` (post-Turn-C merge). Operator runs `cleanup-locked-scratch-dirs.ps1 -DeregisterFirst` when convenient.
- **Schwab refresh-token clock**: renew via `swing schwab logout` → `swing schwab setup` when ≤24h remaining.

---

## §5 Cumulative streaks to preserve

- **ZERO `Co-Authored-By` footer trailer drift**: ~438+ commits cumulative through `bd08644`. ABSOLUTELY DO NOT regress.
- **C.C lesson #6 cumulative validations**: 22x CLEAN through T3.SB3 → 23rd-30th NOTABLE through Phase 13 closer arc → 31st NOTABLE V2 OHLCV brainstorming (Expansions #10 + #11 CLEAN first clean-on-arrival; NEW Expansion #2 + #4 refinements banked as gotchas #17 + #18). **32nd expected at V2 OHLCV writing-plans handback** with all 7 expansions + 5 NEW candidate refinements (#4 SQL-column + #8 SQL-unit + #9 form-anchor + #10 architecture-location + #11 taxonomy + NEW #2-refinement + NEW #4-refinement) + 18 cumulative gotchas BINDING.
- **Schema v21 LOCKED**: through Applied Research Tranche 1 arc per spec §A scope.
- **ZERO new Schwab API calls** (L2 LOCK preserved + REINFORCED through V2 OHLCV harness via `ohlcv_reader.py` carve-out).
- **5778 fast tests baseline** — UNCHANGED through brainstorming + housekeeping (docs only); V2 ship projection +68 tests at executing-plans.

---

## §6 Quick-reference SHA roster

| Item | SHA |
|---|---|
| main HEAD at this handoff write-time | `bd08644` (post-V2-OHLCV-brainstorming-merge housekeeping) |
| Handoff brief commit (this file) | TBD on commit |
| V2 OHLCV brainstorming merge | `362fe18` |
| V2 OHLCV brainstorming dispatch brief | `acaf305` |
| Phase 13 triage RESOLVED — Path B LOCKED | `b4d7719` |
| V2.G1-G4 banked | `edbf4af` |
| T4.SB executing-plans + Phase 13 FULLY CLOSED merge | `2a56158` |
| T4.SB writing-plans merge | `9b2a4db` |
| T4.SB brainstorming merge | `4299340` |
| T-T4.SB.6 closer commit (Phase 13 FULLY CLOSED marker landed) | `c62fd98` |
| T-T4.SB.6 triage-agenda artifact stub | `5d6f613` |

---

## §7 Suggested first session flow (Turn D)

1. Read this brief end-to-end
2. Read `CLAUDE.md` line 3 (current state at HEAD `bd08644`)
3. Read `docs/v2-ohlcv-criterion-evaluator-brainstorm-return-report.md` (221 lines; cumulative discipline + 18 OQs summary)
4. Read V2 OHLCV brainstorming spec at `docs/superpowers/specs/2026-05-23-v2-ohlcv-criterion-evaluator-design.md` — ESPECIALLY §I OQs (lines 731-865) + §A-§F (architecture decisions LOCKED) + §M dispatch sequence proposal
5. Drive operator-paired 18-OQ triage per §3.1 (5 rounds of AskUserQuestion)
6. Draft V2 OHLCV writing-plans dispatch brief per §3.2
7. Commit brief per §3.3 + provide inline prompt per §3.4
8. Context-budget check per §3.5

Estimated wall-clock: ~2-4 hours orchestrator-paced for the full Turn D sequence (heavy because 18-OQ triage is rare scale; the OQ enumeration + per-OQ AskUserQuestion authoring + binding LOCK + brief drafting all consume context).

---

## §8 Do NOT

- Re-litigate the 5 LOCKED architectural recommendations (OHLCV reader carve-out + cfg-substitution interface + 1D 5-point grid + hybrid output + 15-variable-in-one-dispatch scope) — those were settled at brainstorming Codex chain
- Skip operator-paired OQ triage (18 OQs MUST be LOCKED per operator decisions before writing-plans dispatch)
- Modify the brainstorming spec in-place — amendments go in writing-plans dispatch brief as §1.5.1+ sections (mirror T2.SB6c + T4.SB precedent)
- Add Co-Authored-By footer to ANY commit (~438+ streak)
- Skip pre-Codex orchestrator-side review at writing-plans phase (32nd cumulative validation expected with all 7 expansions + 5 NEW candidate refinements (#4 + #8 + #9 + #10 + #11 + NEW #2-refinement + NEW #4-refinement) + 18 cumulative gotchas BINDING)
- Skip size-check pre-flight before housekeeping (was 10 at this commit; demote at writing-plans merge brings to 11; archive-split needed)
- Push without verifying empty Co-Authored-By trailer on commits
- Commission V2.G1-G4 operator gate bug work — STILL DEFERRED per operator decision 2026-05-23 PM
- Commission Phase 14 — DEFERRED until V2 OHLCV harness output informs operational scope per Path B sequencing

---

*End of orchestrator handoff brief. Post-V2-OHLCV-brainstorming-merge + post-housekeeping + pre-18-OQ-triage transition. Next orchestrator (Turn D): operator-paired 18-OQ triage → writing-plans dispatch brief drafting → commit-before-inline + inline prompt → context-budget watch. ~438+ cumulative ZERO Co-Authored-By trailer drift preserved through this handoff write-time. Applied Research Tranche 1 arc IN-FLIGHT (brainstorming SHIPPED `362fe18` 2026-05-23; writing-plans + executing-plans remain). 32nd cumulative C.C lesson #6 validation expected at writing-plans handback with NEW gotchas #17 + #18 BINDING.*
