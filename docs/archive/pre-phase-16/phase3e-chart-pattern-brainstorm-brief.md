# Phase 3e — Chart-Pattern Shape Estimator: Brainstorm Dispatch Brief

**Audience:** Fresh Claude Code instance with no prior conversation context.
**Mission:** Run a brainstorm-only session for the chart-pattern shape estimator (phase3e item 3e.6) via the project's `copowers:brainstorming` discipline. Produce a design spec, get adversarial Codex review on it, stop. Do NOT proceed to implementation, planning, or coding.
**Expected duration:** ~1-2 hours of operator-interactive brainstorming + 2-5 rounds of Codex review on the resulting spec.
**Drives an implementation later:** A separate, future plan-and-execute dispatch will consume this spec. Don't pre-empt it.

---

## §0 Read first

In order:

1. **`docs/orchestrator-context.md`** — project framing, operator-drives discipline, copowers workflow, anti-patterns to avoid. Pay particular attention to the 2026-04-25 entry on "Chart-pattern algorithm is for encoding, not throughput" and the 2026-04-25 framework framing.
2. **`docs/phase3e-todo.md` §3e.6** — the original backlog entry for this feature with reference image pointers (note: pointer paths in that entry are stale; correct paths are below).
3. **`CLAUDE.md`** at repo root — project conventions and gotchas. Especially: OHLCV fetch scope rule, OhlcvCache breaker, base-layout shared VM gotcha, HTMX OOB-swap partial drift, yfinance API regression patterns.
4. **`docs/qullamaggie-mcp-capabilities.md`** — capability reference for the qullamaggie MCP server, which is connected and available. The server's `get_setup_criteria('flag_pattern')` returns Qullamaggie's own criteria for flag-pattern setups; useful as a reference layer for definitional questions during brainstorm. **Reference-only**, not source-of-truth (per V2.1 §VII.F).
5. **`reference/images/flag_pattern.png`** — operator-curated reference image of a flag pattern. Definitional anchor for the V1 pattern.
6. **`reference/methodology/minervini-trend-template.md`** — Minervini methodology transcription. Source-of-truth methodology reference.
7. **`reference/Future Work/2026-04-23-bifurcated-strategic-implementation-proposal-v2.1.md`** §VII.F — the source-of-truth correction protocol. The chart-pattern algorithm is governed by this protocol IF its output ever becomes a production scoring/bucketing input. V1 is explicitly NOT scoped to that, but the brainstorm must respect the boundary.
8. **`docs/superpowers/specs/`** (browse) — examples of past spec docs. Match the structural conventions; don't reinvent.

---

## §0 Skill posture

**INVOKE:**

- `copowers:brainstorming` — this brief's primary skill. The wrapper handles operator-interactive design, spec-doc writing, and adversarial Codex review on the spec.

**DO NOT INVOKE (V1 STOP after spec is reviewed):**

- `copowers:writing-plans` / `superpowers:writing-plans` — implementation planning is NOT part of this dispatch. Orchestrator triages the spec, operator decides whether to commission a plan-and-execute dispatch.
- `copowers:executing-plans` / `superpowers:executing-plans` / `superpowers:subagent-driven-development` — no implementation in this dispatch.
- `superpowers:test-driven-development` — no code in this dispatch.

The brainstorming skill itself will engage the operator interactively. You (the implementer) drive the brainstorm conversation; the operator answers, redirects, and approves. Use the operator's own framing where it differs from yours.

---

## §1 Strategic context

The chart-pattern shape estimator's framing is **encoding qualitative chart-pattern input into structured feedback-loop data, NOT throughput acceleration**. This is binding orchestrator-context guidance:

- The operator can manually assess chart patterns at saturation rate (capital is the binding constraint, not throughput). The algorithm is NOT solving a throughput problem.
- The algorithm's value is making the chart-pattern dimension of trade decisions **structured, queryable, and analytically usable** alongside `hypothesis_label` (currently free-text).
- Pre-registration discipline applies — the algorithm is a measurement instrument, not a recommendation engine. Operator remains arbiter at trade entry.

The trade evidence loop currently captures: trade outcome (R, $, dates), `hypothesis_label` (free-text encoding of rationale), bucket classification (A+/watch/skip). The algorithm's output adds a structured chart-pattern dimension to that loop.

---

## §2 Locked constraints (operator-set; do NOT re-litigate in brainstorm)

The following decisions were made in the orchestrator-thread before this dispatch. The brainstorm must respect them. If the operator brings them up during brainstorm, acknowledge they're settled and refocus on the open design questions.

### V1 scope

1. **One pattern only: `flag_pattern`.** Prove the encoding-and-tagging pipeline end-to-end on a single shape. Other patterns (pennant, base, cup-with-handle, tight channel, qullamaggie's broader taxonomy) are V2+ additions, NOT in V1.

2. **Governance posture: display + persist on trades + confidence metric. Production scoring/bucketing UNTOUCHED.** The algorithm output is operator-facing data plus per-trade evidence. It does NOT feed `bucket_for`, `evaluation/scoring.py`, criteria evaluation, or any production decision logic. Promoting any aspect to production scoring would require V2.1 §VII.F protocol — explicitly out of V1 scope.

3. **Compute timing: pipeline-time, on chart-scope tickers.** Algorithm runs during pipeline execution for the same set that gets charts built (A+ + top near-trigger watchlist per existing chart-scope resolver). NOT at view time (no per-render cost). NOT at trade entry only (pipeline-time enables watchlist display). Result is cached/persisted from the pipeline run.

4. **Display surface: watchlist rows.** Operator scans watchlist top-N with the pattern tag visible (alongside existing `TT✓ VCP✓ A+`-style tags). Watchlist display is a primary V1 driver — operator uses it for trade evaluation, not just listing.

5. **Trade-entry consumption: cached-only for V1.** Trade entry consumes the pipeline-cached classifier result for the ticker. Out-of-scope manual trades (operator entering a trade for a ticker not in chart-scope) are NOT handled in V1 — explicit operator decision. Future V2 may add on-demand fallback fetch.

6. **Operator override at entry: store algorithm and operator values separately.** Trade row carries `chart_pattern_algo` (always populated from classifier) + `chart_pattern_algo_confidence` (always populated) + `chart_pattern_operator` (NULL unless operator explicitly overrides at entry). Effective-pattern-for-analysis = operator value if set, else algo. Enables future calibration / agreement-rate studies.

### Non-V1 (explicitly out of scope; do NOT design for these in this brainstorm)

- Additional patterns beyond flag_pattern.
- Manual-trade fallback for out-of-chart-scope tickers.
- Production scoring/bucketing changes (V2.1 §VII.F territory).
- ML / neural-net / deep-learning approaches if a deterministic geometric classifier is viable (operator preference: use the simpler approach unless there's a compelling reason otherwise; brainstorm should evaluate this).
- Multi-timeframe analysis (weekly + daily) unless brainstorm finds a strong reason daily-only is insufficient.
- Real-time / intraday classification (daily bars only).

---

## §3 Open design questions (the brainstorm's actual job)

These are the questions the brainstorm conversation should explore with the operator and resolve in the spec. NOT exhaustive — discover others as they emerge.

### Definition

- **What geometric properties define a flag pattern in this project's terms?** Consult `reference/images/flag_pattern.png`, the qullamaggie MCP `get_setup_criteria('flag_pattern')` output, and Minervini's methodology. Synthesize a project-specific definition the operator agrees with. A flag pattern has roughly: a strong prior trend (the "pole"), a brief consolidation/pullback (the "flag" itself, typically 1-3 weeks), and a continuation breakout. Quantify each element.
- **What are the acceptance and rejection edge cases?** A definition is only useful if it tells you when something is NOT a flag.

### Algorithm

- **Approach:** rule-based geometric (range CV, slope checks, ratio checks, regression-on-bars) vs. ML-based (trained on labeled examples) vs. LLM-based (call out to Claude/another model with chart data) vs. hybrid. Operator preference is the simpler approach; brainstorm evaluates whether geometric rules can express the definition with adequate fidelity.
- **Data window:** How many daily bars are required? (Minimum to detect pole + flag; cap to avoid false positives from ancient action.) Daily-only confirmed; revisit only if necessary.
- **Confidence representation:** Scale (0-1, 0-100, raw score), source (rule-confidence as min/avg of component checks, statistical fit metric, calibrated probability), and what "high confidence" means semantically.
- **Display threshold:** What confidence cutoff renders the tag on the watchlist? (Below threshold → no tag shown but still persisted on trades that fire.) How is the threshold chosen and reviewed?

### Persistence schema

- **Trade row columns** (locked: `chart_pattern_algo`, `chart_pattern_algo_confidence`, `chart_pattern_operator`). Confirm exact names, types, NULL semantics.
- **Pipeline-time result cache:** new table (e.g., `pipeline_pattern_classifications` keyed on `(pipeline_run_id, ticker)`) vs. new columns on `pipeline_chart_targets`. Tradeoffs: schema cleanliness vs. join cost vs. blast radius.
- **Migration sequencing:** likely two migrations (one for pipeline cache, one for trades columns). Number depends on existing migration sequence (currently at 0008 per orchestrator-context).
- **Cache invalidation / staleness semantics:** Pattern result is keyed to a specific pipeline run; if pipeline reruns same day, what happens? Pre-Tranche-C mixed-anchor lessons apply — bind to `pipeline_runs.evaluation_run_id` consistently.

### Pipeline integration

- **Step placement:** extend `_step_charts` (computed at chart time, since OHLCV is in hand) vs. new `_step_patterns` (separate concern, separate retry semantics). Tradeoff: cohesion vs. separation.
- **Lease-fenced write boundary:** per-ticker fenced write (mirroring `_step_charts` granularity) vs. batched write at end of step. Reuse existing patterns from Tranche B-ops/Tranche C work.
- **Failure modes:** What happens if classifier fails for one ticker? Whole step fails? Per-ticker absent-state row?
- **Performance budget:** Acceptable per-pipeline-run overhead (seconds/minutes added to current pipeline runtime).

### Watchlist display

- **Tag format:** plain text (`flag`), with confidence (`flag (0.78)`), threshold-only (`flag✓`), iconography. Decide presentation in line with existing tag convention (`TT✓ VCP✓ A+`).
- **Tag placement:** alongside existing flag tags on watchlist row, or separate column.
- **Below-threshold behavior:** no tag shown vs. dimmed tag with low-confidence indicator.
- **Sort interaction:** does the new tag participate in the existing tag-aware sort precedence (Session 2 sort-by-tags) or stay neutral?

### Trade-entry UI

- **Override mechanism:** dropdown? toggle (`accept algo / reject / select different`)? free-text override? Where in the entry form does the override surface appear?
- **Operator workflow:** by default, algorithm output is accepted (override field stays NULL) and only filled if operator actively disagrees. UI must make the algorithm value visible (so operator can disagree informedly) but not require interaction in the common case.

### Test strategy

- **Source of labeled examples:** Operator-labeled historical OHLCV data (operator picks N tickers + dates, labels each as flag/not-flag, classifier is tested against those labels)? Qullamaggie ticker_index examples (he discusses tickers with setup tags including flag-pattern; could be a label source)? Synthetic generated patterns for unit tests of geometric components?
- **Sample size:** Phase3e backlog suggested 50-100 examples. Confirm or revise.
- **False-positive vs. false-negative tolerance:** which is the worse error in V1, given the operator-arbiter stance?
- **Test directory layout:** mirrors `swing/` — likely `tests/evaluation/patterns/test_flag_pattern.py` or similar.

### Phase 2 carve-out

- **Touches `swing/data/`?** Yes (new migrations + repo functions for trades columns and pipeline pattern cache). Phase 2 carve-out required per CLAUDE.md project conventions; brainstorm spec must enumerate exactly which files in `swing/data/` are added/modified and justify each.

---

## §4 Conventions for the brainstorm output

- Spec doc location: `docs/superpowers/specs/YYYY-MM-DD-chart-pattern-flag-v1-design.md` (or whatever today's date is when brainstorming completes).
- Spec follows the project conventions (see existing specs in `docs/superpowers/specs/` for shape).
- Commit the spec doc when done. Conventional-commit message: `docs(specs): chart-pattern flag-v1 design (phase3e §3e.6)`.
- **No Claude co-author footer. No `--no-verify`. No amending.**

---

## §5 Adversarial review (handled by copowers wrapper)

The `copowers:brainstorming` wrapper automatically invokes Codex MCP review on the resulting spec. The wrapper iterates rounds until `NO_NEW_CRITICAL_MAJOR`. Pass these specific watch items to Codex via the wrapper's standard mechanism:

- **Locked-constraint violations.** Does the spec respect all six locked constraints in §2? Especially: V1 = single pattern (flag_pattern only), no production scoring change, persist on trades + confidence metric, pipeline-time compute, separate algo/operator fields.
- **Falsifiability.** Is the algorithm's output testable against the operator's intent? Can a reviewer say "this output is wrong because X" without ambiguity?
- **OHLCV scope correctness.** Pattern classification scope ⊆ chart-scope set per assumption. If the spec implies any expansion of OHLCV fetch beyond chart-scope, that's a correctness issue requiring justification or rescoping.
- **CLAUDE.md gotcha respect.** Especially OhlcvCache breaker semantics, base-layout shared VM (any new VM field needs adding to ALL base-layout VMs), HTMX OOB-swap partial drift (any new tag-rendering partial must use shared `{% include %}`).
- **Schema integrity.** Migration sequence valid (next number after 0008)? Trade-row columns NULL-safe? Cache invalidation correct vis-à-vis `pipeline_runs.evaluation_run_id` mixed-anchor lessons?
- **Mixed-anchor risk.** Any place the spec reads "latest evaluation" directly should bind to `pipeline_runs.evaluation_run_id` instead. Bug 7 family.
- **Pre-registration / governance violations.** Any sneaking-in of production scoring influence, fitness metrics that look operational, or framing that promotes the algorithm output to recommendation status.
- **Test strategy adequacy.** Is the labeled-example source identified? Sample size practical? False-positive/false-negative tradeoff acknowledged?
- **Phase 2 carve-out enumeration.** Spec lists every `swing/data/` file added/modified, with justification.
- **Discriminating tests.** For any tests proposed, the test under post-fix code must produce a different outcome than under pre-fix code (per `feedback_regression_test_arithmetic` memory). Compounding-confound failure mode (per 2026-04-26 lessons): when a test asserts on a primary key, would temporarily disabling the keyed-on element still pass the test? If so, vacuous test.

---

## §6 Done criteria

The brainstorm is done when ALL of the following hold:

- [ ] Spec doc exists at `docs/superpowers/specs/YYYY-MM-DD-chart-pattern-flag-v1-design.md`.
- [ ] Spec is committed to `main` via conventional commit.
- [ ] Spec respects all six locked constraints in §2.
- [ ] Spec addresses all open design questions in §3 (or explicitly defers any with rationale).
- [ ] Adversarial Codex review reached `NO_NEW_CRITICAL_MAJOR` verdict.
- [ ] Operator approved the spec via the brainstorming skill's review gate.

---

## §7 Return report format

Final message to orchestrator (via operator) MUST include:

```
SPEC: docs/superpowers/specs/<filename>.md
COMMIT: <SHA>
ADVERSARIAL ROUNDS: <N>; FINAL VERDICT: NO_NEW_CRITICAL_MAJOR

KEY DESIGN DECISIONS:
- Algorithm approach: <rule-based / ML / LLM / hybrid + rationale>
- Confidence representation: <scale + semantics>
- Pipeline integration: <step placement + persistence schema>
- Watchlist display: <format + threshold>
- Operator override UI: <mechanism>
- Test strategy: <label source + sample size + tolerance>
- Phase 2 carve-out: <enumerated files>

DEFERRED FROM SPEC (explicitly out of V1):
- <list of design questions deferred with rationale>

OPEN QUESTIONS FOR ORCHESTRATOR:
- <any blocker or unresolved framing issue>

ADVERSARIAL FINDINGS (each with disposition):
- <finding>: FIXED in commit <SHA> / ACCEPTED with rationale: <text>

LESSONS WORTH CAPTURING (process insights from this brainstorm):
- <bullet list>
```

---

## §8 If you get stuck

- **If a design question can't be resolved with the operator,** capture both options in the spec with explicit "DEFERRED — operator decision required" status. Don't force a decision the operator hasn't made.
- **If a locked constraint conflicts with what the brainstorm reveals as necessary,** STOP. Do NOT relitigate in brainstorm. Surface the conflict in your return report under "OPEN QUESTIONS FOR ORCHESTRATOR" and let the orchestrator handle it.
- **If Codex review surfaces a finding that contradicts a locked constraint,** apply receiving-code-review discipline (verify before agreeing). If the finding is correct AND the constraint is wrong, surface to orchestrator. If the finding is wrong, document why it's rejected with rationale.
- **If the qullamaggie MCP server is unavailable** during brainstorm, that's not a blocker — the server's capability doc summarizes what `flag_pattern` criteria look like; proceed without live MCP queries and note the absence in the spec.
- **If pre-existing code surprises you** (e.g., chart-scope resolver behaves differently than orchestrator-context describes), trust what you observe over what the docs say. Surface the doc/code drift in the return report.

---

## §9 Anti-patterns specific to this brainstorm

These have caused real problems in past sessions; resist:

- **Drifting into implementation.** This is brainstorm-only. If you find yourself writing code, scaffolding directories, or proposing exact line edits — stop. The spec describes; the future implementation dispatch executes.
- **Re-litigating locked constraints.** The orchestrator-thread already burned context settling these. They're in §2. Don't reopen.
- **Padding the spec.** A focused spec beats a comprehensive one. Each section should earn its space. The reviewer (orchestrator + operator) reads carefully.
- **Vague "TBD" placeholders.** If the brainstorm couldn't resolve something, mark it explicitly DEFERRED with rationale and the decision-point that resolves it. Never leave silent ambiguity.
- **Importing the qullamaggie taxonomy as definitional.** It's reference-only. If Qullamaggie's flag-pattern definition is useful, cite it as input but synthesize a project-specific definition the operator agrees with.
- **Designing for hypothetical V2/V3.** Build the smallest possible V1 that satisfies the locked constraints and the framing. Future patterns, multi-timeframe analysis, ML approaches, intraday classification — all explicitly deferred.
