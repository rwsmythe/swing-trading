# Bifurcated Strategic Implementation Proposal for the Swing Trading Tool

**Prepared for:** Strategic direction-setting beyond the short-term development plan

**Purpose:** To define a two-branch implementation strategy that separates historical research and verification from operator-facing product improvement while preserving a shared core where beneficial.

---

## Executive summary

The project should no longer be treated as a single undifferentiated trading tool.

It should be developed as two deliberately different branches built on a partially shared foundation:

1. **Research and Verification Branch** — designed to propose, falsify, tune, and validate methodological changes on historical data with defensible controls.
2. **Operational Trader-Facing Branch** — designed to improve live decision quality, workflow smoothness, interpretability, and execution discipline for the operator.

These branches should share a common vocabulary and selected infrastructure, but they must not be forced into identical constraints. The research branch should optimize for truthfulness and experimental rigor. The operational branch should optimize for clarity, usability, and trader performance in the real workflow.

The most important strategic decision is therefore this:

> **Do not make the production tool carry the full burden of research correctness, and do not make the research environment inherit the speed and simplicity constraints of the production tool.**

That separation resolves the core tension exposed by the methodological memo.

---

## I. Strategic rationale

The project currently sits at the intersection of two legitimate but different goals:

- building a better trading *product* for daily use;
- and building a better trading *research process* for method discovery and validation.

Those goals overlap, but they are not identical.

A single architecture can support both only up to a point. Beyond that point, the design incentives diverge:

| Dimension | Research branch | Operational branch |
|---|---|---|
| Primary question | Is this method real, robust, and promotable? | What should I do today, and why? |
| Tolerance for complexity | High | Moderate |
| Tolerance for latency | High | Low |
| Data standards | Point-in-time, survivorship-aware, reproducible | Timely, reliable, operationally convenient |
| Optimization target | Valid inference | Better decisions and smoother workflow |
| Acceptance metric | Statistical and robustness thresholds | Decision quality, usability, and trading discipline |

The wrong strategic move would be to collapse these into one environment and let each compromise the other.

---

## II. Governing design principles

### 1. Separate research promotion from production deployment

No new method should enter the operator-facing workflow merely because it is interesting, intuitive, or historically attractive in one backtest.

Every method must move through explicit states:

- **backlog**
- **specified**
- **prototype**
- **validated**
- **shadow mode**
- **production**
- **rejected or retired**

### 2. Preserve a shared conceptual kernel, not a forced shared runtime

The two branches should share:

- instrument identifiers and security master concepts,
- naming conventions for signals and features,
- formal signal definitions,
- experiment and config versioning,
- and an operator/research decision ledger where useful.

They do **not** need to share the same storage engine, vendor stack, test harness, or runtime constraints.

### 3. Prefer explicit layer ownership

Every method belongs to one primary layer:

- universe construction,
- ranking,
- trigger detection,
- sizing,
- stop logic,
- exit logic,
- regime control,
- portfolio exposure,
- or operator governance.

Methods may inform more than one layer, but each needs one declared home.

### 4. Promote only methods with clear marginal value

A method should be adopted only if it improves one or more target metrics without introducing disproportionate fragility, operator confusion, or overlap with an existing rule.

### 5. Treat structural changes as valid if they improve robustness materially

Data acquisition, storage, experiment tracking, and vendor choice are not implementation trivia. They are part of the method. Structural changes are acceptable where necessary.

---

## III. Shared foundation

Before the branches diverge, the project should establish a limited but durable common foundation.

### A. Canonical domain model

Define a shared conceptual schema covering:

- symbol and security identity;
- trading calendar and session model;
- price bar semantics;
- corporate-action handling;
- event timestamps (earnings, guidance, splits, index membership changes);
- trade, recommendation, and exposure records;
- and configuration revision history.

### B. Signal-definition registry

Every signal or method should have a formal definition object or markdown specification including:

- name;
- layer;
- formula or deterministic logic;
- parameters and defaults;
- required data fields;
- expected output shape;
- known caveats;
- and implementation status.

### C. Configuration and provenance

All branch-specific runs should stamp:

- code version;
- config version;
- data snapshot/version;
- universe version;
- vendor source;
- and execution timestamp.

### D. Method catalog and status system

Maintain a central registry with statuses such as:

- research-only,
- candidate for validation,
- shadowed in production,
- production-approved,
- deprecated.

This prevents research ideas from silently leaking into operator workflows.

---

## IV. Branch A — Research and Verification

## Mission

To create a rigorous environment where methodological changes can be proposed, tuned, stress-tested, and either promoted or rejected with defensible evidence.

## A. Objectives

1. Establish historically credible testing infrastructure.
2. Validate or falsify candidate methods from the research memo.
3. Quantify sensitivity to universe construction, lookback choice, and execution assumptions.
4. Produce promotion-ready findings for the operational branch.
5. Reduce discretionary enthusiasm by forcing explicit definitions and robustness standards.

## B. Required structural changes

### 1. Upgrade the data stack materially

The research branch should not rely on the same data assumptions as the production tool if those assumptions degrade historical validity.

Recommended upgrades:

- **Survivorship-bias-aware historical equities data** with delisted symbols and historical index constituents.
- **Point-in-time corporate actions and symbol mapping.**
- **Event datasets** for earnings dates, pre/post-market timing, guidance, and major catalysts where possible.
- **Fundamental history** if growth or earnings-based filters are to be studied seriously.

Recommended stance:

- Use a research-grade historical vendor for the research branch.
- Continue permitting a simpler operational vendor stack in production where appropriate.

### 2. Move research storage away from the production SQLite model

The current SQLite-centered architecture is a good production choice. It is not the ideal core for broad factor research, large panel studies, or repeated parameter sweeps.

Recommended research storage stack:

- partitioned parquet or DuckDB-backed data lake for panel data;
- experiment metadata store;
- artifact directory for reports, parameter sweeps, and validation summaries.

### 3. Build a formal backtesting and experiment framework

The research branch should support both:

- **cross-sectional/factor research**, and
- **event-driven single-name trigger studies**.

Suggested components:

- vectorized factor research engine for ranking and parameter sweeps;
- event-driven simulator for signal-trigger-entry-stop-exit logic;
- experiment runner with manifest-based configurations;
- walk-forward harness;
- sensitivity analysis tooling;
- and shadow-signal export for later production comparison.

### 4. Introduce hypothesis management

Every candidate method should begin as a hypothesis with:

- rationale;
- formal specification;
- intended layer;
- expected benefit;
- potential conflicts;
- and acceptance criteria.

## C. Research workstreams

### Workstream A1 — Universe and ranking research

Primary questions:

- Which relative-strength formulation is most stable and useful?
- Does multi-horizon momentum ranking outperform a single-horizon proxy?
- Do FIP or smoothness filters add value after trend-template gating?
- What is the right universe definition for the intended trading style?

Candidate studies:

- stable RS percentile vs simple 12-week excess return;
- 3/6/9/12-month ensemble ranking vs single 12-1 momentum;
- FIP as rank modifier vs hard filter;
- liquidity and market-cap thresholds;
- IPO seasoning rules.

### Workstream A2 — Trigger and pattern research

Primary questions:

- Which triggers are sufficiently deterministic to justify production use?
- Which pattern detectors are robust across regimes and data vendors?

Candidate studies:

- pocket pivot detection;
- buyable gap-up logic;
- episodic pivot definitions;
- Darvas box trigger rules;
- VCP variants with explicit contraction-sequence logic;
- AVWAP reclaim logic;
- cup-with-handle only if a stable formalization can be defended.

### Workstream A3 — Sizing and stop research

Primary questions:

- What sizing framework best balances expectancy and drawdown?
- Which stop frameworks are operationally survivable and statistically justified?

Candidate studies:

- fixed-R sizing vs ATR-normalized sizing;
- hard stop at pattern low vs ATR stop vs tighter of the two;
- partial-profit rules vs full trail rules;
- earnings blackout and event-risk handling;
- volatility-scaled gross exposure.

### Workstream A4 — Regime and portfolio overlay research

Primary questions:

- Which regime filters improve outcomes materially without destroying opportunity?
- Should portfolio overlays remain outside the operator tool or feed it indirectly?

Candidate studies:

- simple trend filters on benchmark indices;
- accumulation/distribution-day state models;
- follow-through-day logic;
- volatility-targeted exposure scaling;
- optional monthly overlay studies such as GEM/Faber-style allocators.

### Workstream A5 — Operator-behavior analytics

Primary questions:

- Where does operator discretion improve or degrade system performance?
- Which human overrides are beneficial, and which are systematically harmful?

Candidate studies:

- accepted vs skipped recommendations;
- manual stop deviations;
- early exits vs model exits;
- effect of trading during caution/bearish regimes;
- recurring behavioral errors and their cost in R-multiples.

## D. Research methodology standards

Every study should define:

- universe construction rules;
- rebalance cadence;
- signal timing semantics;
- event timestamp assumptions;
- slippage and transaction-cost model;
- position-cap and exposure-cap rules;
- out-of-sample protocol;
- and robustness tests.

Minimum robustness requirements should include:

- walk-forward evaluation;
- parameter perturbation analysis;
- alternate universe checks;
- alternate regime slices;
- and false-discovery awareness when many variants are tested.

## E. Promotion criteria from research to operational branch

A candidate method should be promotable only if it is:

1. **Formally specified**
2. **Historically robust**
3. **Understandable enough to explain to the operator**
4. **Compatible with the operational workflow**
5. **Not redundant with existing rules**
6. **Capable of stable implementation under the production data stack or a justified production-grade replacement**

---

## V. Branch B — Operational Trader-Facing

## Mission

To make the tool materially better at helping the operator find, understand, size, manage, and review trades under real-world constraints.

## A. Objectives

1. Improve decision clarity.
2. Reduce friction in the daily workflow.
3. Make risk, invalidation, and regime context explicit.
4. Support disciplined execution and post-trade learning.
5. Introduce only methods that are stable, explainable, and operationally valuable.

## B. Required structural changes

### 1. Upgrade the operational data layer selectively where it improves actual decision quality

The production tool does not need to mirror the full research vendor stack, but it does need timely and dependable operational data.

Potential upgrades include:

- more reliable EOD and near-real-time prices;
- explicit earnings and catalyst calendar integration;
- historical intraday bars where trigger mechanics require them;
- stronger caching and fallback logic;
- and cleaner separation between reference material, exports, and mutable state.

### 2. Expand the operator model from “screen and report” to “decision support system”

The tool should not only state that a setup exists. It should answer:

- why it qualifies,
- what invalidates it,
- what the preferred entry and stop are,
- how much risk is implied,
- whether market regime supports new exposure,
- and what to do if the setup gaps, triggers, or fails.

## C. Operational product workstreams

### Workstream B1 — Candidate ranking and focus management

Add or improve:

- stable focus ranking using the best validated rank factors;
- explicit ranking rationales;
- ranking stability indicators;
- group or theme context where useful;
- “why this is not top-ranked” diagnostics for near-misses.

### Workstream B2 — Trigger and setup explanation

For each candidate, produce:

- trigger type;
- exact actionable level;
- stop basis;
- distance to trigger and stop;
- quality flags;
- and a short narrative explanation.

This is where validated pattern detectors such as pocket pivots, buyable gap-ups, Darvas breaks, and robust VCP logic should surface.

### Workstream B3 — Risk and trade-construction support

Add or improve:

- suggested shares and R-risk at multiple risk budgets;
- portfolio-cap awareness;
- earnings-proximity warnings;
- gap-risk warnings;
- exposure throttles based on regime;
- and better stop-adjustment guidance.

### Workstream B4 — Regime and exposure dashboarding

The tool should present regime as an operational state, not just a hidden classifier.

Examples:

- risk-on / caution / risk-off stance;
- evidence supporting that stance;
- recommended exposure band;
- count of distribution or warning signals;
- and a plain-language explanation of what that means for new trades.

### Workstream B5 — Journaling and decision audit

The production branch should log:

- what the system recommended;
- what the operator actually did;
- what changed afterward;
- and where the operator deviated.

This creates the feedback loop needed to improve both tool and trader.

### Workstream B6 — Workflow and UX improvements

Continue improving:

- watchlist lifecycle management;
- daily briefing clarity;
- chart embedding and chart annotation;
- open-position dashboards;
- inline trade actions;
- error handling and recovery;
- and visibility into pipeline freshness and failure states.

## D. Operational method-adoption rules

A production method should be accepted only if it is:

- easy to explain;
- easy to audit afterward;
- not excessively parameter-sensitive;
- compatible with the operator’s timeframe and workflow;
- and net-positive for decision quality, not merely historically interesting.

Methods that remain too fuzzy or too data-hungry should stay research-only.

---

## VI. Interaction model between the branches

The two branches should not be isolated silos. They should interact through a disciplined promotion pipeline.

### A. Research → Operational

Research outputs should be delivered as promotion packages containing:

- method definition;
- evidence summary;
- implementation constraints;
- operational caveats;
- expected operator-facing explanation;
- and shadow-mode validation plan.

### B. Operational → Research

Production usage should generate questions for research, such as:

- recurring false positives;
- ranking instability;
- methods the operator ignores;
- setup classes with weak realized expectancy;
- and performance by regime or market cap segment.

### C. Shadow mode

Before full promotion, a candidate method should run in shadow mode inside the operational branch:

- visible to logs and evaluation artifacts;
- optionally visible to the operator as secondary information;
- but not yet allowed to drive primary recommendations.

This is the safest bridge between historical validation and live usefulness.

---

## VII. Recommended strategic architecture

## A. Core production stack

Keep and strengthen the current production principles:

- modular Python package;
- clear layer boundaries;
- SQLite or similar operational store outside synced folders;
- explicit audit rows for mutable trading actions;
- nightly pipeline plus dashboard;
- deterministic recommendation artifacts;
- and strong unit/golden testing.

## B. Parallel research stack

Stand up a separate research environment with:

- research-grade data vendor(s);
- parquet/DuckDB or equivalent research store;
- vectorized research notebooks or scripts for ranking studies;
- event-driven simulator for trade logic;
- experiment manifest system;
- and report generation for promotion decisions.

## C. Shared artifacts

Share only what is worth sharing:

- formal signal specs;
- universe definitions where compatible;
- method cards;
- promotion decisions;
- and selected validation summaries.

---

## VIII. Concrete strategic roadmap

## Phase 0 — Governance and definitions

1. Create the signal-definition registry.
2. Create method cards for all serious candidates from the research memo.
3. Assign each method to a layer and a branch status.
4. Define promotion criteria and validation templates.

## Phase 1 — Research branch foundation

1. Select the historical data stack.
2. Build the research data model and experiment store.
3. Stand up ranking and event-driven backtest harnesses.
4. Reproduce baseline results for the current operational logic.

## Phase 2 — Operational branch strengthening

1. Improve decision explanations and risk presentation.
2. Upgrade earnings/event awareness.
3. Improve ranking diagnostics, regime display, and chart context.
4. Expand journaling of recommendation vs action.

## Phase 3 — First promotion cycle

Select a limited set of candidates for serious promotion, preferably:

- improved RS / momentum ranking;
- one or two validated trigger families;
- stronger regime/exposure signaling;
- and better sizing / earnings-risk logic.

Run them in shadow mode first.

## Phase 4 — Portfolio-level expansion only if justified

Only after the single-name and workflow foundations are strong should the project consider:

- portfolio overlays,
- broader allocation logic,
- monthly trend allocators,
- and more ambitious short-side systems.

---

## IX. Recommended initial candidate set

To keep the program disciplined, the first research-to-production promotion cycle should focus on a narrow set of high-value candidates.

### Highest-priority research candidates

- Stable RS and multi-horizon momentum ranking
- Pocket Pivot detector
- Buyable Gap-Up detector
- Earnings-proximity and event-risk rules
- ATR/ADR-informed sizing and stop frameworks
- Regime and exposure throttles

### Research-only until proven otherwise

- VCP formalization variants beyond a conservative baseline
- FIP as a live production modifier
- AVWAP-based management logic
- GEM/Faber-style overlay integration into the same operator tool
- Expanded short-selling frameworks
- More ambitious state-machine management systems

---

## X. Final recommendation

Adopt the bifurcated model explicitly.

The project is now large and serious enough that it should stop pretending one architecture can satisfy both research rigor and operational simplicity equally well.

The correct strategic stance is:

- **one disciplined research branch** to discover and validate methods,
- **one disciplined operational branch** to help the trader act better every day,
- and **a formal promotion pathway** between them.

That structure preserves ambition without sacrificing coherence.

It also turns the original methodological memo into something genuinely valuable: not a confused basis for one tool, but the upstream research reservoir feeding a mature two-branch trading system.
