# Bifurcated Strategic Implementation Proposal for the Swing Trading Tool — Revised

**Date:** 2026-04-23
**Supersedes:** `2026-04-22-bifurcated-strategic-implementation-proposal.md` (PROP v1)
**Companion documents:**
- `2026-04-22-formal-critique-extending-methodological-basis.md` (CRIT) — diagnostic, retained as-is
- `2026-04-22-rebuttal-critique-and-implementation-proposal.md` (REBUTTAL) — line-level findings, basis for this revision
- `2026-04-17-swing-ground-up-refactor-design.md` (DESIGN) — production-tool ground truth
- `Extending methodological basis.md` (SRC) — original research compendium

**Audience:** Future Claude Code / Codex agent sessions, and the developer directly. Strategic document, not implementation. Implementation artifacts (signal registry files, Phase 0 task lists, pre-commit hooks) are downstream from this document and produced in code-side sessions against the actual repo.

**Reading order for downstream agents:** This document → CLAUDE.md (current repo state) → DESIGN (architectural baseline) → REBUTTAL Part 4 (priority synthesis) → CRIT (for diagnostic context only). Original PROP v1 can be skipped — this document supersedes it in full.

---

## Executive summary

The project should be developed as two deliberately different branches built on a partially shared foundation:

1. **Research and Verification Branch** — designed to propose, falsify, tune, and validate methodological changes on historical data with defensible controls.
2. **Operational Trader-Facing Branch** — designed to improve live decision quality, workflow smoothness, interpretability, and execution discipline for the operator.

These branches share a common vocabulary and selected infrastructure, but they are not forced into identical constraints. The research branch optimizes for truthfulness and experimental rigor. The operational branch optimizes for clarity, usability, and trader performance in the real workflow.

The most important strategic decision is therefore this:

> **Do not make the production tool carry the full burden of research correctness, and do not make the research environment inherit the speed and simplicity constraints of the production tool.**

That separation resolves the core tension exposed by CRIT §II.4.

**State of play as of 2026-04-23.** The operational branch is materially further along than PROP v1 acknowledged. Phase 3d has shipped; 504 fast tests are green on `main`; the Phase 3e backlog is captured in `docs/phase3e-todo.md`. The research branch does not yet exist as a distinct entity. This document's roadmap (§VIII) reflects that asymmetry: the immediate work is to stand up the research branch and the shared kernel, not to begin operational improvements that are already in flight.

**Methodological sources, divided by concern.** *The Disciplined Swing Trader* (Lakes / Qullamaggie synthesis) governs the operator-level methodology — daily/weekly process, psychology, discipline, the "what should I do today" workflow. Minervini, academic momentum research, and practitioner rule-sets (Morales/Kacher, Stockbee, Clenow, Gray-Vogel) govern the signal-computation methodology — how the universe is gated, how setups are detected, how trades are sized and managed. Both concerns are within scope; the bifurcated architecture implements this division physically: the research branch works on signal computation; the operational branch implements both signal output and operator workflow.

---

## I. Strategic rationale

The project sits at the intersection of two legitimate but different goals:

- building a better trading *product* for daily use;
- and building a better trading *research process* for method discovery and validation.

These goals overlap, but they are not identical. A single architecture can support both only up to a point. Beyond that point, the design incentives diverge:

| Dimension | Research branch | Operational branch |
|---|---|---|
| Primary question | Is this method real, robust, and promotable? | What should I do today, and why? |
| Tolerance for discretionary complexity | High, bounded by experimenter sanity | Moderate, bounded by operator interpretability |
| Tolerance for latency | High | Low (nightly pipeline target ≤10 min; currently 2–5 min observed per `docs/cycle-checklist.md`) |
| Data standards | Point-in-time, survivorship-aware, reproducible | Timely, reliable, operationally convenient |
| Optimization target | Valid inference | Better decisions and smoother workflow |
| Acceptance metric | Statistical and robustness thresholds | Decision quality, usability, trading discipline |

Note that the operational branch already has substantial complexity (pipeline lease tokens, two-date semantics, staged artifact promotion, force-clear recovery — see DESIGN §5). The distinction between branches is not complexity *level* but complexity *purpose*.

The wrong strategic move would be to collapse these into one environment and let each compromise the other.

---

## II. Governing design principles

### 1. Separate research promotion from production deployment

No new method enters the operator-facing workflow merely because it is interesting, intuitive, or historically attractive in one backtest.

**Lifecycle states:** `backlog → specified → prototype → validated → production → deprecated → retired`. A method may be `rejected` from any state prior to production. A special status `production-unvalidated` exists for methods that entered production without passing through the formal validation cycle (typically: methods that pre-date the research branch's existence, like the production criteria currently shipping in the operational tool). These methods are first-class registry citizens but flagged for retroactive validation; see §III.D and §VII.E.

**Shadow mode is a modifier, not a lifecycle state.** A production-state method may run a shadow variant alongside its primary rule set, visible in logs and operator UI, without the shadow variant driving primary decisions. This is how challengers earn promotion (see §VI.D).

### 2. Preserve a shared conceptual kernel, not a forced shared runtime

The two branches share:

- instrument identifiers and security master concepts;
- naming conventions for signals and features;
- formal signal definitions (the registry — §III.B);
- experiment and config versioning;
- an operator/research decision ledger where useful;
- timezone and session semantics (DESIGN §5.5 two-date model is the standard, not optional).

They do **not** need to share the same storage engine, vendor stack, test harness, or runtime constraints.

**Acknowledged cost.** This separation is not free of friction: a signal proven in the research environment (Parquet/DuckDB panel data) must be re-implemented against the production environment (SQLite per-ticker rows) before promotion. Budget time for this conversion explicitly. The signal-definition registry (§III.B) and the parity test requirement (§IV.B.2) mitigate but do not eliminate this cost.

### 3. Prefer explicit layer ownership

Every method belongs to one primary layer:

- universe construction
- ranking
- trigger detection
- sizing
- stop logic
- exit logic
- regime control
- portfolio exposure
- operator governance
- monitoring / observability (drift detection, stale-data alarms, post-promotion degradation tracking)

Methods may inform more than one layer, but each needs one declared home.

### 4. Promote only methods with clear marginal value against a specific baseline

A method is adopted only if it improves one or more target metrics without introducing disproportionate fragility, operator confusion, or overlap with an existing rule. Marginal value must be stated *against a specific baseline* — a method is not "better" in isolation; it is better than the specific rule it replaces or the specific gap it fills. This forecloses the rationalization "the new method is interesting, so it must add value."

### 5. Treat structural changes as valid if they improve robustness materially

Data acquisition, storage, experiment tracking, and vendor choice are not implementation trivia. They are part of the method. Structural changes are acceptable where necessary.

---

## III. Shared foundation

Before the branches diverge, the project establishes a limited but durable common foundation. The production branch has already implemented several of these (DESIGN §3 `config_revisions`, `pipeline_runs.rs_universe_version`, `trade_events` audit log); the research branch inherits these patterns rather than inventing parallel conventions.

### A. Canonical domain model

Shared conceptual schema covering:

- symbol and security identity;
- trading calendar and session model — **the two-date model from DESIGN §5.5 (`data_asof_date` / `action_session_date`) is canonical**, using the NYSE calendar via `exchange_calendars` or `pandas_market_calendars`. Backtests that collapse the two dates into one produce subtle look-ahead bugs; the research branch must inherit this discipline rather than re-derive it;
- price bar semantics, including the partial-bar gotcha during market hours (CLAUDE.md notes `yfinance history(interval="1d")` includes the in-progress bar; strip via the exchange-session helper);
- corporate-action handling — **decomposes into five distinct problems**: splits, dividends, mergers, ticker changes, and delistings. Each has different implications for signal computation. Research branch requires point-in-time handling of all five; production branch can rely on yfinance adjusted prices for splits and dividends but must handle the others explicitly;
- event timestamps (earnings, guidance, splits, index membership changes);
- trade, recommendation, and exposure records;
- configuration revision history.

### B. Signal-definition registry

The signal registry is the mechanism by which methods proven in research become implementable in production without re-derivation. It is the single highest-leverage shared asset in the bifurcated architecture and warrants concrete specification rather than a sketch.

**Format.** TOML for human-editability, with a Python dataclass mirror generated from the spec file for programmatic access. JSON is rejected as not hand-editable. One file per signal, located in a `signals/` directory at the repo root (exact path to be decided in the implementation session against the actual repo layout).

**Required fields per signal:**

- `name`, `version` (semver: `MAJOR.MINOR.PATCH`)
- `layer` — one of: `universe`, `ranking`, `trigger`, `sizing`, `stop`, `exit`, `regime`, `portfolio`, `governance`, `monitoring`
- `status` — one of: `backlog`, `specified`, `prototype`, `validated`, `production`, `production-unvalidated`, `deprecated`, `retired`
- `formal_definition` — formula or deterministic logic, with inline citations to source (book page, paper DOI, URL)
- `parameters` — name, type, default, valid range, tuning constraints
- `required_data_fields` — OHLCV, fundamentals, corporate actions, etc., with timing semantics
- `output_shape` — scalar / series / ranked list / boolean / tuple
- `operator_explainability` — three forms:
  - **Single-sentence rationale** (what the trader sees on the recommendation card)
  - **One-paragraph explanation** (what the trader sees on expand)
  - **FAQ entry** for the most common objection
- `predecessor` / `supersedes` — references to the registry entries this method evolved from. Without this field the registry is flat and loses dependency structure (Pocket Pivot supersedes naive volume-breakout; FIP refines raw momentum; Barroso–Santa-Clara scaling supersedes naive momentum exposure).
- `known_caveats` — edge cases, regime dependencies, failure modes
- `evidence_tier` (1–4 — see §IV.D for definitions)
- `hypothesis` / `test_design` / `decision_rule` — populated before any backtest is run (see §IV.D pre-registration)

**Versioning rules.**

- **Patch (`0.0.x`):** documentation or comment changes only, identical output. Production branches may auto-upgrade.
- **Minor (`0.x.0`):** parameter default changes, additional optional fields, backward-compatible. Production branches may auto-upgrade.
- **Major (`x.0.0`):** output semantics change, parameter removal, formula correction. Never auto-upgraded; requires explicit promotion cycle (see §VI.A).

**Deprecation protocol.** A deprecated signal must specify its replacement (by registry key) and a transition window (default 30 days). During transition, both signals run in production with the deprecated one marked in operator UI.

**Catalog ownership.** In a solo-developer context the catalog owner is the developer. The *discipline* of keeping it current is the operational constraint. Rule: no method moves between states without a catalog update in the same commit. This is enforced by a pre-commit hook (implementation deferred to code-side session) that validates catalog-state transitions against the git diff. See §VII.E for the failure mode this prevents.

### C. Configuration and provenance

The production branch has already implemented config revision tracking (`config_revisions`), pipeline run auditing (`pipeline_runs`), universe versioning (`pipeline_runs.rs_universe_version`), and immutable trade event logs (`trade_events`) — see DESIGN §3 and §5.1. The research branch inherits these patterns and the shared provenance schema formalizes them rather than introducing new conventions.

All branch-specific runs stamp:

- code version (git SHA)
- config version (`config_revisions.id`)
- data snapshot/version
- universe version (per DESIGN §4.1 RS universe versioning)
- vendor source
- execution timestamp

### D. Method catalog and status system

A central registry where every method's `status` (per §II.1 lifecycle states and §III.B field schema) is the single source of truth for whether the method is in research, in production, deprecated, or retired. Combined with the shadow-mode modifier (§II.1 / §VI.C), this fully describes any method's relationship to operator-facing decisions.

Two operational properties of the registry:

- **It prevents research ideas from silently leaking into operator workflows** — a method without `status=production` cannot drive primary recommendations, by enforcement at the operational-branch boundary.
- **It prevents production methods from drifting outside the registry's view** — every signal producing operator-facing recommendations must have a registry entry, even production-validated methods that bypassed the formal promotion cycle (which receive `status=production-unvalidated` until validated). See §VII.E for the failure mode this prevents.

---

## IV. Branch A — Research and Verification

### Mission

Create a rigorous environment where methodological changes can be proposed, tuned, stress-tested, and either promoted or rejected with defensible evidence.

### A. Objectives

1. Establish historically credible testing infrastructure.
2. Validate or falsify candidate methods from SRC.
3. Quantify sensitivity to universe construction, lookback choice, and execution assumptions.
4. Produce promotion-ready findings for the operational branch.
5. **Reduce discretionary enthusiasm by forcing explicit definitions and robustness standards.**

### B. Required structural changes

#### 1. Bootstrap-first data strategy

The research branch begins with **free data sources** (yfinance plus a manually maintained delistings list derived from SEC filings and exchange notices) to validate the branch's architecture before committing to paid infrastructure.

Norgate ($630/yr as of 2026) or equivalent paid survivorship-bias-free data is added only when specific criteria are met:

- A specific study's results change by more than a documented threshold (e.g., ≥15% expectancy difference) between bias-free and biased data, AND
- The study's conclusions will inform a production promotion, AND
- No free alternative has been identified in reasonable search

This sequencing preserves the data-quality principle (CRIT-I.2 / SRC's first-paragraph note that survivorship-bias-free data is the single biggest technical dependency) while avoiding premature infrastructure commitment. It also gives the project real experience with its own bias exposure before paying to fix it.

The production branch's data vendor decision is separate (see §V.B.1).

#### 2. Move research storage off the production SQLite model

The current SQLite-centered architecture is a sound production choice. It is not the ideal core for broad factor research, large panel studies, or repeated parameter sweeps.

Research storage stack:

- partitioned Parquet or DuckDB-backed data lake for panel data;
- experiment metadata store;
- artifact directory for reports, parameter sweeps, and validation summaries.

**Promotion bridge requirement.** A promoted signal's computation function must be specified such that it runs against both the research data model (panel Parquet with multi-ticker time-indexed data) and the production data model (per-ticker SQLite rows queried on demand) and produces identical output for identical inputs. This is verified by a **parity test** that is part of every promotion package (see §VI.A).

#### 3. Build a formal backtesting and experiment framework

The research branch supports both:

- **cross-sectional / factor research**, and
- **event-driven single-name trigger studies**.

Suggested components:

- vectorized factor research engine for ranking and parameter sweeps;
- event-driven simulator for signal-trigger-entry-stop-exit logic;
- experiment runner with manifest-based configurations;
- walk-forward harness;
- sensitivity analysis tooling;
- shadow-signal export for later production comparison.

**Minimum specification for the event-driven simulator** (event-driven single-name backtests are a common source of bugs that look good on paper and fail in production):

1. Realistic slippage modeled as a function of ADR (e.g., 5–10% of ADR for market-order entries at breakout).
2. Gap-through of stops with configurable behavior (execute at gap-open price, not at stop price).
3. Earnings-date blackout with configurable lookback (default: no new entries within 5 trading days of announced earnings).
4. Fractional-share vs whole-share sizing modes (production uses whole shares; research should test both).
5. Degradation protocol when intraday data is unavailable: fall back to OHLC-only simulation and flag the trade in the output.

#### 4. Hypothesis management with pre-registration

Every candidate method begins as a hypothesis with:

- rationale;
- formal specification;
- intended layer;
- expected benefit;
- potential conflicts;
- acceptance criteria;
- **explicit null** — the world-state in which the method doesn't work — so the test has a falsifiable outcome.

"I think this improves expectancy, let me backtest it" is not a hypothesis. "This method improves expectancy by ≥0.1R in bullish regimes and ≤neutral in other regimes, with p-value ≤0.1 on a 10-year sample" is a hypothesis.

**Pre-registration.** Before running a study, commit the hypothesis, the test, and the decision rule in the method card. This is the cheapest anti-overfitting control available and it has zero runtime cost. Enforce via the rule that the method card's `hypothesis`, `test_design`, and `decision_rule` fields must be populated and committed before the first backtest run.

### C. Research workstreams

#### Workstream A1 — Universe and ranking research

Primary questions:

- Which relative-strength formulation is most stable and useful?
- Does multi-horizon momentum ranking outperform a single-horizon proxy?
- Do FIP or smoothness filters add value after trend-template gating?
- What is the right universe definition for the intended trading style?

Candidate studies:

- Stable RS percentile formulation (against universe definitions and time);
- Multi-horizon momentum ranking (3/6/9/12-month ensemble vs single 12-1);
- FIP as rank modifier vs hard filter (FIP is coupled to ranking decisions, not independent — see §IX);
- Liquidity and market-cap thresholds;
- IPO seasoning rules.

#### Workstream A2 — Trigger and pattern research

Primary questions:

- Which triggers are sufficiently deterministic to justify production use?
- Which pattern detectors are robust across regimes and data vendors?

Candidate studies:

- Pocket pivot detection (fast-track candidate — see §IX);
- Buyable gap-up logic;
- Episodic pivot definitions;
- Darvas box trigger rules;
- VCP variants beyond the conservative DESIGN §4.2 baseline (the baseline is acceptable and not demoted; this workstream addresses ambitious extensions);
- AVWAP reclaim logic;
- Cup-with-handle only if a stable formalization can be defended.

The reason VCP and similar pattern families are research-only beyond the conservative baseline is that each requires prior segmentation of a time series into regime states before the pattern can be identified, and segmentation is itself an open problem with no canonical solution. These are not implementation tasks; they are research projects in their own right.

#### Workstream A3 — Sizing and stop research

Primary questions:

- Which sizing framework best balances expectancy and drawdown?
- Which stop frameworks are operationally survivable and statistically justified?

Candidate studies:

- Fixed-R sizing vs ATR-normalized sizing;
- Hard stop at pattern low vs ATR stop vs tighter of the two;
- Partial-profit rules vs full trail rules;
- Earnings blackout and event-risk handling;
- Volatility-scaled gross exposure.

#### Workstream A4 — Regime and portfolio overlay research

Primary questions:

- Which regime filters improve outcomes materially without destroying opportunity?
- Should portfolio overlays remain outside the operator tool or feed it indirectly?

Candidate studies:

- Simple trend filters on benchmark indices;
- Accumulation/distribution-day state models;
- Follow-through-day logic;
- Volatility-targeted exposure scaling;
- Optional monthly overlay studies (GEM/Faber-style allocators) — out of scope for near-term.

#### Workstream A5 — Operator-behavior analytics

Primary questions:

- Where does operator discretion improve or degrade system performance?
- Which human overrides are beneficial, and which are systematically harmful?

Candidate studies:

- Accepted vs skipped recommendations;
- Manual stop deviations (with attention to **directional** overrides — when the operator consistently moves stops tighter or wider relative to the method's recommendation, this is a signal about either calibration or risk preference. Both require investigation. Undirected overrides are noise; directional overrides carry information);
- Early exits vs model exits;
- Effect of trading during caution/bearish regimes;
- Recurring behavioral errors and their cost in R-multiples.

#### Workstream sequencing

Workstream ordering matters because A5 cannot start without production history, and other workstreams have layered dependencies:

- **A1 (universe and ranking)** first — blocking for A2 and A4
- **A3 (sizing and stops)** in parallel with A1 — orthogonal dependencies
- **A2 (triggers and patterns)** after A1 — depends on ranked universe
- **A4 (regime and portfolio overlays)** after A2 — depends on candidate pools
- **A5 (operator behavior analytics)** last — requires ≥6 months of production history with the operational-branch journaling of recommendation-vs-action implemented (see §V.C.5)

**Why A5 is last but critical.** A5 is the only workstream that cannot be done in isolation from production. It is also the mechanism by which this project gets strictly better over time — every other workstream can be done with historical data alone; A5 requires the operator-system feedback loop. The corresponding production-side logging (§V.C.5) should be prioritized so A5 has data when it starts.

### D. Research methodology standards

Every study defines:

- universe construction rules;
- rebalance cadence;
- signal timing semantics;
- event timestamp assumptions;
- slippage and transaction-cost model;
- position-cap and exposure-cap rules;
- out-of-sample protocol;
- robustness tests.

**Minimum robustness requirements:**

- Walk-forward evaluation;
- Parameter perturbation analysis (±25% of nominal value, sensitivity reported);
- Alternate universe checks;
- Alternate regime slices;
- False-discovery awareness — multi-variant studies (e.g., testing momentum at 3/6/9/12-month lookbacks) must report the number of variants tried alongside the winner's statistics, so readers can apply Bonferroni-style correction mentally;
- **Data-vendor equivalence testing** — the same rule must produce equivalent bucket assignments on two independent data vendors within a specified tolerance; otherwise the rule is data-vendor-fitted rather than market-fitted (this becomes relevant once a second vendor is in play; see §V.B.1 deferred);
- **Look-ahead bias audit** — every rule must have its data dependencies inspected for forward-leakage (e.g., RS computed against end-of-period universe membership when universe was different at the time; fundamental ratios using data not yet released as of the asof date).

**Evidence tiers** (revised from CRIT §II.3 — method-specific, not source-specific):

- **Tier 1:** Peer-reviewed work with replicable methodology, OR practitioner rules demonstrated on point-in-time data with shared code.
- **Tier 2:** Serious practitioner work with documented rules and published track records.
- **Tier 3:** Open-source implementations whose correctness can be inspected, with evidence of adoption by serious practitioners (`skyte/relative-strength` for IBD-style RS, established Stockbee screeners are Tier 3).
- **Tier 4:** Commentary, podcasts, community consensus, marketing content.

A reproducible backtest with open code is stronger than a peer-reviewed paper whose data is unavailable. Tier assignment is recorded in the registry per §III.B.

### E. Promotion criteria from research to operational branch

A candidate method is promotable only if it is:

1. **Formally specified** (registry entry complete, all required fields populated)
2. **Historically robust** (passes minimum robustness requirements above)
3. **Understandable enough to explain to the operator** (operator_explainability fields present and reviewed)
4. **Compatible with the operational workflow** (does not require interaction patterns the dashboard does not support)
5. **Not redundant with existing rules** (or the redundancy is stated and the replacement plan is committed)
6. **Capable of stable implementation under the production data stack** or a justified production-grade replacement
7. **Computationally compatible** with the nightly pipeline runtime budget (target ≤10 minutes for ≤500 candidates; currently 2–5 minutes observed per `docs/cycle-checklist.md`), or a dedicated compute path with a separate latency budget must be specified. A signal that takes 20 minutes to compute per stock is research-only regardless of its expectancy.

---

## V. Branch B — Operational Trader-Facing

### Mission

Make the tool materially better at helping the operator find, understand, size, manage, and review trades under real-world constraints.

### A. Objectives

1. Improve decision clarity.
2. Reduce friction in the daily workflow.
3. Make risk, invalidation, and regime context explicit.
4. Support disciplined execution and post-trade learning.
5. Introduce only methods that are stable, explainable, and operationally valuable.

### B. Required structural changes

#### 1. Operational data layer — selective, earned upgrades

The production tool does not need to mirror the research vendor stack, but it does need timely and dependable operational data.

**Production data vendor assessment.** The production tool currently uses yfinance (DESIGN §2.2). For EOD swing trading with the current sizing and stop-discipline regime, yfinance EOD data is adequate: its OHLCV accuracy on liquid US equities is high, its adjusted-price handling is acceptable for the signal types currently deployed, and its free-tier rate limits accommodate the current nightly pipeline's load. **Production vendor upgrade is deferred unless a specific reliability incident or a new signal type requires it.** This is a separate decision from the research-branch vendor question.

Operational data improvements warranting near-term attention:

- More reliable EOD and near-real-time prices (the existing PriceCache + OhlcvCache patterns in CLAUDE.md address most of this);
- **Earnings calendar integration is harder than a one-line bullet suggests.** Free sources (yfinance, Yahoo calendar) are often wrong or late on announcement timing (before/after market). Earnings Whispers and Zacks are paid. Finviz shows expected dates but not announcement timing. For EOD swing trading, announcement timing matters because a position held through earnings has materially different risk than one entered after. Budget: expect to integrate ≥2 sources and reconcile discrepancies;
- **Intraday bars are a different class of problem from EOD improvements.** yfinance provides limited intraday history (≤60 days); serious intraday backtesting or execution triggers require paid sources. For the current EOD swing workflow, intraday bars are not required; flag as deferred unless a specific trigger rule needs them;
- Stronger caching and fallback logic;
- Cleaner separation between reference material, exports, and mutable state (largely accomplished by DESIGN's `swing-data/` outside-Drive convention).

#### 2. Expand the operator model from "screen and report" to "decision support system"

The tool does not only state that a setup exists. It answers:

- why it qualifies,
- what invalidates it,
- what the preferred entry and stop are,
- how much risk is implied,
- whether market regime supports new exposure,
- what to do if the setup gaps, triggers, or fails.

These six questions are the core of the operator-facing branch's value proposition.

### C. Operational product workstreams

The Phase 3e backlog in `docs/phase3e-todo.md` already captures concrete operational work items. The workstreams below are the strategic categories those items fall into; specific item triage belongs in code-side spec cycles.

#### Workstream B1 — Candidate ranking and focus management

- Stable focus ranking using the best validated rank factors;
- Explicit ranking rationales;
- Ranking stability indicators;
- Group or theme context where useful;
- "Why this is not top-ranked" diagnostics for near-misses.

#### Workstream B2 — Trigger and setup explanation

For each candidate, produce:

- trigger type;
- exact actionable level;
- stop basis;
- distance to trigger and stop;
- quality flags;
- short narrative explanation.

This is where validated pattern detectors (Pocket Pivot — fast-track per §IX, Buyable Gap-Up, Darvas breaks, robust VCP logic) surface.

#### Workstream B3 — Risk and trade-construction support

- Suggested shares and R-risk at multiple risk budgets;
- Portfolio-cap awareness;
- Earnings-proximity warnings;
- Gap-risk warnings;
- Exposure throttles based on regime;
- Better stop-adjustment guidance (current advisory infrastructure shipped in Phase 3d per CLAUDE.md).

#### Workstream B4 — Regime and exposure dashboarding

The tool presents regime as an operational state, not a hidden classifier:

- Risk-on / caution / risk-off stance;
- Evidence supporting that stance;
- Recommended exposure band;
- Count of distribution or warning signals;
- Plain-language explanation of what that means for new trades.

#### Workstream B5 — Journaling and decision audit

The production branch logs:

- what the system recommended;
- what the operator actually did;
- what changed afterward;
- where the operator deviated.

This is the data source for Workstream A5. **Build this early so A5 has data when it starts.**

#### Workstream B6 — Workflow and UX improvements

General workflow polish:

- watchlist lifecycle management;
- daily briefing clarity;
- chart embedding and chart annotation;
- open-position dashboards;
- inline trade actions;
- visibility into pipeline freshness.

#### Workstream B7 — Error and degradation UX

DESIGN already specifies STALE banners, force-clear recovery, and weather-unavailable warnings (DESIGN §5.3, §5.6). This is a coherent concern that deserves its own workstream rather than being absorbed into B6's generic "workflow improvements."

Scope: failure-mode messaging, recovery actions, degraded-state visibility. Most current items here come from the gotchas section of CLAUDE.md (HTMX 4xx swap config, weather-key drift between `data_asof` and `action_session`, OHLCV breaker reset).

#### Workstream B8 — Offboarding and override UX

When a method is deprecated or a position is being closed against the system's recommendation, the tool supports the override cleanly and logs the rationale. Distinct from B5: B5 is logging; B8 is the UX that enables the operator to override without defeating the logging.

### D. Operational method-adoption rules

A production method is accepted only if it is:

- easy to explain;
- easy to audit afterward;
- not excessively parameter-sensitive;
- compatible with the operator's timeframe and workflow;
- net-positive for decision quality, not merely historically interesting.

**Discretion discipline.** A production method that requires operator discretion must state the discretion explicitly in its method card and log every instance of the discretion being exercised. Discretion without logging is how systems silently decay — the operator's judgment drifts, nobody notices, and six months later the system's recommendations are being routinely overridden with no record of why.

Methods that remain too fuzzy or too data-hungry stay research-only.

---

## VI. Interaction model between the branches

The two branches are not isolated silos. They interact through a disciplined promotion pipeline.

### A. Research → Operational (promotion)

A **promotion package** consists of:

1. **Method card** (per §III.B), with all fields populated including operator_explainability and evidence_tier.
2. **Signal-computation function** with type signatures and test fixtures (pytest-compatible, consistent with the existing test discipline per CLAUDE.md).
3. **Evidence summary** with backtest results, sensitivity analysis (parameter perturbation ±25%), walk-forward results, and robustness across alternate universe definitions.
4. **Operator-explainability text** in three forms (single sentence, paragraph, FAQ).
5. **Shadow-mode activation config** — the parameters under which the method first enters production in shadow form.
6. **Parity test** demonstrating the computation function produces identical output against both research and production data models.

### B. Operational → Research (feedback)

Production usage generates questions for research:

- Recurring false positives;
- Ranking instability;
- Methods the operator ignores;
- Setup classes with weak realized expectancy;
- Performance by regime or market-cap segment;
- **Directional operator overrides** — see Workstream A5.

### C. Shadow mode

Before full promotion, a candidate method runs in shadow mode inside the operational branch:

- visible to logs and evaluation artifacts;
- **visible to the operator by default**, displayed clearly distinguished from primary recommendations (separate panel, different visual treatment, explicit "shadow" labeling);
- not allowed to drive primary recommendations.

**Rationale for default-visible.** This is the single most important design choice in the interaction model. Making shadow signals optional defeats the purpose — the operator cannot calibrate against hidden shadow signals, and unused infrastructure rots. An operator who routinely finds the shadow signal would have produced a better outcome is the mechanism by which shadow methods earn promotion. That mechanism cannot operate if the shadow is invisible.

### D. Demotion and challenge pipeline

Promotion is one direction; demotion is the other. In real systems, demotion is the more common event than promotion — markets change faster than research produces new methods. The pipeline must support both.

A production method may be demoted, deprecated, or retired based on evidence from operation or research:

- **Demotion to shadow.** When a challenging variant outperforms in shadow mode for a specified evaluation window (default: 6 months, ≥30 trade signals), the incumbent is demoted to shadow and the challenger promoted to primary. Both continue running.
- **Deprecation.** A production method is marked deprecated when a superior replacement has been promoted. Deprecated methods continue to produce recommendations flagged as deprecated for the transition window (default 30 days).
- **Retirement.** A deprecated method is retired after the transition window — removed from all operator-facing UI but preserved in the registry with `status=retired` for historical reproducibility.
- **Emergency demotion.** When a production method produces a specified severity of operational failure (e.g., a recommendation that would have caused ≥3R loss with proper sizing), the method can be emergency-demoted to shadow by direct action. The method card logs the emergency and triggers a required research-branch review.

### E. Source-of-truth corrections

When a primary source (book, paper, definitive publication) is acquired that corrects or refines a method currently implemented based on an approximation (e.g., the RS rank approximation in DESIGN §4.1 pending Minervini book verification), the correction is handled as a standard research-to-production promotion cycle, not as a hotfix:

1. The correction is filed as a new method-card version (major version bump per §III.B versioning rules, since output semantics change).
2. The corrected method enters research-branch validation against the same evidence criteria as any new method.
3. If validated, it enters shadow mode in production alongside the approximation.
4. If shadow-mode evidence supports the correction, the approximation is deprecated via the standard demotion pipeline (§VI.D).

**Why not a hotfix.** Source-of-truth corrections often turn out on investigation to be either (a) misremembered, (b) ambiguously specified in the source, or (c) context-dependent in a way the approximation accidentally captures. Treating them as hotfixes imports their uncertainty directly into production.

---

## VII. Recommended strategic architecture

### A. Core production stack

Keep and strengthen the current production principles (DESIGN §2.4 invariants):

- Modular Python package;
- Clear layer boundaries (`swing.web` is the only FastAPI/Jinja consumer; `swing.data.repos` is the only `sqlite3` consumer; criteria are pure functions of `CandidateContext`);
- SQLite operational store outside Drive-synced folders (`%USERPROFILE%/swing-data/swing.db`);
- Explicit audit rows for mutable trading actions (`trade_events`);
- Nightly pipeline plus dashboard;
- Deterministic recommendation artifacts (`daily_recommendations` immutable snapshots);
- Strong unit/golden testing (current baseline: 504 fast tests green per CLAUDE.md).

### B. Parallel research stack

Stand up a separate research environment with:

- A **single** research-grade data vendor initially (multi-vendor reconciliation is a distinct engineering project and is deferred until one vendor has been exhausted as a constraint on research conclusions);
- Parquet/DuckDB or equivalent research store;
- Vectorized research notebooks or scripts for ranking studies;
- Event-driven simulator for trade logic (per §IV.B.3 minimum spec);
- Experiment manifest system;
- Report generation for promotion decisions.

### C. Shared artifacts

Share only what is worth sharing:

- Formal signal specs (the registry);
- Universe definitions where compatible;
- Method cards;
- Promotion decisions;
- Selected validation summaries.

### D. Time-budget reality

This project is developed part-time by a single developer with significant competing commitments — day job, family of five, MBSE project (MBSEConvert), TTS160 firmware development, swing trading itself, and other technical interests. The bifurcated architecture is only valuable if both branches receive sustained attention; otherwise the research branch becomes a graveyard and the production branch evolves without the validation the bifurcation was meant to enforce.

**Acknowledged constraint.** Expected sustained developer attention is **4–8 hours per week averaged over a year**, split roughly **70/30 production/research** during Phases 0–2 and shifting to **50/50** once Phase 3 begins.

**Implication 1 — scope ambition matches time budget.** Methods that require more than a calendar month of evening work to validate should be questioned — they are likely either over-specified or better left to later phases.

**Implication 2 — registry discipline is leverage, not overhead.** The signal-definition registry and method-card discipline are the only mechanism by which intermittent work is cumulative rather than cyclically redone. When time is short, skipping the registry feels efficient and is corrosive.

**Implication 3 — burstiness is expected.** A month with zero research progress is not a failure signal; a quarter with zero progress is.

### E. Failure modes and countermeasures

Both prior documents (CRIT and PROP v1) treated bifurcation as a pure win. It is not. Known failure modes — each of which has occurred in organizations with far more resources than a solo developer:

| Failure mode | Leading indicator | Countermeasure |
|---|---|---|
| Research graveyard — promotions stop | No promotion package produced for >6 months | Quarterly self-review with explicit go/no-go on continuing research |
| Production evolves around the pipeline | Production-only methods entering the signal registry at bronze tier without research validation | Rule: any signal producing operator-facing recommendations must have a registry entry, even if `status=production-unvalidated` |
| Shared foundation bit-rot | Method cards with stale fields, missing versions, or referenced-but-nonexistent predecessors | Pre-commit hook validates registry structure; monthly manual audit |
| Parity tests skipped | Test suite runtime exceeds pipeline tolerance, tests marked skip | Budget parity-test runtime as a first-class constraint; simplify or shard tests rather than skip |
| Bifurcation discipline collapses under time pressure | Operator-facing changes made without touching the registry | Treat as a process violation even when the change is trivially correct; the discipline is the point |

---

## VIII. Concrete strategic roadmap

The roadmap reflects the actual state as of 2026-04-23: Phase 3d shipped, 504 tests green, Phase 3e backlog captured. The operational branch is meaningfully more mature than the research branch, which does not yet exist.

### Phase 0 — Governance and definitions (ongoing, steady-state)

Signal-definition registry, method-card template, and promotion criteria are authored and populated **incrementally as methods enter consideration**. No artificial deadline — this is ongoing work.

- **Initial pass** covers the candidates already identified in §IX: 20–40 hours spread over 4–6 weeks of evening work.
- **Steady-state maintenance:** ≈1–2 hours per week per active research candidate.
- **Discipline rule:** no method moves between lifecycle states without a registry update in the same commit.

The Phase 0 task list itself (small, evening-sized tasks with ≤4 hour bounds) is a downstream artifact for the code-side session, not part of this strategic document.

### Phase 1 — Research branch foundation (begins after current operational work stabilizes)

Minimum-viable research environment using existing free data sources (yfinance + manually maintained delistings list).

**First milestone:** reproduce one production signal (e.g., Minervini Trend Template per DESIGN §4.1) end-to-end in the research environment, producing identical bucket assignments. This earns the parity-test discipline and validates the promotion bridge before the first promotion is attempted.

**Estimated 40–80 hours of evening work.** Norgate or equivalent paid data deferred until §IV.B.1 criteria are met.

### Phase 2 — Operational strengthening (in progress)

**Already underway.** Phase 3d has shipped per CLAUDE.md. Active backlog in `docs/phase3e-todo.md`. This is not a future phase; it is acknowledged as current work and continues independently of Phases 0 and 1.

Specific Phase 3e priorities are tracked in the existing backlog and triaged in the existing copowers spec workflow — they are not enumerated here.

### Phase 3 — First promotion cycle (contingent on Phases 1 and 2 both meaningfully complete)

Defined as: **Phase 1 has reproduced a production signal and validated at least one research candidate end-to-end; Phase 2 has implemented the recommendation/action journaling (Workstream B5) that supports A5.**

Scope: **one or two candidates only.** Pocket Pivot is the obvious first candidate (see §IX and the cross-document commitment in REBUTTAL Finding 3.4). Shadow mode first, always.

### Phase 4 — Not committed

Portfolio overlays, short-side systems, and more ambitious multi-method stacks remain out of scope. Re-evaluate after Phase 3 delivers its first promoted method and produces operator-feedback data to inform direction.

### Phase 5 — Real-money transition (deferred; re-evaluate after Phase 3)

Transition to real money is itself a methodological milestone, not merely a configuration change. Preconditions for Phase 5 consideration:

- Phase 3 has delivered ≥3 promoted methods;
- Operator-behavior analytics (Workstream A5) shows stable recommendation-follow-through rates;
- Paper-trading win rate and expectancy track historical backtest expectations within a specified tolerance;
- Drawdown characteristics in paper match backtest drawdown characteristics.

Without these preconditions, paper-to-real transition is premature.

---

## IX. Recommended initial candidate set

To keep the program disciplined, the first research-to-production cycle focuses on a narrow set of high-value candidates, classified by readiness rather than priority alone.

### Fast-track candidates (minimal research before shadow deployment)

- **Pocket Pivot detector.** The detection rule is `vol[t] > max(vol[t-10:t] where close[i] < close[i-1])` — a single pandas expression. The only research question is confirmation-rule sensitivity (e.g., requiring `close > open` on signal day, distance-to-MA gates). Fast-track to shadow mode after a one-week validation study. **Committed cross-document fate** per REBUTTAL Finding 3.4.
- **Earnings-proximity blackout.** Implementation is trivial once an earnings calendar is integrated; the "research question" is parameter tuning (blackout window width), not method validation. Reclassify as production-candidate pending parameter study and earnings-calendar integration (see §V.B.1 caveats).

### Standard research candidates (full workstream required)

- Stable RS formulation (Workstream A1)
- Multi-horizon momentum ranking (Workstream A1) — coupled to FIP, see below
- Buyable Gap-Up detector (Workstream A2)
- ATR/ADR-informed sizing and stop frameworks (Workstream A3)
- Regime and exposure throttles (Workstream A4)

### Research-only (no near-term promotion expected)

- **FIP as live modifier** — coupled to ranking research. FIP is a modifier on momentum ranking, not a standalone method; it cannot be meaningfully separated from ranking decisions. Either retain both FIP and ranking together in a single research workstream, or defer both. Splitting them produces a near-term ranking system that cannot incorporate the smoothness filter that makes academic momentum work in the first place.
- AVWAP-based management logic
- GEM/Faber portfolio overlays
- Expanded short-selling frameworks
- State-machine management systems
- **VCP formalization variants beyond the conservative baseline already in DESIGN §4.2.** The conservative VCP rules currently in production (prior trend ≥25%, price within 5% of 20MA, tightness as daily range ≤ 2/3 ADR for ≥2 days, volume contraction, orderliness, risk feasibility) are acceptable and not demoted. The research-only designation applies to more ambitious VCP formalizations — Minervini-style multi-contraction sequences with formal contraction-width ratios, cup-with-handle geometric fits, and similar fuzzy pattern-recognition extensions.

---

## X. Final recommendation

Adopt the bifurcated model explicitly.

The project is now large and serious enough that it should stop pretending one architecture can satisfy both research rigor and operational simplicity equally well.

The correct strategic stance is:

- **one disciplined research branch** to discover and validate methods,
- **one disciplined operational branch** to help the trader act better every day,
- and **a formal promotion pathway** between them.

That structure preserves ambition without sacrificing coherence.

It also turns SRC into something genuinely valuable: not a confused basis for one tool, but the upstream research reservoir feeding a mature two-branch trading system.

---

## Appendix A — Downstream agent handoff

This section is for Claude Code or Codex sessions consuming this document.

**The strategic decisions captured in this document are settled.** Do not re-litigate them in the implementation session. The expected downstream outputs are:

1. **An initial signal-definition registry** (TOML format per §III.B) populated with method cards for the candidates in §IX. Begin with the fast-track candidates (Pocket Pivot, Earnings-proximity blackout) and the standard-research candidates.
2. **A Phase 0 task list** sized for 20–40 hours of evening work, with no single task exceeding 4 hours, derived from §VIII Phase 0.
3. **A lightweight catalog-maintenance protocol** (pre-commit hook, monthly audit checklist) addressing the §VII.E failure modes.

When implementing, prefer:

- Real repo paths over invented ones (consult `swing/`, `tests/`, `docs/` directly);
- Minimal additions over speculative scaffolding;
- TDD discipline per CLAUDE.md conventions (failing test → minimal implementation → passing test → commit);
- Conventional commits (`feat(...)`, `fix(...)`, `refactor(...)`, `test(...)`); no Claude co-author footer; no `--no-verify`.

When in doubt about the strategic intent of a section here, prefer the strict reading. The whole point of this document is that the strategy should not be re-derived in implementation sessions.

**Cross-references for downstream sessions:**

- Current repo state and conventions: `CLAUDE.md` (root)
- Architectural baseline: `docs/superpowers/specs/2026-04-17-swing-ground-up-refactor-design.md`
- Current operational backlog: `docs/phase3e-todo.md`
- Daily routine ground truth: `docs/cycle-checklist.md`
- Diagnostic context (do not re-implement, read for reasoning): `reference/Future Work/2026-04-22-formal-critique-extending-methodological-basis.md` and `reference/Future Work/2026-04-22-rebuttal-critique-and-implementation-proposal.md`
- Original research compendium (reclassified per CRIT as a research inventory, not a methodology): `reference/Future Work/Extending methodological basis.md`

---

## Appendix B — Findings traceability

For reference, the REBUTTAL findings incorporated into this revision:

| REBUTTAL Finding | Where addressed in this document |
|---|---|
| 2.1 (preserve PROP-I.A key sentence) | Executive summary blockquote |
| 2.2 (complexity tolerance row) | §I table |
| 2.3 (lifecycle states + shadow modifier) | §II.1 |
| 2.4 (shared kernel cost acknowledgment) | §II.2 |
| 2.5 (monitoring layer) | §II.3 |
| 2.6 (marginal value baseline) | §II.4 |
| 2.7 (preserve PROP-II.5) | §II.5 |
| 2.8 (canonical domain model expansion) | §III.A |
| 2.9 (signal registry full spec) | §III.B |
| 2.10 (production provenance acknowledgment) | §III.C |
| 2.11 (catalog ownership in solo context) | §III.B catalog ownership |
| 2.12 (preserve PROP-IV.A.5) | §IV.A item 5 |
| 2.13 (bootstrap-first data strategy) | §IV.B.1 |
| 2.14 (promotion bridge / parity test) | §IV.B.2 |
| 2.15 (event-driven simulator min spec) | §IV.B.3 |
| 2.16 (hypothesis falsifiability) | §IV.B.4 |
| 2.17 (workstream sequencing) | §IV.C |
| 2.18 (pre-registration) | §IV.B.4 |
| 2.19 (seventh promotion criterion: compute) | §IV.E item 7 |
| 2.20 (operational data caveats) | §V.B.1 |
| 2.21 (preserve PROP-V.B.2 six questions) | §V.B.2 |
| 2.22 (workstreams B7, B8) | §V.C.7, §V.C.8 |
| 2.23 (discretion discipline) | §V.D |
| 2.24 (promotion package contents) | §VI.A |
| 2.25 (directional override feedback) | §IV.C.A5, §VI.B |
| 2.26 (shadow mode visible by default) | §VI.C |
| 2.27 (single research vendor initially) | §VII.B |
| 2.28 (roadmap rewrite) | §VIII |
| 2.29 (candidate reclassification) | §IX |
| 2.30 (preserve PROP-X) | §X |
| 3.1 (operator psychology cross-boundary) | Executive summary methodological-sources paragraph; §IV.C.A5; §V.C.5; §V.C.8 |
| 3.2 (VCP scope clarification) | §IV.C.A2; §IX research-only |
| 3.3 (Norgate cost-earning path) | §IV.B.1 |
| 3.4 (Pocket Pivot fast-track committed) | §VIII Phase 3; §IX fast-track |
| 3.5 (production data vendor handling) | §V.B.1 |
| 3.6 (demotion pipeline) | §VI.D |
| 3.7 (time-budget reality) | §VII.D |
| 3.8 (failure modes and countermeasures) | §VII.E |
| 3.9 (source-of-truth correction protocol) | §VI.E |
| 3.10 (Disciplined Swing Trader layer) | Executive summary methodological-sources paragraph |
| 3.11 (paper-to-live transition) | §VIII Phase 5 |
| 3.13 (cross-references) | Appendix A cross-references |

REBUTTAL findings tagged for CRIT-only revision (1.1, 1.3–1.23) are not addressed here per the user's direction that CRIT remains as-is for future reference.
