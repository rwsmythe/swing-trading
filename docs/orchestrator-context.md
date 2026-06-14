# Orchestrator Context — Persistent Handoff File

**Audience:** Future orchestrator-role Claude sessions for the Swing Trading project. Also useful as a reference when the current orchestrator's context window is compacted.
**Purpose:** Provide enough context to bootstrap an orchestrator role without re-reading conversation history. Not a complete project spec — pointers to authoritative sources are throughout.
**Last updated:** 2026-05-24 PM (Phase 13 `_step_pattern_detect` silent no-op investigation SHIPPED at merge `54bd9c6` — diagnostic-only; H7 NEW root cause CONFIRMED = empty-pool early-return at `runner.py:1485-1490` gated on `bucket == 'aplus'` predicate; ZERO aplus across 7 post-T2.SB3 runs; detector code FULLY OPERATIONAL; H5 confirmed CONTRIBUTING operational gap; **architectural insight: production detector by design only runs on aplus candidates → operator's loosened-A+ hypothesis cannot be tested via production pipeline; Option D cohort-detection harness is the architecturally correct path**; **NEW CLAUDE.md gotcha #27 banked** = silent-skip-without-audit pattern in pipeline steps; **brief-framing accuracy lesson banked: dispatch briefs MUST verify "since X shipped" claims against `git log` of cited commit** — investigation brief framed "78 runs since T2.SB3" but actual was 7 post-ship runs; operator decisions LOCKED = Option A + D + gotcha #27 promote + brief-framing lesson concur). Previous: 2026-05-24 PM (Applied Research Tranche 1 V2 OHLCV full-63-eval-run reproduction CRITERION DRIFT investigation SHIPPED at merge `c8f9612` — 1 investigation commit + findings doc + return report; H6 NEW root cause CONFIRMED: archive bar-content TEMPORAL mutation between V1 persistence + V2 read times via `swing/data/ohlcv_archive.py:write_window:358-360` drop_duplicates `keep='last'` semantics; V2 evaluator CORRECT given inputs via decisive counter-test reproducing V2's bucket exactly for all 14 drift entries; THIRD investigation in a row to confirm V2 evaluator correctness; drift L4-style; 14 candidates flip skip→watch only so max_delta_aplus column UNAFFECTED; **all 5 binding variables ROBUST**: `vcp.tightness_range_factor` +75, `vcp.tightness_days_required` +16, `vcp.adr_min_pct` +11, `vcp.proximity_max_pct` +5, `vcp.orderliness_max_bar_ratio` +1 — all VCP-family; **study publication UNBLOCKED**; Option A RECOMMENDED (characterize as L6 limitation + NEW gotcha #26 + study writeup caveat; THIS housekeeping pass); NEW CLAUDE.md gotcha #26 banked (archive bar-content TEMPORAL mutation; complements #24 + #25; three-piece V1-vs-V2 parity discipline family); method-record v0.2.1 → v0.2.2 amendment with L6; research→shadow promotion gate condition-1 interpretation OPERATOR-PAIRED; ~505+ ZERO Co-Authored-By trailer streak preserved). Previous: 2026-05-24 (Option A baseline-parity sentinel-bucket filter SHIPPED at `b7f70ff`; Tier-1 FULL PASS on 5-eval-run smoke; D.3 method-record v0.2.0 → v0.2.1 with L4 + L5). Previous: 2026-05-22 PM #4 (Phase 13 T4.SB EXECUTING-PLANS SHIPPED — T-T4.SB.6 closer landed; Phase 13 FULLY CLOSED 12 of 12 sub-bundles SHIPPED; cross-bundle pin row 13 GREEN at 4 surfaces; fast E2E `tests/integration/test_phase13_t4_sb_closer_e2e.py` lands; triage-agenda stub at `docs/phase13-closer-next-phase-triage.md`; next: operator-paired triage meeting per §1.5.2.) Previous: 2026-05-22 PM #2 (Phase 13 T4.SB BRAINSTORMING SHIPPED at `4299340` — FIRST sub-bundle of Phase 13 closer arc. 7-commit dispatch; Codex R5 NO_NEW_CRITICAL_MAJOR (ZERO Critical entire chain; 17 MAJOR ALL RESOLVED in-place; 10 MINOR); 28th cumulative C.C lesson #6 NOTABLE (Expansion #7 PARTIAL FAIL on architecture-location wrong-module placement; NEW Expansion #10 CANDIDATE banked). 14 V1 simplifications + V2 candidates banked. 18 OQs surfaced in spec §J for operator-paired triage. Schema v21 UNCHANGED. Phase 13 sub-bundle ship count 11 of 11 — T4.SB closer arc IN-FLIGHT.) Previous: Polish bundle 2026-05-10 SHIPPED at `44ac760` — 3-item bundle: 3e.4 hyp-rec current price line + 3e.7 entry-form example asides extended to all 8 textareas with HTML5 native `<details>`/`<summary>` collapsibility + Ruff N818 mechanical 8-class rename. 9 commits = 5 task-impl + 2 Codex-fix + 1 operator-gate I1 + 1 merge. Codex R1 0/3/2 → R2 0/0/2 NO_NEW_CRITICAL_MAJOR (2 rounds). Operator-witnessed gate: 6 surfaces; S1+S4+S5+S6 PASS; S2+S3 SKIPPED-with-test-coverage. Operator-gate I1 caught two brief-author errors mid-verification: (a) undercount of textareas in Pre-trade thesis fieldset (locked '5' but actual is 8) + (b) operator-iterated reversal of "visible always" lock to "default collapsed, individually expandable." Test count 2121 → 2140 (+19); ruff baseline 26 → 18 (8 N818 cleared; 18 E501 remaining). Adversarial review correctly delegated to implementer per orchestrator-context "Executing-plans dispatch convention" 2026-05-02 (initial brief had this backwards — orchestrator-runs-Codex; corrected via brief revision `596420e`). Previous: Polish bundle 2026-05-09 SHIPPED at `b4bb9dd` — 5-item bundle: 3e.5 daily-mgmt logged-today badge + 3e.6 auto-return to dashboard + 3e.11 strip Phase/Tranche from CLI help + 3e.13 top-nav Reviews link + 3e.14 cadence card "Complete review" inline link. 16 commits = 13 task-impl + 3 adversarial-fix; 3 Codex rounds → NO_NEW_CRITICAL_MAJOR; 2099 → 2121 fast tests (+22); ruff baseline 78 preserved. Mid-dispatch implementer caught a brief-locked predicate error — `action_session_for_run` vs writer's `last_completed_session` — and corrected inline; new round-trip integration test pins read/write alignment. New CLAUDE.md gotcha promoted: session-anchor read/write mismatch family (third instance with weather + this).).

---

## How to use this file

If you are a fresh orchestrator session: read this file end-to-end before engaging with the developer. Then check `git log --oneline -20` to see what's landed recently, then check `git status` to see what's untracked or modified.

If you are the same orchestrator post-compaction: skim the **Currently in-flight work** and **Recent decisions** sections to recover state, then continue.

This file is project-specific and lives in the repo. Update it (small commits) whenever you make a meaningful framing decision, capture a new operating process, or accumulate a lesson worth carrying forward. Avoid bloat — pointers to authoritative documents beat duplicated content. Older content migrates to `docs/orchestrator-context-archive.md` per §"Maintenance: retention discipline" below.

---

## Role and operating pattern

You are the **orchestrator instance** for the Swing Trading project. Your collaborator is the developer (Reid Smythe). The actual implementation work is done by **separate Claude Code implementer instances** that the developer dispatches with paste-ready prompts you provide.

**The pattern is:**

1. Developer raises a need (bug, strategic question, feature, study).
2. You and the developer discuss tradeoffs and decide on scope.
3. You draft a comprehensive **dispatch brief** as a Markdown file in `docs/`.
4. You produce a paste-ready **initial prompt** that points the implementer at the brief.
5. Developer dispatches a fresh Claude Code instance with that prompt.
6. Implementer executes the brief (TDD, adversarial review, etc.) and returns a structured **return report**.
7. Developer relays the return report to you.
8. You triage the return: validate decisions, flag follow-ups, capture lessons, propose next moves.
9. Loop.

**Key principle: the developer drives, you serve.** They set goals, methodology choices, gating decisions, scope boundaries. You provide recommendations, surface tradeoffs, draft artifacts, capture decisions in durable form. You do NOT decide on the developer's behalf when they haven't yet decided. When in doubt, present options with your recommendation and ask.

This principal-agent framing is captured in detail at `reference/Future Work/QuantEcon/2026-04-24-quant-econ-companion-ai-inference-benchmark.md` §"AI's role in this project — operator drives, agent serves."

---

## Governing strategy (binding)

Three documents govern. Read these before engaging on strategic questions.

1. **`reference/Future Work/2026-04-23-bifurcated-strategic-implementation-proposal-v2.1.md`** — the V2.1 governing strategy. Bifurcated architecture (Operational + Research-and-Verification), minimum-viable governance, bootstrap-first data, tranche sequencing.
2. **`reference/Future Work/2026-04-23-rebuttal-response-for-implementors.md`** — binding clarifications on V2.1. Anti-patterns list (strategy inflation, registry maximalism, infrastructure displacement, parity absolutism, bootstrap drift, priority flattening, document worship) is binding.
3. **`CLAUDE.md`** at repo root — current-state context, project conventions, gotchas. Auto-loaded by Claude Code on session start.

Forward-looking strategic content (deferred until V2.1 tranches mature):

- `reference/Future Work/QuantEcon/2026-04-24-quant-econ-future-research-program.md` — quant-econ integration program (Themes 1–4).
- `reference/Future Work/QuantEcon/2026-04-24-quant-econ-companion-trigger-purpose-three-branch.md` — Path A vs Path B framing + three-branch architecture refinement.
- `reference/Future Work/QuantEcon/2026-04-24-quant-econ-companion-ai-inference-benchmark.md` — AI-era crowding metric + operator-drives framing.
- `reference/Future Work/QuantEcon/external-references.md` — pointer file for external resources.

---

## Three-branch architecture (key refinement to V2.1)

V2.1 specifies two branches: Operational + Research-and-Verification. A 2026-04-24 refinement distinguishes two sub-branches within Research:

| Branch | Activity | Per-study horizon | Canonical example |
|---|---|---|---|
| **Operational** | Daily decision-making with promoted methods | Continuous | The `swing/` codebase |
| **Applied Research** | Testing rules developed elsewhere | Weeks–months per study | Earnings-proximity-exclusion (Sessions 2a/b/c) |
| **Basic Research** | Discovering/refining rules at first principles | Months–years per investigation | QuantEcon program (Themes 1–4) |

**Branches are permanent capability, not time-bounded projects.** Idle ≠ failure ≠ dismantle. Branch infrastructure (harness scaffolding, method-record format, cache directories, study templates) persists across idle periods. Time budget is allocated dynamically — 100% to whichever branch has an active study/investigation, idle when none.

Promotion path: Basic Research → Applied Research → Operational.

Full detail: `reference/Future Work/QuantEcon/2026-04-24-quant-econ-companion-trigger-purpose-three-branch.md`.

---

## Currently in-flight work

> **This section decays fastest. Update on every meaningful change.**

> **Archive companion (2026-05-18 Phase 12.5 #3 T-3.3 split — zero-yield):** This section inspected for pre-2026-05-13 entries during the Phase 12.5 #3 archive-split pass; ZERO entries qualified (all "Prior state" snapshots are dated 2026-05-17 or later). No content moved from this section; pointer retained for symmetry with the "Lessons captured" pointer below + audit-trail integrity. See [`docs/orchestrator-context-archive.md`](docs/orchestrator-context-archive.md) for archive companion structure.

### Currently in-flight: PHASE 17 CLOSED (2026-06-13) — no active phase; awaiting the operator's next commission

Phase 17 (Consolidation & Parity-Drift Elimination) closed 2026-06-13 — schema UNCHANGED (v29, zero migrations), ~8132 fast green (the suite de-flaked by 17-D.4), ruff clean, every commit trailers `[]`. Arcs: 17-A single-evaluation orchestration (`bc05958c`) · 17-B `step_guard` extraction (`5c86c254`) · 17-C exports retention CLOSED-as-already-solved (premise false — `archive_old_exports` already retains; no code) · 17-D bug-container [.2 comms dark-mode, .3 review_log_cadence LeaseRevoked re-raise, .4 the `-n auto` polluter healed → de-flake, .5 weather-chart declutter+20MA]. Riders not Phase-17 work (R2 landed; R1/R3 carried to Phase 18, R3 → arc 18-C). **CHARC close audit: CLEAN TO CLOSE.** **Phase 18 (data-collection integrity) is scoped + operator-approved** ([`docs/phase18-todo.md`](phase18-todo.md)) — ready to open on operator go; do NOT commission until then. Canonical history: [`docs/phase17-todo.md`](phase17-todo.md); close-out handoff: [`docs/orchestrator-handoff-2026-06-13-phase17-close.md`](orchestrator-handoff-2026-06-13-phase17-close.md); CHARC close audit: `docs/phase17-close-audit-charc.md`. Trailing (organic, carried from Phase 16 — see phase17-todo §"Phase 16 trailing items"): the TROX age-off check (next nightly; FROZEN-not-removed), the dividend-marker capture, the RD QAs. **Lesson banked this phase:** before scoping a new-capability arc, grep ALL of `swing/` for a pre-existing mechanism (the 17-C premise-error; memory `feedback_brief_premise_check_existing_mechanism` + §Pre-Codex disciplines #38).

#### (superseded close record) PHASE 16 CLOSED (2026-06-12) — Observability & Logging
Phase 16 closed 2026-06-12 with all nine arcs shipped + gated (schema v29, the pipeline 10m25s→2m20s, the v29 cash ledger, the logging overhaul, watchlist pin). Canonical history: `docs/phase16-todo.md`; close-out handoff: `docs/archive/phase16/orchestrator-handoff-2026-06-12-phase16-close.md`.

#### (superseded close record) PHASE 15 CLOSED (2026-06-08) → PHASE 16 was opened

**Phase 15 CLOSED 2026-06-08** at schema **v24** (~7268 fast tests green on `main`; ~720+ commits ZERO `Co-Authored-By`; **L2 LOCK re-anchored ONCE** at the schwabdev-v3 upgrade — the first sanctioned baseline move). Schwab-integration-hardening + operational-correctness phase; ALL arcs SHIPPED+CLOSED: schwabdev v2.5.1→3.0.5 + Fernet (`#20`) · B-7 failure-mode (`#21`; the v24 migration) · PGT-redesign + nav-date (`#22`) · pattern-observation pool-widening (`#23`) · the **data-integrity arc + its descendant chain** (regular-session/completed-day `b237412b` + the `database is locked` deadlock fix `ffb5fdc6`+`4f0b4010` + bad-bar accept + the daily-mgmt #16 fetch-hoist `42c15caa` + Issue #3 `_count_open_at_run` `7bd51750` + the Gate-4 quote-cassette recorder `af36157d` + the Slice-B A-lite quote-mapper fix `a74a41a2`) → **data-integrity arc FULLY CLOSED** (Gate 4 passed, cassette `56e14988`, Schwab live for quotes). **Canonical per-arc history: [`docs/phase3e-todo.md`](docs/phase3e-todo.md) §A + `#20`-`#23`.** **No active dispatch.** **PHASE 16 (active — Observability & Logging):** the LIVE, GROWING todo is [`docs/phase16-todo.md`](docs/phase16-todo.md) — Arc 1 pipeline-run observability (the web subprocess stdout→DEVNULL / no `pipeline.log` / no per-step timing) · Arc 2 logging overhaul (centralized config + level knob + retention + redaction + correlation) · Arc 3 the XMAX watchlist-thumbnail Shape-A truncation bug · Arc 4 account-equity reconciliation (4a done; 4b/4c = wire the existing `cash_movement_mismatch` reconciliation + Schwab-cash ingestion + the cash-vs-NLV `kind` discriminator). The Phase-16-open handoff is [`docs/orchestrator-handoff-2026-06-08-phase16.md`](docs/orchestrator-handoff-2026-06-08-phase16.md). **Fresh orchestrator:** re-compact CLAUDE.md line-3 (the Phase-15 rollover) FIRST per that handoff §4, then read `phase16-todo.md` + `git log --oneline -20`; the snapshots below are pre-Phase-14 historical only.

### Prior state — archived (pre-Phase-14 snapshots)

*The pre-Phase-14 in-flight snapshots (Applied Research Tranche 1 + Phase 13, 2026-05-22/23) were trimmed at the 2026-06-02 Phase-14-close housekeeping — they duplicated the canonical per-cycle record. Canonical history: [`docs/phase3e-todo.md`](docs/phase3e-todo.md) `#1`-`#19` + the per-cycle return reports + [`docs/orchestrator-context-archive.md`](docs/orchestrator-context-archive.md).*

## Recent decisions and framings (don't re-litigate)

These have been settled with the developer's explicit approval. Don't reopen unless they ask.

- **Role scope-limitation + flag-vs-comply (CHARC harness-architecture rule, 2026-06-13).** The orchestrator's scope is intentionally narrow — tactical focus; extra context is creep. Within its swimlane it owes the operator INFORMED CONSENT, not silent obedience AND not re-litigation: flag a consequence ONLY when it is material, non-obvious, AND visible in the orchestrator's own lane (e.g. a waived test that gates merge safety; a skipped migration step that risks data) — then comply regardless; one flag, not a debate. It does NOT flag — and structurally cannot assess — CROSS-PHASE or architectural consequences; those are invisible to it by design and are the director's burden, caught via the §3-equivalent tripwires that route the broad view UP to CHARC. Corollary: a benign, obvious, or cross-scope-only waiver warrants no pushback (e.g. accepting a "these riders aren't this-phase work" waiver is correct). This is CHARC-owned harness architecture (a rule ABOUT orchestrator scope, whose justification lives outside the swimlane — an "unknown unknown" to the role); corrections route through CHARC, not self-authored here.
- **Bifurcated architecture per V2.1.** Settled.
- **Three-branch refinement** (Operational, Applied Research, Basic Research). Settled 2026-04-24.
- **V2.1 Addendum additions adopted in V2.1** (time-budget anchor, demotion pathway, source-of-truth correction protocol). Merged in place.
- **Adversarial review on every code-shipping session** (standing convention). Adopted after Tranche B-ops Session 2 demonstrated value (caught the `open_risk_position_count` bug). Implementer invokes `copowers:adversarial-critic` on the combined diff after task commits land; iterates to `NO_NEW_CRITICAL_MAJOR`; fixes findings in a new commit per no-amend rule.
- **Path A vs Path B framing for QuantEcon program.** Path A = practitioner extension; Path B = quant-rigor overlay. Path B gated on operational system producing above-market returns. Path B is QuantEcon program; not actionable until V2.1 tranches mature AND operational system is proven.
- **Operator-drives, agent-serves principle.** Operator defines problem framing; agent provides knowledge-retrieval + execution. The recursive crowding concern about AI-aided development is narrowed by this discipline.
- **Pre-registration discipline for research studies** (Session 2c). Decision tiers + thresholds committed before viewing data.
- **Survivorship-bias interpretation protocol** (study-level amendment). Absolute metrics treated as lower bound; relative metrics as direction-trustworthy-magnitude-uncertain; weak/null signals → defer not reject.
- **Filter-rule activation-rate sanity check** (forward-looking lesson from Session 2c). Future filter-rule studies pre-register a sanity check that the most aggressive variant must filter ≥10% of signals.
- **Tranche 2 of V2.1 §X satisfied formally by Session 2c's defer outcome.** Discipline held; question-level inconclusive. Bifurcated architecture proven end-to-end.
- **Russell 3000 as primary broader-universe variant** for the candidate-sparsity diagnostic; S&P 1500 as fallback if sourcing has friction.
- **(2026-04-25) Capital-sensitivity finding interpretive disposition: informational, not workflow-changing.** Diagnostic showed structural risk_feasibility blocking shrinks 18.6% → 1.3% on SPX+NDX (and 6.9% → 0.3% on Russell) when capital scales 1× → 5×, but the deterministic A+ count change (5 → 10 SPX, 112 → 123 Russell) doesn't reach workflow-relevance threshold. Operator's framing: "the amount of money available is the amount of money available; without proven history, doesn't make sense to raise capital 2 orders of magnitude to go from 5 months to 2.5 months per A+ candidate."
- **(2026-04-25) Next-move post-Tranche-C: parallel operational + applied-research parity check.** Continue operational work (Phase 3e items, `build_watchlist` mixed-anchor fix, etc.); when research branch reactivates, the cheapest applied-research follow-on is hypothesis 5 (production-vs-replay parity check) to investigate the residual ~50× gap between matrix's most-permissive cell and production rate.
- **(2026-04-25) Production-gating-aware instrumentation as standing pattern.** When instrumenting production logic for diagnostic measurement, mimic production's gating order, not criteria emission order. Caught as R1 Critical in candidate-sparsity diagnostic; would have made primary hypothesis appear 3.5× weaker than reality if uncorrected.
- **(2026-04-25) Hypothesis 5 closed.** Harness-vs-production parity check returned Tier 1 result on n=80 production candidates from eval_15 (action_session 2026-04-25). Drift between research-branch harness and production pipeline is NOT the explanation for the residual ~50× rate gap from Russell-3000-5× to Session 2a anchor. Bound on claim: parity verified at watch/skip classification level; A+ classification parity unverified empirically (n=80 produced zero A+ candidates).
- **(2026-04-25) Path 1 selected for residual-gap question.** Accept "anchor noise + universe selection" as the explanation for the residual ~50× rate gap. Session 2a's CI [0.137%, 1.806%] is consistent with true rates as low as 0.05%; combined with Finviz pre-screening narrowing the universe, the gap is at least partially expected. No further study commissioned. Hypothesis 6 (Finviz universe reconstruction) and hypothesis 4 (regime) remain available but not pursued under current capital constraints.
- **(2026-04-25) Bug 7 family confirmed closed in web layer.** Survey query (`grep -rn 'ORDER BY run_ts DESC LIMIT 1' swing/web/`) on the post-`77877c1` tree confirms every primary read path that joins candidates by ticker now binds via `pipeline_runs.evaluation_run_id` (FK-direct or heuristic). Class durably closed in this layer.
- **(2026-04-25) Framework framing.** The framework is what we are building, informed by Minervini and Disciplined Swing Trader as known-good priors. Research branches exist to test, refine, and — where evidence justifies — depart from those references. Doctrinal fidelity is not the constraint; evidence quality is. Implication: research-branch findings can propose framework changes (criteria modification, allowed-miss extension, bucket logic, universe choice); the V2.1 source-of-truth correction protocol governs the formal change process, but the framework is not bound by the references absent that process.
- **(2026-04-25) Evidence gap framing.** Current operational rate (~2 trades/year confirmed by operator; harness-derived ~2.5 A+/year on SPX+NDX 1×) is too low to produce trade-outcome data sufficient for framework evaluation. Research-derived rate-uplift candidates (universe broadening, allowed-miss extension, criteria refinement) are tools to escape the rate-vs-evidence recursive bottleneck. As of 2026-04-25, operational branch has produced n=1 trade outcome (VIR); the loop has begun to break but evidence accumulation will take time.
- **(2026-04-25) S&P 1500 universe expansion: Tier 2 — Mixed.** 2.39× rate uplift point estimate over SPX+NDX 1× baseline (Wilson CIs overlap, so the difference is suggestive not formally significant on this single window); 48.6% absent earnings data; clean sector + liquidity profile. Capital-fit sub-finding: risk_feasibility blocking is LOWER on mid-cap universes than large-cap at operator's actual capital, contrary to naive expectation. Operator-decision pending on whether to adopt the lever; not re-litigated absent new evidence.
- **(2026-04-25) Sub-A+ trading is in operator's actual practice.** VIR trade (2026-04-20) was framework-recommended in `watch` bucket — passed all 8 trend-template criteria, failed two VCP-layer criteria (`proximity_20ma` extended above 20MA; `tightness` zero-day-streak base not formed). Operator took it anyway as a "trade test" per entry notes. Practice precedes principle: the "willing to relax absolute A+ doctrine" framing post-dates the actual deviation. Future workflow discussion should treat sub-A+ trade-taking as a practice-supported reality, not a hypothetical. Specific category for this trade (now backfilled in `hypothesis_label`): "sub-A+ VCP-not-formed test (proximity_20ma + tightness fails); inaugural trade test."
- **(2026-04-25) Operational branch as evidence-generation surface.** Operator is willing to take hypothesis-tagged sub-optimal trades within risk discipline, treating losses as cost-of-development rather than investment loss. Each trade requires a frozen pre-trade hypothesis label (free-text initially via the `hypothesis_label` column shipped 2026-04-25). Pre-registration discipline applies — label is set at entry and frozen; outcome-driven re-labeling is anti-pattern. This shifts operational posture from "execute proven framework" to "execute candidate framework variations to generate evidence" — V2.1 promotion path running in reverse to escape the rate-vs-evidence bottleneck.
- **(2026-04-25) A+ identifications ≠ trades (statistical analysis discipline).** A+ is a production classification (bucket assignment); trade is an operator decision to enter a position. They should be analyzed as separate measurements; do not conflate. Operator's intent is to trade every A+ but that's not a hard rule, AND going forward trades will outpace A+ identifications because of hypothesis-tagged sub-A+ trade evidence collection. Statistical aggregations (rate, expectancy, etc.) should preserve the distinction.
- **(2026-04-25) Identification rate recalibration.** A+ identification rate on operator's actual Finviz pool is plausibly ~40-100/year per Finviz-pool study extrapolation (8-day snapshot produced 2 unique A+ decisions on 6 distinct CSV-days). NOT ~2/year. The earlier "2/year" framing came from candidate-sparsity diagnostic on broad SPX+NDX universe; Finviz pool is a much tighter pre-filter that implicitly enforces TT criteria, raising the conditional A+ rate substantially. The "2/year" framing is retired.
- **(2026-04-25) Binding constraint is capital tie-up, not identification rate.** Capital ceiling at $7,500 × ~14% per position × ~5 concurrent × ~10 cycles/year ≈ 50 trades/year. With identification volume ~40-100 A+/year + ~470/year near-A+ defensible candidates from Finviz study, candidate volume already exceeds throughput capacity. Time, pipeline cadence, manual chart-review, and trade-execution friction are all non-binding at current scale. Implication: rate-uplift levers (universe broadening, allowed-miss extension) matter less than I previously framed; operational use of existing infrastructure matters more.
- **(2026-04-25) Chart-pattern algorithm is for encoding, not throughput.** Operator's manual chart assessment is fast enough to saturate capital today. The algorithm's value is structuring the qualitative chart-pattern dimension of trade decisions into the feedback-loop's analyzable data. Without it, hypothesis-label free-text absorbs chart-pattern info qualitatively (interim solution). When chart-pattern algorithm exists, it becomes a structured field; hypothesis-label holds remaining qualitative dimensions. Chart-pattern algorithm is important but NOT urgent; multi-session copowers cycle when ready. Phase 3e §3e.6 captures the original scope.
- **(2026-04-25) Next-horizon priority: operational use of newly-built infrastructure, not additional development.** Hypothesis-label infrastructure ships; Finviz-pool study identifies near-A+ defensible candidates (SLDB, UCTT). The actually-urgent next move is operational — take hypothesis-tagged trades, accumulate evidence, let the feedback loop run. Watch-staging UI is a small operational change with immediate value. S&P 1500 adoption decision is operator-pending. Chart-pattern algorithm and other development work are not urgent.
- **(2026-04-25) 10% return target math.** With $7,500 capital, ~50 trade/year ceiling at full deployment, and Minervini-typical expectancy (~0.5-0.8% account return per trade), the math gives 20-40% annual return ceiling. The 10% target is well within range, not the ambitious target it was earlier framed as. Compounding + capital injection to ~$100K extends absolute returns linearly to $20K-$40K/year at the same percentage ceiling.
- **(2026-04-25) Hypothesis investigation plan v0.1 longer-horizon framing: implicit, revisit at first closure gate.** Operator and orchestrator agreed that beyond the 4 starting hypotheses (A+ baseline 20-sample target; near-A+ defensible extension 10-sample; sub-A+ VCP-not-formed 5-sample; capital-blocked smaller-position 5-10-sample), there is no longer-horizon plan, and that's the correct posture for now. Reasoning: data from the 4 starting hypotheses will inform what to test next; trade pace is unknown (3-18 months to fill all 4 targets); committing further hypotheses now risks document-worship anti-pattern OR vague aspiration. **Action: when the first hypothesis closes (whichever hits its target sample size or escapes via tripwire first; likely Sub-A+ VCP-not-formed at 5 samples or A+ baseline at 20), explicitly revisit the longer-horizon planning question with operator.** Decision-cadence framing (Phase A: collect; Phase B: review-and-iterate at first closure; Phase C: longer-horizon strategic review at multi-hypothesis closure) is captured here for that future moment but not yet committed as a roadmap document.
- **(2026-04-25) Hypothesis investigation plan v0.1 OPERATIONAL.** Migration 0008 seeded 4 hypotheses (A+ baseline 20-target; Near-A+ defensible: extension test 10-target; Sub-A+ VCP-not-formed 5-target; Capital-blocked: smaller-position test 10-target). Tripwire values per-hypothesis: consecutive-max-loss N (3 for n=5; 4 for n=6-10; 5 for n=11-20) AND absolute-loss 5% of starting equity. Per-hypothesis status mutation only via `swing hypothesis update --status --reason "..."`; tripwire/sample-size/decision-criteria are immutable post-data (require formal new migration). VIR is sample 1 of 5 in Sub-A+ VCP-not-formed. Dashboard surface and CLI pre-fill operational; operator can take hypothesis-tagged trades from Monday onward.
- **(2026-04-25) Prefix-label convention (operator-facing).** Hypothesis-label matching against the registry uses **case-insensitive PREFIX** match (not substring; chosen by hyp1 R1 to prevent double-counting). **When operator manually composes a `--hypothesis` value** (e.g., for off-pipeline trades or override of pre-fill), the label MUST start with the canonical hypothesis name (e.g., `"Sub-A+ VCP-not-formed test ..."`, NOT `"my custom test for sub-A+"`) for tripwire/progress aggregation to correctly attribute it. The CLI pre-fill emits matcher's `suggested_label_descriptive` which already follows this convention; manual labels are operator-responsibility.
- **(2026-04-25) Hypothesis-recommendation engine framing: dashboard PROPOSES, operator DISPOSES.** The dashboard's Hypothesis-driven recommendations panel is an active recommendation surface — not just a listing. It tells the operator "if you take this trade, it advances hypothesis X (currently N/M samples)." Operator validates the recommendation (chart pattern, risk, sector preference) and either takes the trade or declines. Tripwire-fired hypotheses surface visually (red row); operator evaluates whether to pause/escape via `swing hypothesis update --status paused --reason "..."`. Pre-registration discipline applies — hypothesis plan and tripwires are frozen at migration 0008; only `status` is mutable via CLI.
- **(2026-04-25) Entry discipline for hypothesis trades: wait for pivot (stop-buy at pivot).** All hypothesis-tagged trades enter at-pivot via stop-buy order (or stop-limit for higher-volatility names where slippage control matters). Do NOT chase more than ~1% above pivot; if price gaps significantly above pivot at open, skip that day. Rationale: (a) pivot is the framework's prescribed entry trigger; (b) entry-execution is a confound on per-hypothesis expectancy aggregation — pre-committing to at-pivot eliminates that confound from the per-hypothesis statistics. Applies to ALL four hypotheses uniformly, including Sub-A+ VCP-not-formed (where the "pivot" is somewhat placeholder since base isn't formed; entry-at-pivot is still the cleanest discipline). The framework's initial_stop discipline caps the downside if pivot turns out to be the day's high → pullback. Operator workflow: review hyp-tagged dashboard listings → manual analysis (chart pattern, sector, risk) → if proceeding, stop-buy at recommended pivot → accept that pivot-as-day's-high is a known failure mode budgeted by the initial_stop.
- **(2026-04-26) Watchlist sort uses four-key composite ordering.** Sort key: tag count DESC → tag precedence DESC (`A+`=4, `VCP✓`=2, `TT✓`=1, summed) → abs(% to pivot) ASC → ticker ASC for determinism. Hypothesis-recommendations table sort untouched per scope discipline (its existing prioritizer is hypothesis-aware: progress, target distance, tripwire). Operator decision recorded; revisit hyp-recs sort separately if needed.
- **(2026-04-26) `/prices/refresh` anchor consistency closed Bug-7 family in this layer.** The route's cache-prewarm path was using `MAX(run_ts) FROM evaluation_runs` (the pre-Tranche-C mixed-anchor pattern) while `build_dashboard` and `build_watchlist` use pipeline-eval-first via `latest_evaluation_run_id`. Session 2 R1 caught the divergence as part of sort-anchor consistency review; the route now consumes the same pipeline-eval-first anchor. Survey query (`grep -rn 'MAX(run_ts) FROM evaluation_runs' swing/web/`) confirms no remaining occurrences in the web layer. Class durably closed.
- **(2026-04-26) Phase 3 dispatch discipline: disjoint-task-partitioning, no worktree isolation initially.** Phase 2 execution surfaced internal subagent collision (see Lessons captured). Operator decision: try task-partitioning brief discipline first (cheaper, prevention rather than containment) before falling back to worktree isolation (heavier ceremony). Phase 3 brief specifies: each task assigned to exactly one subagent (multiple tasks per subagent allowed; task sets must be DISJOINT across agents); subagents must verify task deliverable doesn't already exist before starting; abort + report if it does. Worktree isolation is the fallback if collision recurs in Phase 3+.
- **(2026-04-26) Phase 4+ dispatch discipline: continue partitioning + ADD observable verification.** Phase 3 produced one rogue task duplicate (b080da9 + revert 132142c) despite single-subagent dispatch. Net code state was correct; noise bounded (~20% of chain vs Phase 2's ~30%). Operator decision: continue brief discipline; ADD observable verification — subagent MUST include `git log --grep="Task X.Y" --oneline` output in commit body BEFORE each task commit. Makes duplicate-detection observable to Codex review (Codex can flag commits whose body shows existing task implementation). If Phase 4 sees another rogue, escalate to worktree isolation in Phase 5+.
- **(2026-04-26) Review-fix commit message convention formalized.** Task implementation commits MUST include task ID (e.g., `feat(pipeline): Task 3.2 — ...`). Adversarial review-fix commits SHOULD include round + finding ID (e.g., `fix(pipeline): Codex R1 Major 2 — summary-log denominator semantics`). Format-only cleanup commits (ruff, comment-only) no task ID needed (e.g., `style(pipeline): ruff UP037 cleanup`). Phase 2 precedent (`115c96b`) and Phase 3 R2 M1 finding settled this. Captured in §"Binding conventions" below.
- **(2026-04-26) Observable-verification subject-only grep refinement.** Phase 4 surfaced false positives in the `git log --grep="Task X.Y"` rule when commit bodies cross-referenced future task IDs in narrative prose. Phase 5+ briefs adopt: `git log --pretty='%s' --grep='^[a-z]+\([a-z]+\): Task X.Y'` — subject-only, anchored to the conventional-commit prefix structure. Doesn't constrain commit-body prose. Single-subagent + observable-verification (Phase 4 evidence) successfully prevented rogue duplicates; worktree isolation NOT escalated.
- **(2026-04-26) Phase 4 scope-deviation acceptances (R1 Major 2).** Two scope deviations from Phase 4 brief §1 file allowlist were accepted as in-scope-by-spirit: (a) `.gitignore` modification for `.tmp-phase4/` — brief §5 mandated `pytest --basetemp=<gitignored-relative-dir>`; gitignore entry is the natural corollary. (b) `tests/pipeline/test_step_charts_classification.py` — Task 4.8 closed Phase 3's OPEN QUESTION on date deserialization by removing `.isoformat()` workarounds that became broken assertions once Task 4.0a parsed dates as `date` objects; downstream consumer of authorized Task 4.0a carve-out extension. **Pattern for future briefs:** when a brief authorizes a Phase 2 carve-out extension touching upstream behavior, downstream tests of the modified file are naturally in-scope; brief should explicitly list them OR brief should explicitly say "downstream tests of carve-out file are in-scope by extension."
- **(2026-04-26) Base-layout 5-VM rule scope.** CLAUDE.md gotcha applies only when `base.html.j2` dereferences the new field. Phase 4 brief blanket-required all 5 VMs to gain `pattern_tags`; implementer correctly scoped to 2 (`WatchlistVM`, `DashboardVM`) per spec §3.5 because flag-tag rendering lives in `partials/watchlist_row.html.j2` (consumer-scoped). Spec scope was narrower and correct. **Future briefs:** don't blanket-require the 5-VM rule unless `base.html.j2` is actually being touched. Verify the gotcha applies before requiring its mitigation.
- **(2026-04-26) Phase 6 mathtext fix landed as standalone tiny commit (`2fd0ecc`).** Phase 6 visual verification surfaced a pre-existing matplotlib mathtext quirk in the chart title format (`pivot $110.00 stop $95.00` — paired `$..$` triggered math mode, italicizing "stop"). Pre-existing in legacy title format; Phase 6 didn't introduce it but every Phase 6 chart shipped with the artifact. Operator approved as standalone tiny commit before Phase 7 dispatch (Q1, post-Phase-6 triage). Fix: `\$` escape in raw f-string; matplotlib renders `\$` as literal `$` glyph without entering math mode. Test assertions updated to match (`r"... pivot \$110.00 ..."`).
- **(2026-04-26) Internal-Codex `(internal)` qualifier convention** (Q2, post-Phase-6 triage). Phase 6 surfaced commit-message tag collision: subagent-dispatched internal-Codex round (`c215c79`) and orchestrator-wrapper Codex round (`13d0deb`) both labeled "Codex R1 Major 1." Convention: internal-Codex commits append `(internal)` qualifier; orchestrator-Codex commits stay as-is. Subject-only grep regex still matches both forms (when the grep is invoked correctly per the 2026-04-27 ERE refinement below). Captured in §"Binding conventions" above. Phase 7+ briefs adopt the convention.
- **(2026-04-27) Subject-only grep regex amended to ERE + POSIX digit class** (Q1, post-Phase-7-implementer triage). Phase 7 implementer-side discovered empirically that the convention's regex `^[a-z]+\([a-z]+\): Task X.Y` returns empty under git's default BRE because `+` is literal in BRE (not a quantifier) and `\d` is a Perl-style class POSIX doesn't recognize. The "expected empty" output then matched for the wrong reason — the regex was non-functional. Amended convention: subagent invokes `git log -E --pretty='%s' --grep='^[a-z]+\([a-z]+\): Task X.Y'` with the `-E` flag (ERE mode); for Codex round labels, use `[0-9]` instead of `\d`. Captured in §"Binding conventions" above. **Lesson worth surfacing in past briefs:** prior phase briefs that included the BRE-incompatible regex were technically non-functional; the discipline still worked because (a) the implementer typically reads commit subjects directly anyway, and (b) ZERO-rogue track record was real (other partitioning rules carried the load). Going forward, briefs use the ERE form.
- **(2026-04-27) Manual verification round 1 complete; Tier-1 mathtext fix dispatch queued.** Operator + orchestrator walked verification doc step-by-step; ~75% coverage achieved; ONE production regression confirmed (mathtext title fix #1) + 3 UX gaps + 2 design questions + 7 doc fixes surfaced. Findings consolidated in `docs/chart-pattern-flag-v1-manual-verification-results.md`. Operator instruction during walkthrough: "do not take action on feedback until we finish or hit a significant blocker" — discipline held; all findings logged as observations, none fixed mid-walkthrough. Tier-1 mathtext fix dispatched ahead of Task 7.3 fixture labeling (legible chart titles needed during labeling work). All other findings tier-prioritized for post-V1 backlog OR natural-workflow exercise.
- **(2026-04-27) Phase 7 FP/FN aggregator: deferred to operator-manual classification** (Q2, post-Phase-7-implementer triage). Spec §3.1.4 + §4.2 require FP-biased tuning at Task 7.4 checkpoint based on FP/FN tally over labeled fixtures. Phase 7 implementer-side did NOT add an automated session-scoped FP/FN aggregator — operator does manual classification from pytest output (`pytest -v` reports per-fixture PASS/FAIL with label + actual pattern in the error message). ACCEPTED for V1 personal-use scope; if Task 7.4 reveals operator needs aggregation tooling, add as a small standalone follow-up. Captured in `docs/phase3e-todo.md` Phase 7 → operator handoff items.
- **(2026-04-26) Chart-pattern shape estimator V1 scope locked (six decisions).** Brainstorm output at `docs/superpowers/specs/2026-04-26-chart-pattern-flag-v1-design.md` (commit `081f689`). Locked: (1) **One pattern only — `flag_pattern`**; other patterns (pennant, base, cup-handle, tight channel) are V2+ additions. (2) **Governance: display + persist on trades + confidence metric; production scoring/bucketing UNTOUCHED.** Promoting any aspect to production decision logic requires V2.1 §VII.F. (3) **Compute timing: pipeline-time on chart-scope tickers** (extends `_step_charts`, shares in-hand OHLCV — zero scope expansion). (4) **Display surface: watchlist rows + trade-entry form + chart overlay.** (5) **Trade-entry consumption: cached-only.** Out-of-chart-scope manual trades have no override surface in V1. (6) **Operator override: algo and operator values stored separately** on trade row (4 columns: chart_pattern_algo, chart_pattern_algo_confidence, chart_pattern_operator, chart_pattern_classification_pipeline_run_id audit anchor). Effective-pattern-for-analysis = COALESCE(operator, algo). Algorithm approach: rule-based geometric (deterministic; 11 gates; min-of-clearances confidence). Watchlist tag rendering: parallel `pattern_tags` VM field — `_sort_watchlist` byte-for-byte UNCHANGED (sort-neutrality structurally guaranteed). Spec passed 5 adversarial Codex rounds (22+ findings dispositioned).
- **(2026-04-25) Vocabulary for confirmed hypotheses: "promoted" (per V2.1 promotion-path).** A hypothesis whose investigation closes positively (target sample met AND decision criteria evaluated positive AND operator decides to retain as ongoing recommendation surface) is **promoted**, not "lemma" / "validated" / "confirmed" / other generic terms. Reuses V2.1 three-branch promotion-path language (Basic Research → Applied Research → Operational; here: under-investigation → promoted-to-operational). Behavioral implications of `promoted` status: (a) continues to appear on dashboard recommendation surface but with different visual treatment (no "N/M progress" since target was met; instead lifetime stats like "promoted; lifetime: N trades, mean R X.XX"); (b) tripwire stays armed — if performance degrades post-promotion, the tripwire surfaces it for operator re-evaluation; (c) per-trade attribution continues so we can monitor for degradation. **Implementation deferred until first closure approaches:** a future small migration `0009_hypothesis_status_promoted.sql` will add `'promoted'` to the `hypothesis_registry.status` CHECK constraint enum (currently `active`/`paused`/`closed-escaped`/`closed-target-met`). Pre-registration discipline preserved — status enum widening is a formal migration, not a CLI-mutable operation.
- **(2026-04-27) Orchestrator-vs-implementer brainstorm-pattern decision.** For substantive design work (≥3 architectural decisions of medium complexity OR spec output ≥500 lines OR orchestrator context approaching 60%+), DISPATCH the brainstorming workflow to a fresh implementer instance rather than running it in the orchestrator thread. Reasoning: spec-by-construction self-contained (implementer has no conversation history to leak in); discipline isolation (single-role focus on the rigid brainstorming workflow); orchestrator context preserved for cross-dispatch triage; pattern parity with writing-plans + executing-plans (also implementer dispatches). For smaller-scoped brainstorms (1-2 sections, well-bounded scope), orchestrator-thread is more efficient (avoids ~10-15 min context-reload overhead). The chart-scope policy v2 brainstorm (~6 sections, schema migration + signature change + policy redesign) was borderline — finished in orchestrator-thread because we were ~75% done when the question came up. Future substantive brainstorms default to dispatch.

---

## Operating processes

### Brief drafting

Briefs live in `docs/` with naming pattern `{tranche-name}-{session-name}-brief.md`. Examples: `tranche-a-brief.md`, `tranche-b-ops-session-2-brief.md`, `tranche-c-pipeline-linkage-brief.md`.

A brief MUST include:

- Audience statement ("Fresh Claude Code instance with no prior conversation context").
- Mission paragraph.
- Expected duration estimate.
- §0 "Read first" — list of files the implementer must read, with rationale.
- §0 "Skill posture" — which superpowers/copowers skills to invoke or NOT invoke.
- Strategic context section (compressed; what they need that isn't in linked references).
- Scope section with explicit "out of scope" sub-list.
- Binding conventions (commit style, no-amend, TDD, test discipline, etc.).
- Per-task specifications with acceptance criteria.
- Adversarial review section (target + watch items).
- Done criteria.
- Return report format.
- "If you get stuck" section.

Briefs typically run 200–500 lines. Tight is better than padded. Self-contained — the implementer should be able to execute end-to-end from the brief + linked references without your conversation context.

### Paste-ready initial prompt

Always provide alongside the brief. Format:

```
You are dispatched as the {session-name} implementer for the Swing Trading project in this repo.

Step 1 — Read `docs/{brief-filename}.md` in full. {one sentence on what's in it}.

Step 2 — Read the references §0 of the brief points at, particularly {key references}.

Step 3 — Execute the brief directly. {Skill posture summary; key disciplines; key out-of-scope reminders.}

Step 4 — Produce the return report per §{N} of the brief as your final message.
```

### Triage of return reports

When a return report comes back, triage in this order:

1. **Verify the work matches the brief.** Commits landed? Tests green? Adversarial review verdict?
2. **Validate the substantive decisions.** Did the implementer make sensible calls on judgment-call items?
3. **Triage adversarial-review findings.** Each ACCEPTED-with-rationale finding deserves a sentence of acknowledgment; each FIXED finding deserves verification that the fix is correct.
4. **Flag follow-ups.** Items the implementer flagged for future work go to `docs/phase3e-todo.md` or appropriate backlog at the next housekeeping opportunity.
5. **Capture lessons.** Process insights go into this file or into memory.
6. **Propose next moves.** Don't decide unilaterally; offer options with recommendation.

#### Posting to the directors via the comms mailbox (added 2026-06-11, comms Stage 1)

After you relay a return report to the operator in chat (UNCHANGED — that is the operator's control point and it stays), ALSO post the same report to both directors via the file mailbox so they track arc state without the operator hand-relaying it:

```
python scripts/role_mail.py post --from orchestrator --to charc,rd \
  --type return_report --subject "<arc>: <one line>" --body-file <return-report.md>
```

**The IMPLEMENTER never posts to the mailbox — the ORCHESTRATOR does, and only AFTER QA.** Return reports flow: implementer → orchestrator (the implementer's final chat message, operator-relayed) → orchestrator QA against disk → THEN the orchestrator posts the QA'd report to the directors. A dispatch / executing-plans prompt MUST NOT instruct the implementer to run `role_mail.py post` (and NEVER `--from orchestrator` — that impersonates this role and bypasses the QA gate). The implementer's final brief step is always "return report as your final chat message," nothing more. (Caught 2026-06-12: the Arc 17-A executing prompt's Step 9 told the implementer to post its `return_report` straight to charc+operator, skipping QA — a brief-template defect, not an implementer deviation. A brief §8 / dispatch step that says "return report via the mailbox" must be read as the orchestrator's post-QA action, and dispatch prompts must be authored accordingly.)

Additionally, post LIFECYCLE events as `--type status` to both directors as they happen, so the directors follow arc state in real time:

- copowers-phase transitions: brainstorm / writing-plans / executing-plans **dispatched** or **returned**.
- generational handoff: include the handoff-brief path in the body.
- phase close.

What does NOT go through the mailbox (stays operator-hand-carried by design — the information-vs-authority line): **dispatch-direction traffic** — commissioning briefs, implementer dispatch prompts, and approvals. The mailbox carries *information* (status, queries, return reports) between roles; *authority* (decisions, commissions, dispatch) remains operator-mediated. `decision_request` is the operator's type only; `role_mail.py` refuses to route it to a director (the L1 lock). There is no orchestrator inbox in V1 — you POST to directors and receive direction FROM the operator in chat. Bootstrap a fresh orchestrator generation with `scripts/orchestrator_bootstrap.md`.

### Bug-fix briefs and operator-confirmation gate

For bug-fix briefs where the mechanism is not yet diagnosed (scope: "Investigation comes first; fix comes second"), require an explicit **operator-confirmation gate** between the investigation phase and the fix phase. This prevents the failure mode demonstrated by Bug 2 (2026-04-25) — implementer assumes a plausible mechanism, builds a fix that's internally correct but addresses a different path than the one operator is hitting.

**Brief language template (insert between investigation phase and fix phase):**

```
### Investigation-phase operator-confirmation gate (before §X fix phase)

Before designing the fix, draft a "mechanism candidate" message back to
the operator containing:
  - The mechanism you believe is causing the bug
  - The reproduction sequence you used to confirm it (concrete steps)
  - Specific evidence (network trace, response body, DOM state, etc.)
  - Explicit confirmation request: "Does this match what you see?"

Wait for operator confirmation before proceeding to design the fix. If
the operator says "that's not what I see," repeat investigation with the
new information. Do NOT design the fix until the mechanism is
operator-confirmed.
```

For FIX-DIRECT briefs (known mechanism, specified fix), the gate is not needed.

**Adversarial-review watch items for ALL bug-fix briefs:**

Standing watch items the brief should pass to `copowers:adversarial-critic` for any bug-fix dispatch:

- "Did the investigation empirically reproduce the operator's EXACT symptom (not a plausible-but-different mechanism that produces a similar-looking failure)?" Bug 2 (2026-04-25) demonstrated this failure mode.
- "Did the fix address the root cause, or only the surface symptom?" Sometimes the symptom can be made to go away without understanding why — that's brittle and likely to recur.
- For UI bugs specifically: the project lacks a JS test harness (see `docs/phase3e-todo.md` JS-execution test harness gap). String-match assertions on rendered HTML confirm structure but NOT runtime JS behavior. Operator manual verification is the actual confidence source for JS-behavior fixes; document the verification steps in the return report.

### Housekeeping commits

Periodically, accumulate untracked drift + small backlog updates + minor documentation corrections into a single small "housekeeping" commit. Pattern: `docs/{phase}-housekeeping-brief.md` brief; one-session implementer work; landing commits like `docs: track {description}`. Examples shipped: `4f74493` (Tranche B cleanup), `b03f66a` (B-ops cleanup), `2df7adb..6c179de` (post-2c housekeeping).

**Don't let housekeeping accumulate.** When 5+ untracked artifacts exist or 3+ small follow-ups have been deferred, dispatch a housekeeping commit.

---

## Binding conventions (project-wide)

These come from CLAUDE.md but are restated here because you'll be drafting briefs that enforce them:

- **Branch:** `main`. No feature branches.
- **Commits:** conventional-commits. **No Claude co-author footer. No `--no-verify`. No amending.** Commit-message conventions (formalized 2026-04-26):
  - **Task implementation commits** MUST include task ID: `feat(area): Task X.Y — <description>`. Partitioning-prevention surface; makes duplicate-task detection trivial.
  - **Adversarial review-fix commits** SHOULD include round + finding ID: `fix(area): Codex R1 Major 2 — <description>` or `test(area): Codex R3 Minor 1 — <description>`. Audit-trail surface; not partitioning-relevant.
  - **Internal-Codex review-fix commits** (subagent-driven within-task review BEFORE orchestrator-wrapper Codex round) use the `(internal)` qualifier: `fix(area): Codex R1 Major 1 (internal) — <description>`. Distinguishes from orchestrator-wrapper Codex commits without breaking the subject-only grep regex (matches both forms when invoked correctly per the regex syntax note below). Phase 6 surfaced the disambiguation need (commit `c215c79` was internal-Codex; `13d0deb` was orchestrator-Codex; both labeled "Codex R1 Major 1" caused audit confusion).
  - **Subject-only grep observable verification** (regex amended 2026-04-27 post-Phase-7-implementer Q1): subagent invokes `git log -E --pretty='%s' --grep='^[a-z]+\([a-z]+\): Task X.Y'` (ERE flag `-E` + POSIX digit class) BEFORE each task implementation commit. **The `-E` flag is required** — git's default Basic Regular Expression mode treats `+` as a literal character, not as a quantifier; without `-E`, the grep silently returns empty even when matching commits exist (the "expected empty" output then matches for the wrong reason). For matching Codex/internal-Codex round labels, the canonical regex form is `^[a-z]+\([a-z]+\): Codex R[0-9]` (POSIX `[0-9]` instead of `\d` because POSIX regex doesn't support Perl-style character classes). Phase 7 implementer-side discovered the BRE incompatibility empirically (commit chain `528d38b..ca66216`); convention amended to specify ERE + POSIX explicitly.
  - **Internal code-review fix commits** (per Phase 5 precedent) use `code-review` prefix: `fix(area): code-review I1 — <description>` or `fix(area): code-review T6.1 — <description>`. Distinguishes from Codex review by review source.
  - **Format-only cleanup commits** (ruff, comment, whitespace) no task ID needed: `style(area): ruff UP037 cleanup`.
- **TDD:** failing test first, minimal implementation, pass, commit. One red-green cycle per logical change.
- **Phase isolation:** during Phase 3 work, `swing/trades/` and `swing/data/` are read-only unless an explicit carve-out is granted in the brief. Carve-outs require justification and listing of specific files touched.
- **DB location:** `%USERPROFILE%/swing-data/swing.db` — outside the Drive-synced folder. Never violate this; SQLite + Drive sync = corruption.
- **Tests:** `python -m pytest -m "not slow" -q` is the fast suite; must stay green. Slow suite (`-m slow`) is network-dependent; don't require it for routine validation.
- **Frozen-clock convention for date-touching tests (R2 rider, added 2026-06-12 with the Phase 17 Arc 17-A dispatch; debt item D9).** NEW tests that exercise date/session logic (`datetime.now()`, `date.today()`, `action_session_for_run`, session anchors) MUST pin the clock via a frozen-clock fixture rather than reading the live wall clock — this closes the day/DST-boundary false-green family (memory `feedback_no_false_green_claim`, 2026-05-30; ~90 legacy files call live clocks per CHARC register D9). **No retrofit** — the convention applies to newly-added tests only, not a sweep of existing ones.
- **Out-of-scope catches get a DURABLE landing the moment they are noticed (convention amendment, operator-approved, CHARC-originated, 2026-06-12).** When an implementer or orchestrator notices a defect or gap OUTSIDE the current dispatch's scope, it gets a durable home in the SAME breath as the notification — post a `role_mail` fyi (`--to charc,operator`) OR add a line to the current phase's open bug-container arc (17-D this phase). A chat-only mention is NOT sufficient: chat notifications evaporate with the session — a Phase 16 implementer's shape-identification invariant catch was lost exactly this way. (Complements the §Anti-patterns "flag in return reports, don't fix inline" discipline — this governs WHERE the flag durably lands.)
- **Ruff:** `ruff check swing/` baseline is 18 errors (E501 only) as of the 2026-05-10 polish-bundle ship (`efd3e15` cleared 8 N818 via mechanical exception-class rename batch; `9c9b57c` had previously brought the broader baseline 78 → 26 — see `docs/phase3e-todo.md` 2026-05-10 entry for residual breakdown). Earlier baselines for historical reference: 26 post-sweep / pre-N818; 98 pre-2026-05-10 sweep; 91 pre-Phase-5; 81 pre-Phase-7 (drift between historical anchors was pre-existing-legacy or ruff-version drift, not introduced by dispatches). Briefs forbid introducing new violations; the residual 18 E501 are explicit banked-for-bundling items per the phase3e-todo entry, not free territory for incidental fixes outside the bundle. Verify via `ruff check swing/ --statistics` not `wc -l` (default ruff output is multi-line per violation).
- **Adversarial review** on code-shipping sessions is mandatory (standing convention).
- **Executing-plans dispatch convention (formalized 2026-05-02 post-Phase-5).** Direct invocation of `superpowers:subagent-driven-development` followed by `copowers:adversarial-critic` (NOT the `copowers:executing-plans` wrapper, which bundles both phases without marker-file management between them). Workflow: (1) `superpowers:using-git-worktrees` to create isolated worktree (REQUIRED per `subagent-driven-development` skill docs); (2) `touch .copowers-subagent-active` to activate the global PreToolUse Codex-blocking hook (`~/.claude/hooks/block-copowers-during-subagent.sh`, registered in `~/.claude/settings.json`) which physically prevents subagents from invoking `copowers:adversarial-critic`, `copowers:review`, or `mcp__plugin_copowers_codex__codex*`; (3) invoke `superpowers:subagent-driven-development` to execute tasks; (4) `rm .copowers-subagent-active` after all tasks complete; (5) invoke `copowers:adversarial-critic` directly with PHASE/SPEC_PATH/PLAN_PATH/BASELINE_SHA; (6) operator-witnessed verification gate; (7) merge worktree to main. Hook is global (active for ALL Claude Code sessions across ALL projects on this machine); subagents physically cannot bypass. See `docs/phase5-configuration-page-executing-plans-brief.md` (`671451f`+, revised) as the canonical brief template for this workflow.
- **Worktree + editable-install verify-command (formalized 2026-05-02 post-Phase-5).** When a worktree-isolated dispatch needs runtime/browser verification via a CLI entry point (e.g., `swing web`), the verify-command MUST point at the worktree's package, not the editable-install path. PowerShell: `$env:PYTHONPATH = "."; python -m swing.cli web` from inside the worktree dir. Bash: `PYTHONPATH=. python -m swing.cli web`. Pytest is not affected (cwd-based discovery); CLI entry points ARE affected (editable-install resolver). Specify in any brief that uses worktrees + needs runtime verification.
- **Worktree directory path MUST be `.worktrees/<branch>/` at repo root (formalized 2026-05-09 post-polish-bundle-ship + cleanup-script extension).** Worktree-isolated dispatch briefs MUST specify the worktree directory path explicitly in §3 binding conventions OR §8 dispatch metadata. Required path: `.worktrees/<branch>/` at repo root — NOT `.claude/worktrees/<branch>/` (the `superpowers:using-git-worktrees` skill default). Rationale: `.worktrees/` is the project-precedent location aligned with the elevated-cleanup script `cleanup-locked-scratch-dirs.ps1` (which scans both paths as of 2026-05-09 but `.worktrees/` is the canonical naming) AND aligned with Phase 5/6/7/8 ship history (cleanup recurrence patterns + ACL-handling discipline). The 2026-05-08 lesson on worktree directory path discipline is now elevated to a binding convention; new briefs MUST include the explicit path. Failure mode (from Phase 8 V1 polish dispatch 2026-05-07): brief specified branch name only; implementer's `using-git-worktrees` invocation chose `.claude/worktrees/phase8-v1-polish/` per skill default; husk required separate `git worktree remove --force` to clean up because cleanup-script targeting was `.worktrees/` only. Cleanup-script extension landed 2026-05-09 covers both paths; brief discipline still required.
  - **(2026-06-12 reinforcement — home-dir-leakage chore.)** Sibling-of-repo worktree dirs (`C:/Users/rwsmy/swing-<arc>-plan`, `../swing-trading-sqlite-lock`, etc.) are **DEPRECATED** — they are the leak source that scattered orphaned husks one level above the repo (cleaned 2026-06-12). **ALL implementer worktrees live at `<repo>/.worktrees/<name>`** — repo-contained, gitignore-covered, swept by the cleanup script. Every dispatch brief MUST specify the `.worktrees/<name>` path; never let `using-git-worktrees` pick a sibling or `.claude/worktrees/` default. The `.worktrees/` ignore was moved out of the untracked per-clone `.git/info/exclude` into the **tracked `.gitignore`** (2026-06-12) so the ignore is reviewable and travels with the repo.

---

## Anti-patterns to avoid

These have caused real problems; resist the impulse:

- **Drafting briefs that reference "uncommitted" files without verifying current `git status`.** I made this mistake on the post-2c housekeeping brief (claimed Bug 7 in Bugs.txt was uncommitted; it had been committed by Session 2b's mid-session catch-up). Always verify before asserting tracking state.
- **Padding triage responses with structure that doesn't earn its space.** Headers + bullets + tables when a few sentences would do is noise. The developer reads carefully; respect their time.
- **Introducing new strategic framings without operator approval.** This is the operator-drives discipline. If you have a new framing in mind, present it as "want to discuss?" not as fait accompli.
- **Proposing action when only triage is needed.** Sometimes the right response is "clean session, standing by." Don't manufacture next steps just because the developer asked for triage.
- **Re-litigating decided framings.** The decisions in §"Recent decisions and framings" are settled. Don't reopen them unless the developer does.
- **Vacuous regression tests.** A test that passes under both pre-fix and post-fix code is worse than no test. Memory file `feedback_regression_test_arithmetic.md` captures the canonical example.
- **Mid-session scope expansion.** Bug-class issues discovered mid-session in OTHER surfaces should be flagged in return reports, not fixed inline. The pipeline-linkage session correctly flagged `build_watchlist` per this discipline.
- **Treating "diagnose, don't decide" as soft.** When a study or diagnostic is scoped as descriptive, sneaking in implicit recommendations through "should" framings or threshold suggestions violates scope. The reviewer will catch this; better to write the discipline in correctly the first time.
- **Re-fetching expensive data when it can be cached.** yfinance has rate limits. Diagnostic studies should use cache-warm patterns; never burn yfinance quota for re-runs of already-fetched data.
- **Brief internal inconsistency between "mirror canonical" and prose-asserted counts.** When a brief points the implementer at a canonical template AND prescribes an independent count of cases, the count must match the canonical OR the deviation must be called out explicitly. The build_watchlist mixed-anchor fix brief had §0 say "mirror canonical" (3 tests) and §4.1 say "add a second test" (2 implied); implementer correctly chose canonical-template fidelity but had to do judgment work I should have done at draft time. Always cross-check prose counts against any canonical references the brief points at.
- **Bug-fix investigation that tests plausible mechanisms instead of operator's actual reproduction.** Bug 2 (trade entry form vanishes mid-typing, 2026-04-25) demonstrated this failure mode: implementer interpreted operator's ambiguous symptom report ("when I adjust the price") as form submission with stop≥entry; built TestClient probe of POST /trades/entry with stop=entry; got 500 + bare-div response that gets hoisted out of `<tbody>` by HTML parser; declared mechanism identified; built fix for that path. Adversarial review approved because the fix was internally correct. Operator manual verification revealed the actual mechanism was different (sizing-hint span hx-target inheritance from parent form). First fix `04ef355→20d2cab` was correct for ITS mechanism but wasn't operator's bug; required follow-up `2a167d1` for the actual cause. **Pattern to avoid:** treating implementer's interpretation of operator's symptom as ground truth. For UI bugs especially: TestClient confirms server-side behavior but doesn't verify the bug fires through the path the operator is hitting. **Mitigation:** see §"Operating processes" §"Bug-fix briefs and operator-confirmation gate" — INVESTIGATION-FIRST bug-fix briefs must include an operator-confirmation gate between investigation and fix.

---

## Pre-Codex review + brief-authoring disciplines

> **Relocated (compressed) from CLAUDE.md 2026-05-28** per the operator-paired CLAUDE.md size restructure (Option B: compress code gotchas in CLAUDE.md + split process/review disciplines here). These are the **process / review / brief-authoring meta-disciplines** — they fire at orchestrator / dispatch / Codex-review time, NOT at code-write time (code-failure gotchas stay in `CLAUDE.md`). Full pre-compression verbatim text (dates, commit SHAs, Codex rounds, findings docs) → [`docs/CLAUDE.md-archive.md`](docs/CLAUDE.md-archive.md) §"Appended 2026-05-28". `#N` / "Expansion #N" labels are preserved so cross-references in shipped briefs still resolve. **Apply all of these in the pre-Codex review pass at every dispatch's brainstorming + writing-plans + executing-plans phases** (the cumulative "C.C lesson #6 validation").

### Pre-Codex review "Expansion #N" catalog (verify-before-lock)

- **Expansion #2 — brief-vs-actual-production-function-signature.** When a brief/spec/plan references a production function, grep its DEFINITION + verify (a) signature (param names, positional vs keyword, types); (b) side-effect contract (read-only vs write vs fetch-on-miss); (c) error semantics (raises vs None vs default); (d) documented invariants. Re-grep at writing-plans.
  - **#2 sub-refinement — cascade-call-graph.** Also verify whether the function invokes its documented sibling helpers (grep the body); don't infer cascade from naming/docstring. Under `from __future__ import annotations`, resolve return annotations via `typing.get_type_hints`, not raw `inspect.signature` (returns string forms).
- **Expansion #4 — SQL skeleton column verification.** Every SQL skeleton's columns / JOIN-ON / WHERE / subquery verified against the actual `swing/data/migrations/*.sql` before publishing. Brief-vs-actual schema reality check: grep migrations for any proposed NEW table/column before claiming it's new (it may already exist).
  - **#4 refinement — JOIN-cardinality + downstream-sufficiency.** Per JOIN, enumerate 1:1 vs 1:N; verify the result row-set is SUFFICIENT for the consumer (e.g. an RS-criterion evaluator needs the FULL universe, not just candidates); re-check the universe after any harness mutation (cleanup/fetch/fill).
  - **#4 sub-refinement — runtime-binding-shape + empty-result-set.** Per parameterized SQL, enumerate the binding shape (scalar vs list vs dict) and empty-input handling. (The sqlite3 list-bind / dynamic-`?` / empty-short-circuit specifics are also kept as a code gotcha in CLAUDE.md.)
- **Expansion #6 — content-completeness audit.** For each spec data-surface checklist item, enumerate per-field disposition LIVE / V1 PLACEHOLDER / V1 STUB before Codex. Silently rendering a stub as if it were live is the failure mode.
- **Expansion #7 — cross-row semantic scope audit.** For any POST handler consuming operator input + a cross-row lookup, enumerate the lookup SCOPE (ticker / pattern_class / candidate / pipeline_run) + cross-check against the spec's wording; add a plant-different-scope discriminating test.
- **Expansion #8 — per-counter / SQL-aggregation UNIT audit.** For each COUNT/SUM/GROUP BY AND each Python accumulator, state what unit it counts; add DISTINCT or CTE-then-aggregate to prevent JOIN-cardinality inflation; verify LIMIT applies at the right unit. Applies to ANY counter, not just SQL aggregates.
- **Expansion #9 — form-render anchor lifecycle audit.** For any hidden form anchor driving POST-time validation, audit 4 dimensions: (a) soft-warn confirm `form_values` round-trip; (b) GET-time query-param consumption; (c) candidate-snapshot consistency across pipeline runs; (d) explicit-anchor-vs-latest-snapshot validation order. (POST-time rejection-ladder + server-recompute are code gotchas in CLAUDE.md.)
- **Expansion #10 — architecture-location audit (+ 4 sub-disciplines).** When wiring NEW logic into an EXISTING module, verify the module has the dependency-context to host it (else new module + DI). Sub-disciplines: (a) triangulate template-vs-VM-parser-vs-emitter for "doesn't render" gaps; (b) renderer-kwargs uniformity LOCK + cache-collision test when a surface enum is reused by 2+ callers; (c) SQL LIKE wildcard-escape raw-vs-escaped per binding position; (d) orphan-label preservation when refactoring exact-match → delimiter-aware groupings.
- **Expansion #11 — taxonomy / attribution propagation audit.** When introducing a NEW enum (`kind`/`status`/`type`) OR any attribution metadata (`variable_name`/`source`/`tier`), propagate to all derived dataclasses + serializers (CSV/JSON/markdown headers) + test fixtures; downstream rendering must map by the FIELD, not a value-matching heuristic; paired `old_X`/`new_X` must source from the SAME baseline.
- **Expansion #12 — sibling-route audit under single-anchor-binding.** When introducing a single-anchor-binding discipline at one route, enumerate ALL sibling routes touching the same data/cache layer + verify each carries the anchor; the NO-RUN scenario must refuse a silent "resolve-latest-now" fallback (explicit None-guard + unavailable banner).
- **Expansion #13 — cumulative regression cascade audit.** When a Codex MAJOR fix RESTRUCTURES code (extract function / move logic out of a loop / new field), run an "imagined next-round" pass for 2nd-order regressions before invoking the next round; add tests for the NEW invariants the restructure creates.
- **Expansion #14 — recency / filter / dedup semantic-ordering audit.** For N sequential filter/dedup/aggregation steps, audit order of operations + attribution-metadata propagation (max/min/all of which field) + the downstream consumer's reference asof (filter-admit vs walk-forward must use the same asof).
- **Expansion #15 — narrative artifact path/fact lag.** A post-fix-bundle commit MUST sweep ALL narrative docs (findings, return reports, study writeups, status lines) for stale artifact paths + per-row facts (entry dates, R-values, session/column counts) whenever a new smoke artifact is emitted or any outcome shifts.
- **Expansion #16 — ASCII discipline scope clarity.** Declare ASCII scope EXPLICITLY across ALL flowing-through-stdout surfaces (narrative + source + tests + smoke + manifest + CLI help) and assert programmatically via `text.encode("ascii")` over the declared set. (The CLI-stdout cp1252 crash is a code gotcha in CLAUDE.md.)
- **Expansion #6/#7 process note — the 5-expansion pass does NOT catch content-completeness vs spec text NOR cross-row semantic scope on operator-input flows** unless #6 + #7 are run explicitly; pre-Codex review must walk each spec data-surface item + each cross-row lookup scope.
- **Pre-Codex review must cross-check spec source-of-truth against dispatch-brief sketches** — the brief's prescriptions (caps, tuples, thresholds) may be wrong vs the spec's BINDING text at the cited section; verify against the spec, not the brief alone.

### Brief-authoring + applied-research methodology disciplines

- **(#33) Cohort-validity-vs-verdict-criteria.** Briefs with criterion-based verdict thresholds MUST additionally bind the evaluation cohort; if the canonical cohort yields fewer than N patterns, report INSUFFICIENT SAMPLE — do NOT substitute a more-favorable alternative cohort. (Banned narrative terms LOCK also lives here.)
- **(#34) Brief-prescription cross-table verification.** When a brief prescribes a (sweep_point + count) tuple from an analytical artifact, cross-check the artifact SUMMARY TABLE (authoritative) against the per-variable drill-down header; the summary table wins on disagreement.
- **(#35) Substrate-density metric disambiguation.** When a brief carries a numerical anchor (density/survival/rate/fraction) from a prior arc, quote the exact numerator + denominator + pre-filter + semantic intent; verify metric-compatibility with the new brief's usage (e.g. `F/T` per-ticker productivity ≠ `F/R_raw` survival rate).
- **(#36) Two-Codex-chain default for applied research dispatches.** Default to TWO Codex chains: chain #1 implementation review BEFORE smoke-artifact emission; chain #2 methodology + narrative review AFTER smoke + findings draft. Single-chain requires explicit Sec 7 justification (e.g. <100 LoC, no smoke, no findings narrative). The single C.C-lesson-#6 validation slot spans both chains.
- **(#37) Substrate-freshness sensitivity.** Briefs carrying a prior-arc cohort fixture + R-value anchor MUST cite (a) the cohort fixture SHA; (b) the filter params; (c) the source-artifact SHA the fixture derived from; (d) a regeneration-stability assertion. Implementer Slice-1 discriminating test asserts brief-stated N matches actual filtered-N within tolerance; escalate via Brief Amendment on mismatch (cohort fixtures regenerated over time drift their FILTERED membership — `max_observed_asof_date` shifts patterns in/out of recency windows).
- **(#38) Pre-commission premise verification — does the capability already exist?** Before scoping a NEW-capability arc (new command/module/mechanism), grep ALL of `swing/` for a PRE-EXISTING mechanism that already provides it — not just the one adjacent mechanism you happen to know. The capability-level analog of Expansion #4's "grep migrations before claiming a table is new." Failure mode (17-C, 2026-06-13): the orchestrator commissioned `swing exports cleanup` for exports retention having found only the adjacent `_prune_shadow_expectancy_artifacts`; `swing/rendering/retention.py:archive_old_exports` (a DIFFERENT package) already zip-retained dated `exports/<date>/` dirs every pipeline run → the arc was redundant at the 90d default + data-UNSAFE at shorter windows. Caught only at writing-plans by the implementer's brief-vs-live-code grounding (Expansion #2). Grep BEYOND the package you expect; verify the arc's FOUNDING PREMISE ("X doesn't exist yet"), not just the referenced-function signatures. Memory: `feedback_brief_premise_check_existing_mechanism`.
- **V1-simplification banking discipline.** Every V1 placeholder / stub / simplification the implementer ships MUST be enumerated in the return report (§6 or equivalent) WITH its V2 dependency cited. Pre-Codex review's content-completeness audit (#6) is the gate; the return-report table is the permanent ledger.

### Process hygiene

- **(#1) Test-count drift in plan docs.** Plan/brief test-count estimates go stale — trust `pytest` output, not the plan. (Same failure family as cohort-size estimates being empirically falsified.)
- **Auto-memory staleness.** The auto-memory at `~/.claude/projects/.../memory/` can go stale (e.g. `project_refactor_intent`); verify against current `git log` before relying on it.

---

## Maintenance: retention discipline

> Added 2026-05-05 as part of the handoff-document structural separation refactor. This section governs ongoing curation of this file + `docs/phase3e-todo.md` to keep fresh-orchestrator bootstrap consumption bounded over time.

### Active vs archive boundary

Two pairs of handoff docs:

- `docs/orchestrator-context.md` (active; canonical filename) + `docs/orchestrator-context-archive.md`
- `docs/phase3e-todo.md` (active; canonical filename) + `docs/phase3e-todo-archive.md`

Bootstrap discipline: fresh-orchestrator session reads only the active files (this one + `docs/phase3e-todo.md`) + `CLAUDE.md` + `git log -20` + `git status`. Archive companions are searchable on demand via Grep / Read.

### Cooldown rules (when to migrate)

Migration triggers, in order of frequency:

1. **End of phase ship.** When a phase merges to main, migrate that phase's SHIPPED `phase3e-todo.md` entries to the archive. One-phase cooldown (don't archive the same phase that just shipped — give one ship-cycle of "still warm" context). Worked example: Phase 7 shipped 2026-05-05 at `c617777`; Phase 6 SHIPPED entries (Phase 6 sub-bundle of journal v1.2) migrated to archive at this dispatch. Phase 7 SHIPPED entry migrates to archive at end of next phase ship (Phase 8 or Phase 9, whichever lands first).
2. **Lessons-captured cap.** Active `Lessons captured` section maintains last ~30 entries. When a new lesson lands and pushes the count past 30, the oldest lesson migrates to archive (or promotes to CLAUDE.md if it's durable code-failure prevention; see below).
3. **Recent-decisions supersession.** When a "Recent decisions and framings" entry is fully superseded by a later decision, archive the old entry with a cross-ref to the superseding one. When refined (not fully superseded), keep both with cross-ref. Default-conservative: when in doubt, KEEP in active. Re-litigation risk dominates.
4. **Tripwire-fired entries.** When a trigger-gated `phase3e-todo.md` entry resolves (e.g., 2026-05-04 worktree-cleanup-script entry RESOLVED 2026-05-05), migrate to archive with `TRIGGER FIRED + RESOLVED YYYY-MM-DD` footer. Mirror the worktree-cleanup-script + handoff-document-growth precedents.

### Lesson promotion: archive vs CLAUDE.md

For lessons being aged out of the active section:

- **Promote to CLAUDE.md gotchas** if the lesson durably prevents code failure for future sessions (e.g., yfinance API regressions; HTMX failure surfaces; Windows ACL gotchas; SQL/Python idiom collisions; matplotlib mathtext quirks). CLAUDE.md is auto-loaded so the gotcha fires every session, not just when grep'd.
- **Archive (no promotion)** if the lesson is process-only / single-incident-historical / discipline-applied-to-orchestrator-thread (e.g., commit-message convention refinements; subagent-collision diagnosis history; specific phase-handoff items).

Most older lessons (the 96 archived 2026-05-05) fall into "archive only" — their durable code-failure prevention has already landed in CLAUDE.md gotchas. Re-promotion would duplicate.

### Archive-split trigger (hierarchical decomposition deferred)

If an archive file exceeds **~80k tokens** (mirrors the active-file pressure point that motivated the original split), revisit hierarchical decomposition. Likely categorization at that point: SHIPPED-by-phase + lessons-by-domain (HTMX / yfinance / Windows / SQLite / dispatch-discipline / brief-drafting) + decisions-by-quarter. Defer category invention until the trigger fires — data informs categories better than upfront design.

### Size-check trigger at housekeeping-commit time (added 2026-05-18 PM per CLAUDE.md evaluator pass — Option B2 restructure)

At every housekeeping-commit step (when appending a new SHIPPED entry to status-tracking docs), verify the following soft thresholds — if exceeded, the housekeeping commit MUST include a triage step (archive-split, restructure, or compact-summary swap) rather than silently growing the surface:

| Doc | Surface | Soft threshold | Trigger response |
|---|---|---|---|
| `CLAUDE.md` line 3 ("Current state" summary) | Single paragraph; pointer-heavy; not a SHIPPED ledger | **>2,000 chars** | Trim back to ~5-10 sentences; preserve as compact summary; do NOT regress to a ledger paragraph (history goes to `docs/CLAUDE.md-archive.md`). |
| `CLAUDE.md` §"Gotchas" (added 2026-05-28 Option B) | Code/runtime/test failure-prevention; **trigger + fix only** | **>~55K chars total, OR any single gotcha >~700 chars, OR a process/review discipline added here instead of to orchestrator-context** | Compress the new/oversized gotcha to trigger+fix at banking time; relocate any process/review/brief-authoring discipline to this file's §"Pre-Codex review + brief-authoring disciplines"; append the full forensic detail (dates/SHAs/Codex-rounds) to `docs/CLAUDE.md-archive.md`. Do NOT bank verbose multi-paragraph forensic gotchas into CLAUDE.md. |
| `docs/orchestrator-context.md` §"Currently in-flight work" | Active + "Prior state" sub-sections | **>10 "Prior state" sub-sections retained** (per L-W2 conservative cap) | Trim oldest "Prior state" sub-sections to `docs/orchestrator-context-archive.md`. |
| `docs/orchestrator-context.md` §"Lessons captured" | Most-recent N retained per cap target | **>~40 entries** (cap target ~30; trigger at +10 over) | Migrate oldest 5-10 to archive companion. |
| `docs/phase3e-todo.md` (active SHIPPED entries) | Top-prepended SHIPPED entries | **>~25 SHIPPED entries** retained (or one quarter's worth) | Archive-split old SHIPPED entries to `docs/phase3e-todo-archive.md`. |
| `docs/CLAUDE.md-archive.md` + `docs/orchestrator-context-archive.md` + `docs/phase3e-todo-archive.md` | Append-only history companions | **No size threshold** (append-only by design) | N/A — companion docs grow; grep-on-demand only. Per §"Archive-split trigger" above, hierarchical decomposition reconsidered at ~80k tokens per file. |

**Rationale for the line 3 cap:** the Phase 12.5 #3 evaluator pass (2026-05-18 PM) surfaced that line 3 had grown to ~133K chars (~40K-50K tokens loaded into every fresh Claude Code session). Option B2 restructure replaced it with a compact ~1.3K-char "Current state" summary; this cap discipline prevents regression to the wall-of-text shape. The "current state" line is meant to be a 5-10-sentence orientation for fresh sessions, pointing them at `docs/orchestrator-context.md` + `docs/phase3e-todo.md` for detail.

**Pattern for triage at housekeeping-commit time (operator-driven OR orchestrator-self-checked):**
1. Pre-commit (before drafting the housekeeping commit message): compute size of each surface above (`wc -c`, char counts, sub-section counts).
2. If any threshold exceeded: PAUSE the housekeeping-commit + draft a restructure plan + escalate to operator decision (do NOT defer to next session — defer leads to drift; the wall-of-text shape that motivated this discipline emerged precisely because per-session size pressure was below per-session deferral pressure for months).
3. If thresholds clear: proceed with housekeeping-commit normally.

**Where this discipline applies:** every housekeeping commit landing after an integration merge OR after a meaningful in-flight decision worth recording in handoff docs. The operator-facing daily routine at [`docs/cycle-checklist.md`](docs/cycle-checklist.md) does NOT include this discipline (it's purely operator-trading-cadence; housekeeping is an orchestrator action). A brief cross-reference is added at the bottom of cycle-checklist.md so operators reviewing the routine doc are aware that orchestrator-side housekeeping discipline lives here.

### Invocation cadence

- **At session-end after each ship:** quick check whether SHIPPED items in `phase3e-todo.md` should be migrated; whether the lessons cap has been exceeded; whether any "Recent decisions" have been fully superseded.
- **Operator-explicit:** operator can request retention-discipline pass at any time (e.g., "do a housekeeping pass on the handoff docs").
- **Quarterly or longer:** revisit the active-vs-archive boundary holistically; archive entries that are now firmly historical even if they didn't fire a per-incident trigger.

### What this section does NOT govern

- The structural-separation refactor itself (one-time work; SHIPPED 2026-05-05).
- Removing content from `CLAUDE.md` §"Quick Start" / §"Strategy" / §"Architecture" / §"Invariants" / §"Conventions" / §"Windows + gitbash" sections (these are curated by their own discipline; project-conventions are append-mostly). **Note (2026-05-18 PM Option B2 restructure):** the CLAUDE.md line 3 "Current state" summary IS governed by the size-check trigger above. **Note (2026-05-28 Option B restructure):** the §"Gotchas" section is NOW governed by the size-check trigger above and is NO LONGER exempt — new code gotchas are banked as compressed trigger+fix; process/review/brief-authoring disciplines are banked into this file's §"Pre-Codex review + brief-authoring disciplines" (NOT CLAUDE.md); full forensic detail goes to `docs/CLAUDE.md-archive.md`. The remaining body sections (Quick Start / Strategy / Architecture / Invariants / Conventions / Windows + gitbash) are NOT governed (per this exclusion).
- Memory entries (`MEMORY.md` index + per-memory files at `~/.claude/projects/.../memory/`); those have their own retention semantics.

---

## Lessons captured (with cross-references)

> **ARCHIVED 2026-06-12 (Phase-16 close, retention discipline):** the 30 full lesson
> narratives (~48K chars, Phase-12→15 era) moved verbatim to
> [`docs/orchestrator-context-archive.md`](orchestrator-context-archive.md)
> §"Lessons captured — archived at Phase-16 close". The durable code-facing
> essence lives in CLAUDE.md §Gotchas; the process essence in §Operating
> processes / §Pre-Codex disciplines above. The TITLE INDEX below is the
> grep-trigger — match a title here, read the full text in the archive.

- Schema-CHECK + Python-constant + dataclass-validator MUST land in the same task for atomic consistency.
- Cross-column CHECK precedence: schema-defended is defense-in-depth; service-layer is primary path.
- Plan-author schema additions DURING the writing-plans Codex chain need explicit spec-amendment-or-escalation BEFORE landing — not bank-after-write.
- Plan-size budget for architectural-pivot writing-plans: 3000-3700 lines for 4 sub-sub-bundles × ~50 tasks; 25% over schema-design-plan budget.
- 9-substantive-round Codex chain is the new project high-water mark (Phase 12 Sub-bundle C brainstorm 2026-05-15 at `d682c25`); chain shape healthy when finding-count taper is monotonic-with-cascade-cleanup-spikes; 4C+26M+15m total findings; ZERO ACCEPT-WITH-RATIONALE.
- Brainstorm-time composition-source claims need empirical verification BEFORE spec encoding; brief-author "spec will compose validators from shipped repos" is unfounded if shipped repos don't expose callable validators.
- Persisted-JSON-tier-1 vs re-fetched-tier-1 asymmetry: data shape constrains classifier determinism — when V1 mapper exposes less than the source provides, the missing-detail case MUST tier-2 even if the operator-locked tier-1 model would naively apply.
- Synthetic-fixture-only acceptance test for production-write-contract surfaces: don't contaminate production audit trail when payload-required choices exist in a multi-choice resolution menu.
- Brief enumeration of shipped CHECK enums needs empirical verification against migration files BEFORE encoding as binding §1.5 / §0.7.
- Orchestrator MUST commit the executing-plans dispatch brief to main BEFORE providing the inline dispatch prompt to operator — recurring procedural gap (2026-05-15 instance + prior unspecified instances; operator-surfaced 2026-05-15: "This is not the first time").
- Operator-paired-gate-caught implementation gap → orchestrator-inline gate-fix (precedent: 11B `34be84e` + 12A `e2c0384` + 12B `7b75d4a` — now 3 instances cumulatively).
- Operator architectural pushback supersedes orchestrator scope assumptions; reframe before bandaging.
- Brief-recommended technical micro-decisions should be empirically pre-tested against multi-row + same-second cases before plan adoption; "clever value-mangling" patterns (sign-flip, negative IDs, sentinel encoding) are fragile under concurrent insertion + tiebreak edge cases.
- Convergent multi-round Codex chains are healthy at 4-9 rounds when fix-introduced regressions are the failure mode; R-final confirmation pass with no new findings is a valid stopping pattern; tapered finding count is the diagnostic.
- Brief-premise empirical-verification extends to brainstorm-phase, not just writing-plans-phase.
- Repo functions must NOT call `conn.commit()` — caller controls transaction scope.
- Subprocess cfg-propagation: child-process CLI body is the binding override point, NOT the parent process that spawns it.
- HTMX form-driven endpoints have two browser-only failure surfaces TestClient cannot detect: HX-Request header reset on embedded forms + HX-Redirect for success-path response.
- Worktree-isolated dispatches + editable installs need verify-command pointed at the worktree, not the editable-install path.
- Exchange-session helper family has multiple members; brief author MUST specify forward (`action_session_for_run`) vs backward (`last_completed_session`) semantically.
- Brief-scoped read-only consumer modules force scope-vs-DRY tradeoff at writing-plans time.
- State-bearing entities require enumeration of ALL state-transition UI surfaces in the brief, not just the creation path.
- Production-write classifier soft-block under auto-mode: AskUserQuestion responses are NOT visible to the auto-mode classifier; only chat-text "yes, run X" authorizations are.
- `tomli_w.dump` is a one-way TOML serializer: comments + key-order + whitespace are dropped on write.
- Operator's "pause" means STOP all forward motion immediately, even items appearing independently confirmed.
- At worktree-side operator-witnessed gates, the `swing` console-script routes to the editable-install path (main repo), NOT the worktree's code. Use `python -m swing.cli <subcommand>` from worktree cwd.
- Orchestrator's wall-clock duration estimates for dispatched work are routinely 3-5x too long. When estimating Phase work, divide naive estimate by 3-5x to land on operator's actual experienced wall-clock.
- Sub-bundle architectural fix can hold in negative sense (no regression) while positive lift fails to fire — synthetic-fixture-vs-production-emitter shape drift family.
- Per-run-vs-per-fill re-emission family: each fresh reconciliation_run that finds no Schwab match for an open fill emits a new `unmatched_open_fill` discrepancy on that same fill, regardless of prior resolutions.
- Bash tool's persistent cwd across invocations CAN drift away from the primary worktree if earlier commands `cd` into a subdirectory. Use `git -C "<absolute-path>"` for cross-worktree git operations rather than relying on cwd.

## External tools available

Capabilities outside the repo that orchestrator/implementer sessions may consult during conversation. Listing them here so future sessions know they exist; details and governance status live in the linked docs.

- **`qullamaggie` MCP server** — knowledge-base wrapper around Kristjan Kullamägi's trading commentary (437 stream sessions, Oct 2019 – Dec 2021; ~2.5M words; 3,980 rules; 84 setup types; 1,214 tickers). Eight tools surfaced as `mcp__qullamaggie__*`. Configured user-global in `~/.claude.json`; runs as a daemon at `http://localhost:9871/mcp`. Source repo: `C:\Users\rwsmy\qullamaggie-mcp\`. **Reference-only; not a source-of-truth.** Promoting any aspect to production criteria or methodology requires V2.1 §VII.F. Full tool inventory, invocation patterns, and gotchas: `docs/qullamaggie-mcp-capabilities.md`.

---

## Memory entries (cross-session persistence)

The Claude memory system has these durable entries relevant to this project:

- **`MEMORY.md`** index lists project memories (3 new banked 2026-05-17):
  - `project_references.md` — Disciplined Swing Trader PDF + Minervini physical-only book.
  - `project_refactor_intent.md` — refactor later, not now.
  - `feedback_regression_test_arithmetic.md` — verify test arithmetic distinguishes pre-fix from post-fix.
  - `feedback_pause_means_pause.md` (NEW 2026-05-17) — operator's "pause" means STOP all forward motion immediately, even items appearing independently confirmed.
  - `feedback_worktree_cli_invocation.md` (NEW 2026-05-17) — at worktree-side gates, `swing` routes to editable-install path NOT worktree; use `python -m swing.cli` from worktree cwd.
  - `feedback_time_estimates_overstated.md` (NEW 2026-05-17) — orchestrator wall-clock estimates 3-5x too long; divide naive estimates by 3-5x for actual operator-paced wall-clock.

If you make a meaningful process discovery worth carrying across sessions, save it as a memory entry AND update this file's "Lessons captured" section.

---

## Key file locations

| Location | Contents |
|---|---|
| `CLAUDE.md` (root) | Current-state, conventions, gotchas. Auto-loaded. |
| `docs/Bugs.txt` | Operator-reported bug list. |
| `docs/phase3e-todo.md` | Operational backlog (active; canonical filename). |
| `docs/phase3e-todo-archive.md` | Archived SHIPPED + closed entries (grep on demand). |
| `docs/cycle-checklist.md` | Daily/weekly/monthly operator routine. |
| `docs/*-brief.md` | Dispatch briefs (one per implementer session). |
| `docs/superpowers/specs/` | Phase-design specs (e.g., Tranche B-ops session 1 design). |
| `docs/orchestrator-context.md` | This file (active; canonical filename). |
| `docs/orchestrator-context-archive.md` | Archived older lessons + superseded framings (grep on demand). |
| `docs/qullamaggie-mcp-capabilities.md` | Reference for the qullamaggie MCP server (tool inventory, governance status, suggested invocation patterns). |
| `reference/Future Work/` | V2.1, rebuttal-response, archived predecessors. |
| `reference/Future Work/QuantEcon/` | Forward-looking strategic content (program + companions + external references). |
| `reference/methodology/` | Source-of-truth methodology references (e.g., Minervini Trend Template transcription). |
| `research/README.md` | Research branch intro. |
| `research/method-records/` | Method records per V2.1 §IV.B format. |
| `research/studies/` | Study designs and evidence summaries. |
| `research/notes/` | Research notes (data-source evaluations, decision memos). |
| `research/harness/` | Research code (e.g., earnings_proximity replay harness). |
| `swing/` | Production codebase (consumed read-only by research branch). |
| `~/swing-data/swing.db` | Production SQLite DB (outside Drive). |
| `~/swing-data/research-cache/` | Research-branch OHLCV + earnings caches (outside Drive). |

---

## Session-start checklist for fresh orchestrator sessions

1. Read this file end-to-end.
2. Check `git log --oneline -20` to see recent commits.
3. Check `git status` to see untracked files or modified files.
4. Read `CLAUDE.md` (auto-loaded but worth re-skimming for the gotchas list).
5. Skim `docs/phase3e-todo.md` for current operational backlog.
6. Ask the developer: "What's currently in flight or recently dispatched? What's today's question?"
7. If the developer is mid-decision, present options with recommendation; don't decide for them.
8. If the developer raises a new strategic question, propose where in the existing framing it fits before drafting anything.

---

## Session-end checklist (when wrapping up a working session)

1. Update §"Currently in-flight work" with current state.
2. If a meaningful framing decision was made, add to §"Recent decisions and framings."
3. If a process insight was captured, add to §"Lessons captured."
4. If a new file or convention was introduced, update §"Key file locations" or §"Operating processes."
5. **Retention discipline check (per §"Maintenance: retention discipline" above):** end of phase ship → migrate that phase's SHIPPED `phase3e-todo.md` entries to archive (one-phase cooldown); lessons-captured cap exceeded → migrate oldest to archive (or promote to CLAUDE.md if durable code-failure prevention).
6. Don't update for trivia. Bias toward fewer, higher-quality updates.

---

## How to update this file

Small commits via the regular implementer-dispatch pattern, OR direct orchestrator edit during conversation (the developer will commit later as part of housekeeping). Either is fine.

When updating: keep sections in their current order. Add new sub-bullets rather than restructuring sections. The next orchestrator's mental model is shaped by the current organization; preserve it unless the developer agrees to a reorganization.

If active sections grow large enough that bootstrap becomes a token-budget issue, see §"Maintenance: retention discipline" — the structural-separation pattern is established (active vs archive companion); migrate aged content to `docs/orchestrator-context-archive.md` rather than splitting active into multiple files.
