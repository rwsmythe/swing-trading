# Orchestrator Context — Persistent Handoff File

**Audience:** Future orchestrator-role Claude sessions for the Swing Trading project. Also useful as a reference when the current orchestrator's context window is compacted.
**Purpose:** Provide enough context to bootstrap an orchestrator role without re-reading conversation history. Not a complete project spec — pointers to authoritative sources are throughout.
**Last updated:** 2026-04-25 (post-Finviz-pool + hypothesis-label + binding-constraint analysis settled)

---

## How to use this file

If you are a fresh orchestrator session: read this file end-to-end before engaging with the developer. Then check `git log --oneline -20` to see what's landed recently, then check `git status` to see what's untracked or modified.

If you are the same orchestrator post-compaction: skim the **Currently in-flight work** and **Recent decisions** sections to recover state, then continue.

This file is project-specific and lives in the repo. Update it (small commits) whenever you make a meaningful framing decision, capture a new operating process, or accumulate a lesson worth carrying forward. Avoid bloat — pointers to authoritative documents beat duplicated content.

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

**As of 2026-04-25 (post-Finviz-pool + hypothesis-label):**

- **S&P 1500 universe expansion study** — SHIPPED. Commits `a921e4b` (D1) → `4a372da` (D5 R3). Tier 2 — Mixed (2.39× rate uplift; 48.6% absent earnings; clean sector/liquidity).
- **Finviz-pool per-criterion binding-constraint analysis** — SHIPPED. Commits `618cb9c` (D1) → `6ca6a40` (D5 R2). Descriptive characterization on 14 qualifying production evaluation_runs (8-day snapshot; 1,209 evaluations; 6 distinct CSVs). **Bucket distribution: aplus=3 watch=249 skip=898 error=45 excluded=14.** Watch:A+ ratio 83. **Top blocker: `proximity_20ma` at 44.17%** — structural consequence of operator's tight Finviz filter selecting for already-extended momentum tickers. **Near-A+ defensible subset: 15 rows / 2 distinct tickers (SLDB, UCTT) × 3 days; every defensible row fails `proximity_20ma` only.** Doctrine-defensible miss set frozen at D1: TT8_rs_rank, risk_feasibility, proximity_20ma. Adversarial review caught 5 majors + 3 minors across 3 rounds, including manifest-integrity and sentinel-conflation findings; all resolved.
- **Trade hypothesis label Phase 3e change** — SHIPPED. Commits `1cec5df` → `123f83c`. Migration 0007 adds nullable `hypothesis_label TEXT` column to `trades`; entry path + CLI `swing trade entry --hypothesis` flag + `swing journal review` aggregation by label. Phase 2 carve-out respected; one deviation (pure-compute placement in `swing/journal/stats.py` to mirror existing `compute_stats` pattern) accepted with rationale. Adversarial review pushed canonicalization scope beyond brief minimum (NFC normalization, control-char stripping, etc.) for grouping-key stability — defensible expansion. 822 fast tests passing combined with parallel Finviz-pool work.
- **No work currently in flight.**

**Operational branch outcome data: n=1 as of 2026-04-25.** First closed trade (VIS, ~-10% loss; framework-recommended sub-A+ meeting TT + price threshold). Stop-loss discipline functioned. Production DB is source-of-truth for trade outcome details. Statistically nothing; case-study informative.

**All queued follow-ups in `docs/phase3e-todo.md`.**

**Active operator constraints (refined 2026-04-25):**

- Solo developer, ~4–8 hrs/week sustained (V2.1 §III.7 time-budget anchor); operator confirms time is non-binding for current workflow scale.
- Operator capital: $7,500. **Capital tie-up is the primary forward constraint** (~50 trade/year ceiling at full deployment under Minervini sizing; ~14% per position × ~5 concurrent × ~10 cycles/year). At Minervini-typical expectancy, ceiling translates to 20-40% annual return — well above operator's 10% target.
- Universe: SPX+NDX baseline; S&P 1500 adoption decision pending operator call.
- Pipeline cadence: daily; no trade-execution friction.
- Manual chart-pattern review: non-binding for throughput at current capital ceiling; **chart-pattern algorithm is for ENCODING qualitative input into structured feedback-loop data, not for throughput acceleration.**
- A+ identification rate on operator's actual Finviz pool: order-of-magnitude ~40-100/year per Finviz-pool study extrapolation + Session 2a anchor (NOT the ~2/year baseline I had been using; that was on broad SPX+NDX universe, not operator's filtered pool).

---

## Recent decisions and framings (don't re-litigate)

These have been settled with the developer's explicit approval. Don't reopen unless they ask.

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
- **(2026-04-25) Evidence gap framing.** Current operational rate (~2 trades/year confirmed by operator; harness-derived ~2.5 A+/year on SPX+NDX 1×) is too low to produce trade-outcome data sufficient for framework evaluation. Research-derived rate-uplift candidates (universe broadening, allowed-miss extension, criteria refinement) are tools to escape the rate-vs-evidence recursive bottleneck. As of 2026-04-25, operational branch has produced n=1 trade outcome (VIS); the loop has begun to break but evidence accumulation will take time.
- **(2026-04-25) S&P 1500 universe expansion: Tier 2 — Mixed.** 2.39× rate uplift point estimate over SPX+NDX 1× baseline (Wilson CIs overlap, so the difference is suggestive not formally significant on this single window); 48.6% absent earnings data; clean sector + liquidity profile. Capital-fit sub-finding: risk_feasibility blocking is LOWER on mid-cap universes than large-cap at operator's actual capital, contrary to naive expectation. Operator-decision pending on whether to adopt the lever; not re-litigated absent new evidence.
- **(2026-04-25) Sub-A+ trading is in operator's actual practice.** VIS trade was framework-recommended at sub-A+ (TT + price threshold; missing some A+ criteria). Practice precedes principle: the "willing to relax absolute A+ doctrine" framing post-dates the actual deviation. Future workflow discussion should treat sub-A+ trade-taking as a practice-supported reality, not a hypothetical.
- **(2026-04-25) Operational branch as evidence-generation surface.** Operator is willing to take hypothesis-tagged sub-optimal trades within risk discipline, treating losses as cost-of-development rather than investment loss. Each trade requires a frozen pre-trade hypothesis label (free-text initially via the `hypothesis_label` column shipped 2026-04-25). Pre-registration discipline applies — label is set at entry and frozen; outcome-driven re-labeling is anti-pattern. This shifts operational posture from "execute proven framework" to "execute candidate framework variations to generate evidence" — V2.1 promotion path running in reverse to escape the rate-vs-evidence bottleneck.
- **(2026-04-25) A+ identifications ≠ trades (statistical analysis discipline).** A+ is a production classification (bucket assignment); trade is an operator decision to enter a position. They should be analyzed as separate measurements; do not conflate. Operator's intent is to trade every A+ but that's not a hard rule, AND going forward trades will outpace A+ identifications because of hypothesis-tagged sub-A+ trade evidence collection. Statistical aggregations (rate, expectancy, etc.) should preserve the distinction.
- **(2026-04-25) Identification rate recalibration.** A+ identification rate on operator's actual Finviz pool is plausibly ~40-100/year per Finviz-pool study extrapolation (8-day snapshot produced 2 unique A+ decisions on 6 distinct CSV-days). NOT ~2/year. The earlier "2/year" framing came from candidate-sparsity diagnostic on broad SPX+NDX universe; Finviz pool is a much tighter pre-filter that implicitly enforces TT criteria, raising the conditional A+ rate substantially. The "2/year" framing is retired.
- **(2026-04-25) Binding constraint is capital tie-up, not identification rate.** Capital ceiling at $7,500 × ~14% per position × ~5 concurrent × ~10 cycles/year ≈ 50 trades/year. With identification volume ~40-100 A+/year + ~470/year near-A+ defensible candidates from Finviz study, candidate volume already exceeds throughput capacity. Time, pipeline cadence, manual chart-review, and trade-execution friction are all non-binding at current scale. Implication: rate-uplift levers (universe broadening, allowed-miss extension) matter less than I previously framed; operational use of existing infrastructure matters more.
- **(2026-04-25) Chart-pattern algorithm is for encoding, not throughput.** Operator's manual chart assessment is fast enough to saturate capital today. The algorithm's value is structuring the qualitative chart-pattern dimension of trade decisions into the feedback-loop's analyzable data. Without it, hypothesis-label free-text absorbs chart-pattern info qualitatively (interim solution). When chart-pattern algorithm exists, it becomes a structured field; hypothesis-label holds remaining qualitative dimensions. Chart-pattern algorithm is important but NOT urgent; multi-session copowers cycle when ready. Phase 3e §3e.6 captures the original scope.
- **(2026-04-25) Next-horizon priority: operational use of newly-built infrastructure, not additional development.** Hypothesis-label infrastructure ships; Finviz-pool study identifies near-A+ defensible candidates (SLDB, UCTT). The actually-urgent next move is operational — take hypothesis-tagged trades, accumulate evidence, let the feedback loop run. Watch-staging UI is a small operational change with immediate value. S&P 1500 adoption decision is operator-pending. Chart-pattern algorithm and other development work are not urgent.
- **(2026-04-25) 10% return target math.** With $7,500 capital, ~50 trade/year ceiling at full deployment, and Minervini-typical expectancy (~0.5-0.8% account return per trade), the math gives 20-40% annual return ceiling. The 10% target is well within range, not the ambitious target it was earlier framed as. Compounding + capital injection to ~$100K extends absolute returns linearly to $20K-$40K/year at the same percentage ceiling.

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

### Housekeeping commits

Periodically, accumulate untracked drift + small backlog updates + minor documentation corrections into a single small "housekeeping" commit. Pattern: `docs/{phase}-housekeeping-brief.md` brief; one-session implementer work; landing commits like `docs: track {description}`. Examples shipped: `4f74493` (Tranche B cleanup), `b03f66a` (B-ops cleanup), `2df7adb..6c179de` (post-2c housekeeping).

**Don't let housekeeping accumulate.** When 5+ untracked artifacts exist or 3+ small follow-ups have been deferred, dispatch a housekeeping commit.

---

## Binding conventions (project-wide)

These come from CLAUDE.md but are restated here because you'll be drafting briefs that enforce them:

- **Branch:** `main`. No feature branches.
- **Commits:** conventional-commits. **No Claude co-author footer. No `--no-verify`. No amending.**
- **TDD:** failing test first, minimal implementation, pass, commit. One red-green cycle per logical change.
- **Phase isolation:** during Phase 3 work, `swing/trades/` and `swing/data/` are read-only unless an explicit carve-out is granted in the brief. Carve-outs require justification and listing of specific files touched.
- **DB location:** `%USERPROFILE%/swing-data/swing.db` — outside the Drive-synced folder. Never violate this; SQLite + Drive sync = corruption.
- **Tests:** `python -m pytest -m "not slow" -q` is the fast suite; must stay green. Slow suite (`-m slow`) is network-dependent; don't require it for routine validation.
- **Ruff:** `ruff check swing/` baseline is 81 errors (pre-existing). Briefs forbid introducing new violations; don't try to fix the baseline incidentally.
- **Adversarial review** on code-shipping sessions is mandatory (standing convention).

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

---

## Lessons captured (with cross-references)

Process insights from this project's history, with examples and pointers:

- **Adversarial review catches architectural improvements TDD alone misses.** Examples: Tranche B-ops Session 2 caught `open_risk_position_count` collapse; Session 3 caught the `TradeStopFormVM.force` dead field; Tranche C pipeline-linkage caught two additional mixed-anchor surfaces (`_step_export`, `candidates_by_ticker`) beyond the brief's enumeration. **Why this works:** code review surfaces what the writer didn't think of; the writer's TDD discipline only covers what they thought to test.
- **Pre-registration discipline forces honest "defer" outcomes.** Session 2c's anti-rationalization clause held through 4 review rounds. Decision unchanged across review; only the justification framing changed. **Why this works:** the discipline is structural, not aspirational.
- **Sample-size-driven failure is a study-design failure, not a discipline failure.** Session 2c had 11 signals against ≥30 needed; the study technically completed but methodologically failed. The right framing is "process succeeded, question inconclusive."
- **Filter-rule studies need activation-rate sanity check.** Lesson from Session 2c (variant filter was a no-op because no signal had earnings within X=10 trading days). Captured as forward-looking amendment in `research/studies/earnings-proximity-exclusion.md` §Amendments.
- **Same bug class often has multiple surfaces.** Bug 7 (mixed-anchor) showed up in today_decisions, chart-scope resolver, _step_export, and candidates_by_ticker. The brief named the first two; review found the other two. **Always enumerate read-paths that touch the affected data, not just the obvious surface.**
- **Operator-drives framing protects against AI methodology homogenization.** Detailed in QuantEcon companion. The recursive concern about AI-aided development is narrowed but not eliminated by this discipline.
- **Stale-server failure mode after code changes.** Documented in CLAUDE.md gotchas. Jinja templates auto-reload; Python dataclasses do not. Always restart `swing web` after class/field changes.
- **HTMX OOB-swap partial drift.** Documented in CLAUDE.md gotchas. Use `{% include %}` to share partials between full-page and OOB-swap render paths; never hand-duplicate markup.
- **Production-gating mismatch in instrumentation can lie silently.** When instrumenting production logic for diagnostic measurement, the instrumentation must mimic production's gating order, not the criteria's emission order. Tranche C candidate-sparsity diagnostic R1 Critical caught this: original D2 walked emitted criterion order, but production `bucket_for` applies `risk_feasibility` as hard pre-filter. Net effect: capital hypothesis appeared 3.5× weaker than reality before fix. **General lesson:** instrumentation can pass unit tests and still produce systematically biased aggregate numbers if it doesn't mimic production's control flow. Production-vs-instrumentation parity needs explicit verification when measurement matters for decisions.
- **Diagnostic findings can be informational without being prescriptive.** Operator may reasonably decline to act on a diagnostic finding even when the finding is statistically meaningful. Capital-sensitivity finding (Tranche C diagnostic, 2026-04-25) is the canonical example: structural blocking change is large in proportional terms (18.6% → 1.3%) but the deterministic operational change (5 → 10 SPX A+ signals/year) doesn't cross workflow-relevance threshold for the operator's actual usage. Diagnostic does its job by surfacing the data; operator decides whether the data warrants action. Don't push action when "informational" is a defensible response.
- **Some bugs are sample-size failures, not discipline failures.** Session 2c's defer outcome with 11 signals against ≥30 needed was a study-design failure (variant filter was a structural no-op on the chosen universe), not a process failure (pre-registration discipline held through 4 review rounds, decision unchanged). Distinguish these in triage: process-level success can coexist with question-level inconclusive.
- **Brief drafting drift on tracking state.** Don't claim files are uncommitted/untracked without verifying current `git status`. The post-2c housekeeping brief mistakenly claimed `docs/Bugs.txt` was uncommitted when it had been committed by Session 2b's mid-session catch-up commit. Implementer caught and corrected. Pattern: brief drafting that touches tracking state should explicitly call for `git status` verification at dispatch rather than asserting state from orchestrator memory.
- **Manifest-integrity generalization.** Manifests must reflect actual code state at run time, not the most-recent commit when the artifact was committed. Parity-check D3 originally committed a manifest pointing at D2's SHA when the run included an uncommitted wrapper class (`_CountingPriceFetcher` for cache-stat instrumentation); R1 caught it. Generalization of the candidate-sparsity diagnostic R1 Critical lesson: instrumentation/manifest can lie silently, and adversarial review is the surface that catches it. Pattern: any artifact that asserts code-state provenance must verify against the actual run-time state, not the latest committed state. If you've been editing during a run and have uncommitted changes, your manifest's `git_sha` claim is wrong.
- **n=1 parity with non-A+ sample bounds the parity claim.** Tier 1 result on a sample with zero A+ candidates verifies parity at the watch/skip classification level but not at A+. When designing parity studies, anticipate sample composition: if the production run typically produces zero or near-zero A+, the parity verification cannot exercise A+ classification logic. Operator-facing interpretation must preserve this bound. Generalizable beyond the parity check: any classification-equivalence study should anticipate sample composition vs the bucket categories the equivalence claim covers.
- **Brief drafting: canonical-template references win over prose count assertions.** When a brief says "mirror canonical template X" and ALSO independently asserts a count of cases, but the canonical template has a different count, the implementer must do judgment work that should have been done at draft time. Build_watchlist mixed-anchor fix Brief §0 (mirror canonical, 3 tests) vs §4.1 (add a second test, 2 implied) had this inconsistency; implementer correctly chose canonical-template fidelity. Pattern: when a brief points at a canonical template, prose counts must match the template OR explicitly call out the deviation. Prefer "mirror the template (which has N cases)" over independent count assertions.
- **Grouping-key fields need canonicalization-at-persistence-boundary, not just display safety.** When a brief introduces a free-text field that becomes a grouping/aggregation key downstream, the brief should specify canonicalization-at-persistence-boundary requirements (NFC normalization, control-char handling, whitespace normalization, empty-string handling) — not just display-level safety. Trade hypothesis_label work R1/R2 caught this: brief specified "free-text safety" (display-level), but the field is the grouping key for evidence aggregation. Adversarial review pushed canonicalization scope beyond brief minimum because grouping-key instability would corrupt outcome-by-hypothesis statistics. Pattern for future briefs introducing free-text fields: ask "is this field a grouping key downstream?" If yes, specify canonicalization at the persistence boundary (e.g., inside the entry service, not at display time).

---

## Memory entries (cross-session persistence)

The Claude memory system has these durable entries relevant to this project:

- **`MEMORY.md`** index lists three project memories:
  - `project_references.md` — Disciplined Swing Trader PDF + Minervini physical-only book.
  - `project_refactor_intent.md` — refactor later, not now.
  - `feedback_regression_test_arithmetic.md` — verify test arithmetic distinguishes pre-fix from post-fix.

If you make a meaningful process discovery worth carrying across sessions, save it as a memory entry AND update this file's "Lessons captured" section.

---

## Key file locations

| Location | Contents |
|---|---|
| `CLAUDE.md` (root) | Current-state, conventions, gotchas. Auto-loaded. |
| `docs/Bugs.txt` | Operator-reported bug list. |
| `docs/phase3e-todo.md` | Operational backlog (Phase 3e items + accumulated B-ops deferred items). |
| `docs/cycle-checklist.md` | Daily/weekly/monthly operator routine. |
| `docs/*-brief.md` | Dispatch briefs (one per implementer session). |
| `docs/superpowers/specs/` | Phase-design specs (e.g., Tranche B-ops session 1 design). |
| `docs/orchestrator-context.md` | This file. |
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
5. Don't update for trivia. Bias toward fewer, higher-quality updates.

---

## How to update this file

Small commits via the regular implementer-dispatch pattern, OR direct orchestrator edit during conversation (the developer will commit later as part of housekeeping). Either is fine.

When updating: keep sections in their current order. Add new sub-bullets rather than restructuring sections. The next orchestrator's mental model is shaped by the current organization; preserve it unless the developer agrees to a reorganization.

If this file ever exceeds ~400 lines, consider splitting:

- `docs/orchestrator-context.md` — high-level (what you're reading).
- `docs/orchestrator-brief-templates.md` — brief-drafting patterns and examples.
- `docs/orchestrator-lessons.md` — accumulated process insights.

But don't split prematurely. Single-file lookup beats multi-file navigation until the file becomes genuinely unwieldy.
