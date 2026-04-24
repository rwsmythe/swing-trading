# Rebuttal: Critique of Extending Methodological Basis & Bifurcated Implementation Proposal

**Date:** 2026-04-22
**Author context:** Prepared as input to a future Claude Code / Codex agent session for strategy revision and actionable roadmap development.
**Scope:** Line-level analytical rebuttal of two strategic documents, followed by cross-document consistency and gap analysis.

## Source documents reviewed

- **CRIT** — `2026-04-22-formal-critique-extending-methodological-basis.md` (Google Drive file id `1hWMQAMJY1yUQx0J6bIKA3V_gwM-TzdMx`)
- **PROP** — `2026-04-22-bifurcated-strategic-implementation-proposal.md` (Google Drive file id `1ze8JISNLE3kkYl2OBH0BtqBw5Zj4vsRy`)
- **DESIGN** — `2026-04-17-swing-ground-up-refactor-design.md` (Google Drive file id `18CSl-zNb9MsuaytKelp7GDPOcf2t0yRj`) — referenced as the current production-tool ground truth
- **SRC** — `Extending methodological basis.md` — the original research memo that CRIT reviews; referenced but not re-read for this rebuttal (content is summarized indirectly through CRIT)

## Agent instructions

When consuming this document:

1. Section anchors use the form `CRIT-II-2` (critique, section II, subsection 2) and `PROP-IV-B-1` (proposal, section IV, subsection B, sub-item 1). These match the source documents' own numbering.
2. Findings are tagged `[KEEP]`, `[REVISE]`, `[EXPAND]`, `[RESOLVE]`, `[ADD]`, or `[REMOVE]` to indicate the recommended action.
3. Priority tags `[HIGH]`, `[MEDIUM]`, `[LOW]` reflect strategic load-bearing weight, not effort.
4. The "Proposed edit" blocks contain concrete text ready to splice into a revised version of the source document.
5. Part 3 contains cross-document findings that cannot be assigned to either document alone.

## Top-level assessment

- **CRIT** is sharp and mostly correct. Its central diagnosis — that the source memo is a research compendium, not a methodology — is the single most valuable contribution across both documents. Its weaknesses are four: occasional overreach, internal conflations mirroring those it accuses the source of, abstractness in its own remedies, and absence of direct quotation of the document being reviewed.
- **PROP** is stronger than CRIT overall — well-structured, internally consistent, operationally plausible. Its core thesis (bifurcate research and production) is correct. Its weaknesses are three: the "shared foundation" is under-specified, several proposed structural changes import complexity without acknowledging cost, and the roadmap ignores the solo-developer / part-time pacing reality.
- As a **pair**, the documents form a coherent argument (CRIT diagnoses, PROP resolves) but have five consistency issues and six material gaps that should be closed before either becomes the basis for implementation work.

---

# Part 1 — Rebuttal of CRIT

## CRIT — Executive summary

### Finding 1.1 [REVISE] [LOW]
**Line reviewed:** *"Its main failure is architectural discipline."*

The word *failure* is too strong. SRC was written in response to a request for additional references — it was never asked to be a methodology. Calling a scope mismatch a failure reframes SRC's scope and then faults it for not meeting the reframed scope.

**Proposed edit:**
> Its main limitation for this project is architectural discipline — it was asked to inventory references, and it does that well, but the closing synthesis blurs the line between inventory and governing logic.

### Finding 1.2 [KEEP] [HIGH]
**Line reviewed:** *"Bottom-line judgment: retain the memo, but reclassify it."*

This is CRIT's strongest sentence and the correct strategic call. Preserve verbatim.

## CRIT Section I — What the memo does well

### Finding 1.3 [EXPAND] [LOW]
CRIT-I.1 correctly identifies SRC's implementation-orientation but does not distinguish between generic codification bias and SRC's unusually specific practice of providing deterministic formulas for every core metric (e.g., `ADR%_20 = 100 × (mean(H/L, 20) − 1)`).

**Proposed insertion after CRIT-I.1:**
> Specifically, SRC provides closed-form formulas for ADR%, IBD-style RS rating, Mansfield RS, FIP, Clenow momentum score, and Barroso–Santa-Clara vol-scaling. This level of specificity is what allows the memo to be used at all by a downstream developer, and it distinguishes SRC from typical trading reading lists that hand-wave at "using Python libraries."

## CRIT Section II — The central problems

### Finding 1.4 [REVISE] [LOW]
**CRIT-II.1** — The critique treats the word *basis* in SRC's title as a structural claim. The title is *"Extending methodological basis"* — a verb phrase implying incremental addition to an existing basis, not a claim to constitute one. This is a reasonable reading but not the only reading.

**Proposed edit:**
> The title invites confusion — "extending methodological basis" reads in two ways, and the document's content exercises both readings without committing to one.

### Finding 1.5 [RESOLVE] [HIGH]
**CRIT-II.2 vs CRIT-II.8** — These two subsections give inconsistent treatment of operator psychology.
- CRIT-II.2 classifies it as a separate "operator governance layer" outside the alpha engine.
- CRIT-II.8 criticizes SRC for leaving operator workflow "conceptually acknowledged but not structurally integrated."

One cannot simultaneously require a layer to be integrated (II.8) and separate (II.2). Pick one.

**Proposed resolution** — Replace both with a single coherent treatment:
> Operator governance is a real component of the system, but SRC treats it as a topical appendix rather than as a structural component. Either elevate it to a first-class layer with explicit interfaces to the signal layers, or excise it from the methodology proper and handle it in a separate operator-facing specification. What it cannot be is a decorative afterthought that the memo gestures at without integrating.

### Finding 1.6 [REVISE] [MEDIUM]
**CRIT-II.3** — Evidence tiers are source-specific (peer-reviewed > practitioner > open-source > commentary). Evidence tiers should be method-specific: a reproducible backtest with open code is stronger than a peer-reviewed paper whose data is unavailable.

**Proposed edit to tier definitions:**
> - Tier 1: Peer-reviewed work with replicable methodology, OR practitioner rules demonstrated on point-in-time data with shared code.
> - Tier 2: Serious practitioner work with documented rules and published track records.
> - Tier 3: Open-source implementations whose correctness can be inspected, with evidence of adoption by practitioners.
> - Tier 4: Commentary, podcasts, community consensus, marketing content.

### Finding 1.7 [ADD] [HIGH]
**CRIT-II.4** — This is the strongest argument in CRIT and the foundation of PROP's bifurcation. The critique should explicitly name PROP as the resolution.

**Proposed insertion at end of CRIT-II.4:**
> This conflation is not merely a weakness of the memo; it is the tension that the bifurcated implementation strategy (companion document PROP) is designed to resolve. See PROP §I.

### Finding 1.8 [EXPAND] [MEDIUM]
**CRIT-II.5** — CRIT demands governance for parameter choice but is itself vague about that governance.

**Proposed insertion:**
> Concretely: any parameter tuned on historical data must have its sensitivity tested across ±25% of nominal value, and multi-variant studies (e.g., testing momentum at 3/6/9/12-month lookbacks) must report the number of variants tried alongside the winner's statistics so readers can apply Bonferroni-style correction mentally.

### Finding 1.9 [EXPAND] [MEDIUM]
**CRIT-II.6** — Correct that pattern-heavy methods are under-specified, but incomplete on *why*.

**Proposed insertion:**
> The root cause is that each of these pattern families (VCP, cup-with-handle, cycle-of-price-action) requires prior segmentation of a time series into regime states before the pattern can be identified, and segmentation is itself an open problem with no canonical solution. These are not implementation tasks; they are research projects in their own right.

### Finding 1.10 [KEEP] [HIGH]
**CRIT-II.7** — The list of possible system roles (stock picker / setup detector / portfolio allocator / exposure governor / operator assistant) is the clearest framing of the architectural ambiguity. Preserve verbatim.

### Finding 1.11 [KEEP] [HIGH]
**CRIT-II.9** — The sentence *"That sequencing is backwards"* is the correct critique of SRC's closing blueprint. Preserve verbatim.

### Finding 1.12 [REVISE] [MEDIUM]
**CRIT-II.10** — Correct that exclusion discipline is a pre-condition for the other critiques to be actionable. This point currently sits at the end of the section but should be earlier.

**Proposed action:** Promote CRIT-II.10 to CRIT-II.2 (or CRIT-II.1) — exclusion discipline is the meta-critique that structures all the specific ones.

## CRIT Section III — Mismatch with project context

### Finding 1.13 [ADD] [LOW]
CRIT-III lists the current project characteristics (Finviz, yfinance, SQLite, nightly pipeline) but does not cite DESIGN explicitly. A reader cannot verify the claim without re-reading DESIGN.

**Proposed insertion at start of CRIT-III:**
> The characteristics described here are taken from the current refactor design document (DESIGN §2.2 and §2.3). This section assumes that document as the ground truth for what currently exists.

### Finding 1.14 [KEEP] [HIGH]
**Line reviewed:** *"The memo is not wrong because it is ambitious. It is wrong only if the project treats all of that ambition as belonging to one system boundary."*

Best single sentence in CRIT-III. Preserve verbatim.

## CRIT Section IV — Recommendations

### Finding 1.15 [REVISE] [LOW]
**CRIT-IV.1** — Three proposed titles offered (*Strategic Research Backlog / Candidate Methodologies and Evidence Map / Research Inventory for Method Expansion*). Offering three reads as indecision.

**Proposed action:** Commit to one. Recommended: **Research Inventory for Method Expansion** — most honest and most specific label.

### Finding 1.16 [ADD] [MEDIUM]
**CRIT-IV.2** — Part B (method inventory) should include a `predecessor / supersedes` field so the inventory can track method evolution. Pocket Pivot supersedes naive volume-breakout; Frog-in-Pan refines raw momentum; Barroso–Santa-Clara scaling supersedes naive momentum exposure. Without this field the inventory is flat and loses dependency structure.

### Finding 1.17 [ADD] [MEDIUM]
**CRIT-IV.3** — Method card template is missing a critical field: `operator_explainability`. A method can be rigorous and historically robust yet operationally useless if the trader cannot be told why today's recommendation exists. PROP Branch B depends on this property; CRIT should require it.

**Proposed addition to template:**
> - **Operator explainability**: single-sentence rationale (what the trader sees on the card), one-paragraph explanation (what the trader sees when expanding), and an FAQ entry for the most common objection.

### Finding 1.18 [ADD] [MEDIUM]
**CRIT-IV.4** — Exclusion rules are missing vendor-independence.

**Proposed additional exclusion rule:**
> Methods whose definitions are vendor-dependent (e.g., any rule stated in terms of an IBD proprietary rating) must have a non-proprietary replacement specified, or the rule is rejected. DESIGN §4.1 handles this for RS Rating via the stable reference universe; the methodology as a whole needs this principle explicit.

### Finding 1.19 [ADD] [MEDIUM]
**CRIT-IV.5** — Backtesting standards are missing two controls.

**Proposed additions:**
> - **Data-vendor equivalence testing**: the same rule must produce equivalent bucket assignments on two independent data vendors within a specified tolerance; otherwise the rule is data-vendor-fitted rather than market-fitted.
> - **Look-ahead bias audit**: every rule must have its data dependencies inspected for forward-leakage (e.g., RS computed against end-of-period universe membership when universe was different at the time; fundamental ratios using data not yet released as of the asof date).

## CRIT Section V — Retain / defer / downgrade

### Finding 1.20 [REVISE] [HIGH]
**CRIT-V.1 retain list** — The entry *"stable relative-strength and multi-horizon momentum ranking"* combines two distinct research questions.

**Proposed split:**
> - Stable relative-strength formulation (question: which RS variant is most stable across universe definitions and time?)
> - Multi-horizon momentum ranking (question: does a 3/6/9/12-month ensemble outperform single-horizon 12-1 momentum?)

### Finding 1.21 [RESOLVE] [HIGH]
**CRIT-V.1 vs CRIT-V.2** — FIP is deferred to research-only but multi-horizon ranking is retained for near-term. FIP is a modifier on momentum ranking, not a standalone method — it cannot be meaningfully separated from ranking decisions.

**Proposed resolution:**
> Either retain both FIP and ranking together in a single research workstream, or defer both. Splitting them produces a near-term ranking system that cannot incorporate the smoothness filter that makes academic momentum work in the first place.

### Finding 1.22 [REVISE] [LOW]
**CRIT-V.3 downgrade list** — *"Open-source repos without evidence of robustness"* is too broad. Distinguish adoption-weighted repos (e.g., `skyte/relative-strength`, Stockbee-style screeners) from unreviewed code.

**Proposed edit:**
> Open-source repositories without evidence of adoption by serious practitioners. Repositories with documented adoption (e.g., `skyte/relative-strength` for IBD-style RS computation, established Stockbee screeners) are Tier 3 and may inform implementation.

## CRIT Section VI — Final judgment

### Finding 1.23 [REVISE] [LOW]
**CRIT-VI closing sentence** — *"It is also still undisciplined in the precise way that sophisticated research documents often are: it knows many relevant things before it has decided what kind of system it is actually building."*

Tone wobbles relative to the sharpness of the rest of CRIT. Either commit to sharpness or soften throughout.

**Proposed sharpened edit:**
> It knows many relevant things without having decided which ones matter, which is the characteristic weakness of a research document mistaken for a decision document.

---

# Part 2 — Rebuttal of PROP

## PROP — Executive summary

### Finding 2.1 [KEEP] [HIGH]
**Line reviewed:** *"Do not make the production tool carry the full burden of research correctness, and do not make the research environment inherit the speed and simplicity constraints of the production tool."*

Strongest single sentence in either document. Preserve verbatim.

## PROP Section I — Strategic rationale

### Finding 2.2 [REVISE] [LOW]
**PROP-I table row: Tolerance for complexity**

Current: Research=High, Operational=Moderate.

The production tool already has substantial complexity (pipeline lease tokens, two-date semantics, staged artifact promotion, force-clear recovery). The distinction is not complexity level but complexity purpose.

**Proposed edit:**
> | Tolerance for discretionary complexity | High, bounded by experimenter sanity | Moderate, bounded by operator interpretability |

## PROP Section II — Governing design principles

### Finding 2.3 [EXPAND] [LOW]
**PROP-II.1 promotion states** — States listed: `backlog → specified → prototype → validated → shadow mode → production → rejected/retired`.

Two clarifications needed:
- Add `deprecated` state distinct from `retired`. Deprecated methods are being phased out but still in production during transition; retired methods are off. Operator UX differs.
- Clarify that `shadow mode` is not a lifecycle state but a production modifier — a method can be simultaneously in production for primary recommendations and shadow for a new variant.

**Proposed edit:**
> States: `backlog → specified → prototype → validated → production → deprecated → retired`. Shadow mode is a modifier applied within production: a production-state method may run a shadow variant alongside its primary rule set, visible in logs and optionally in operator UI, without the shadow variant driving decisions. Rejected methods exit the pipeline at any state prior to production.

### Finding 2.4 [EXPAND] [MEDIUM]
**PROP-II.2 shared kernel** — *"They do not need to share the same storage engine, vendor stack, test harness, or runtime constraints."* True, but the separation has a cost not acknowledged.

**Proposed addition:**
> The cost of this separation is data-conversion friction at the promotion boundary. A signal proven in the research environment (Parquet/DuckDB panel data) must be re-implemented against the production environment (SQLite per-ticker rows) before promotion. Budget time for this conversion explicitly. The signal-definition registry (§III.B) mitigates but does not eliminate this cost.

### Finding 2.5 [ADD] [MEDIUM]
**PROP-II.3 layer ownership** — Missing a layer.

**Proposed addition to layer list:**
> - Monitoring / observability (detection of drift, stale data, method degradation after promotion)

### Finding 2.6 [EXPAND] [MEDIUM]
**PROP-II.4 marginal value** — Vague in a way that invites rationalization.

**Proposed edit:**
> A method should be adopted only if it improves one or more target metrics without introducing disproportionate fragility, operator confusion, or overlap with an existing rule. Marginal value must be stated against a specific baseline — a method is not "better" in isolation; it is better than the specific rule it replaces or the specific gap it fills.

### Finding 2.7 [KEEP] [MEDIUM]
**PROP-II.5** — *"Data acquisition, storage, experiment tracking, and vendor choice are not implementation trivia. They are part of the method."*

Correct and load-bearing. Preserve verbatim. Note that CRIT does not make this principle explicit and would benefit from it.

## PROP Section III — Shared foundation

### Finding 2.8 [EXPAND] [HIGH]
**PROP-III.A canonical domain model** — Bullet list is incomplete in two ways.

**Proposed additions:**
> - **Timezone and session semantics are load-bearing.** DESIGN §5.5 already establishes the two-date model (`data_asof_date` / `action_session_date`) using the NYSE calendar. The research branch must inherit this discipline rather than re-derive it — backtests that collapse the two dates into one produce subtle look-ahead bugs.
> - **Corporate-action handling decomposes into five distinct problems**: splits, dividends, mergers, ticker changes, and delistings. Each has different implications for signal computation. Research branch requires point-in-time handling of all five; production branch can rely on yfinance adjusted prices for the first two but must handle the others explicitly. Shared domain model must express these differences.

### Finding 2.9 [EXPAND] [HIGH]
**PROP-III.B signal-definition registry** — Under-specified. This is the most important piece of shared infrastructure in the entire proposal and is currently two sentences.

**Proposed replacement of PROP-III.B:**
> The signal registry is the mechanism by which methods proven in research become implementable in production without re-derivation. It is the single highest-leverage shared asset in the bifurcated architecture.
>
> **Format.** TOML or YAML for human-editability, with a Python dataclass mirror for programmatic access (generated from the spec file). JSON is rejected — not hand-editable.
>
> **Required fields per signal:**
> - `name`, `version` (semver: MAJOR.MINOR.PATCH)
> - `layer` (universe / ranking / trigger / sizing / stop / exit / regime / portfolio / governance / monitoring)
> - `status` (backlog / specified / prototype / validated / production / deprecated / retired)
> - `formal_definition` — formula or deterministic logic, with inline citations to source (book page, paper DOI, URL)
> - `parameters` — name, type, default, valid range, tuning constraints
> - `required_data_fields` — OHLCV, fundamentals, corporate actions, etc., with timing semantics
> - `output_shape` — scalar / series / ranked list / boolean / tuple
> - `operator_explainability` — rationale sentence, explanation paragraph, FAQ
> - `predecessor` / `supersedes` — references to the registry entries this method evolved from
> - `known_caveats` — edge cases, regime dependencies, failure modes
> - `evidence_tier` (1–4 per CRIT-II.3 as revised)
>
> **Versioning rules.**
> - Patch (0.0.x): documentation or comment changes only, identical output.
> - Minor (0.x.0): parameter default changes, additional optional fields, backward-compatible. Production branches may auto-upgrade to minor versions.
> - Major (x.0.0): output semantics change, parameter removal, formula correction. Never auto-upgraded; requires explicit promotion cycle.
>
> **Deprecation protocol.** A deprecated signal must specify its replacement (by registry key) and a transition window (default 30 days). During transition, both signals run in production with the old one marked as deprecated in operator UI.

### Finding 2.10 [EXPAND] [LOW]
**PROP-III.C configuration and provenance** — The production branch has already started this work (DESIGN `config_revisions`, `pipeline_runs.rs_universe_version`, `trade_events` audit log). The proposal should acknowledge and leverage this.

**Proposed addition:**
> The production branch (DESIGN §3 and §5.1) has already implemented config revision tracking, pipeline run auditing, universe versioning, and immutable trade event logs. The research branch should inherit these patterns and the shared provenance schema should formalize them rather than invent new conventions.

### Finding 2.11 [ADD] [MEDIUM]
**PROP-III.D method catalog** — Correct but ownership-free in a solo-developer context.

**Proposed addition:**
> Catalog ownership: in a solo-developer context the catalog owner is the developer, but the *discipline* of keeping it current is the operational constraint. Rule: no method moves between states without a catalog update in the same commit. Enforced by a pre-commit hook that validates catalog-state transitions against the git diff.

## PROP Section IV — Research and Verification Branch

### Finding 2.12 [KEEP] [HIGH]
**PROP-IV.A Objective 5** — *"Reduce discretionary enthusiasm by forcing explicit definitions and robustness standards."*

The most honest objective in either document. Preserve verbatim.

### Finding 2.13 [REVISE] [HIGH]
**PROP-IV.B.1 data stack upgrade** — Endorses Norgate at $630/yr without acknowledging cost or proposing a lower-cost starting point. This is the most expensive single recommendation in PROP and should be earned, not assumed.

**Proposed replacement:**
> **Bootstrap approach.** The research branch should begin with free data sources (yfinance plus a manually maintained delisting list derived from SEC filings and exchange notices) to validate the branch's architecture before committing to paid infrastructure. Norgate ($630/yr as of 2026) or equivalent should be added only when a specific research question demonstrates that survivorship bias is materially affecting conclusions.
>
> **Criteria for paid-vendor adoption:**
> - A specific study's results change by more than a documented threshold (e.g., ≥15% expectancy difference) between bias-free and biased data, AND
> - The study's conclusions will inform a production promotion, AND
> - No free alternative has been identified in reasonable search
>
> This sequencing preserves the data-quality principle (CRIT-I.2) while avoiding premature infrastructure commitment. It also gives the project real experience with its own bias exposure before paying to fix it.

### Finding 2.14 [ADD] [MEDIUM]
**PROP-IV.B.2 research storage** — Missing the promotion-bridge specification.

**Proposed addition:**
> **Promotion bridge.** A promoted signal's computation function must be specified such that it runs against both the research data model (panel Parquet with multi-ticker time-indexed data) and the production data model (per-ticker SQLite rows queried on demand) and produces identical output for identical inputs. This is verified by a parity test that is part of every promotion package.

### Finding 2.15 [EXPAND] [MEDIUM]
**PROP-IV.B.3 backtesting framework** — Event-driven simulation is under-specified. Event-driven single-name backtests are a common source of bugs that look good on paper and fail in production.

**Proposed minimum specification for the event-driven simulator:**
> 1. Realistic slippage modeled as a function of ADR (e.g., 5–10% of ADR for market-order entries at breakout)
> 2. Gap-through of stops with configurable behavior (execute at gap-open price, not at stop price)
> 3. Earnings-date blackout with configurable lookback (default: no new entries within 5 trading days of announced earnings)
> 4. Fractional-share vs whole-share sizing modes (production uses whole shares; research should test both)
> 5. Degradation protocol when intraday data is unavailable: fall back to OHLC-only simulation and flag the trade in the output

### Finding 2.16 [EXPAND] [MEDIUM]
**PROP-IV.B.4 hypothesis management** — Generic. Missing the falsifiability requirement.

**Proposed addition:**
> Every hypothesis must specify its null — the world-state in which the method doesn't work — so the test has a falsifiable outcome. "I think this improves expectancy, let me backtest it" is not a hypothesis; "this method improves expectancy by ≥0.1R in bullish regimes and ≤neutral in other regimes, with p-value ≤0.1 on a 10-year sample" is a hypothesis.

### Finding 2.17 [ADD] [HIGH]
**PROP-IV.C workstreams** — No ordering specified. Ordering matters because workstream A5 (operator behavior) cannot start without production history, and workstreams depend on each other.

**Proposed addition — workstream sequencing:**
> **Recommended ordering:**
> - A1 (universe and ranking) first — blocking for A2 and A4
> - A3 (sizing and stops) in parallel with A1 — orthogonal dependencies
> - A2 (triggers and patterns) after A1 — depends on ranked universe
> - A4 (regime and portfolio overlays) after A2 — depends on candidate pools
> - A5 (operator behavior analytics) last — requires ≥6 months of production history with the journaling of recommendation-vs-action implemented (DESIGN §6.1)
>
> **Why A5 is last but critical.** A5 is the only workstream that cannot be done in isolation from production. It is also the mechanism by which this project gets strictly better over time — every other workstream can be done with historical data alone; A5 requires the operator-system feedback loop. Prioritize building the production-side logging (PROP-V Workstream B5) immediately so A5 has data when it starts.

### Finding 2.18 [ADD] [MEDIUM]
**PROP-IV.D methodology standards** — Missing pre-registration.

**Proposed addition:**
> **Pre-registration.** Before running a study, commit to the hypothesis, the test, and the decision rule in the method card. This is the cheapest anti-overfitting control available and it has zero runtime cost. Enforce via a rule: the method card's `hypothesis`, `test_design`, and `decision_rule` fields must be populated and committed before the first backtest run.

### Finding 2.19 [ADD] [MEDIUM]
**PROP-IV.E promotion criteria** — Six criteria listed; missing one.

**Proposed seventh criterion:**
> 7. **Computationally compatible** with the nightly pipeline runtime budget (current: pipeline completes in ≤10 minutes for ≤500 candidates per DESIGN §5), or a dedicated compute path with a separate latency budget must be specified. A signal that takes 20 minutes to compute per stock is research-only regardless of its expectancy.

## PROP Section V — Operational Trader-Facing Branch

### Finding 2.20 [EXPAND] [MEDIUM]
**PROP-V.B.1 data layer** — Two operational concerns understated.

**Proposed additions:**
> - **Earnings calendar integration is harder than the bullet suggests.** Free sources (yfinance, Yahoo calendar) are often wrong or late on announcement timing (before/after market). Earnings Whispers and Zacks are paid. Finviz shows expected dates but not announcement timing. For EOD swing trading, announcement timing matters because a position held through earnings has materially different risk than one entered after. Budget: expect to integrate ≥2 sources and reconcile discrepancies.
> - **Intraday bars are a different class of problem from EOD improvements.** yfinance provides limited intraday history (≤60 days); serious intraday backtesting or execution triggers require paid sources. For the current EOD swing workflow, intraday bars are not required; flag as deferred unless a specific trigger rule needs them.

### Finding 2.21 [KEEP] [HIGH]
**PROP-V.B.2 six decision-support questions** — (why qualifies, what invalidates, preferred entry/stop, risk implied, regime support, gap/trigger/fail responses).

Preserve verbatim. This is the core of the operator-facing branch's value proposition.

### Finding 2.22 [ADD] [MEDIUM]
**PROP-V.C workstreams** — Two missing.

**Proposed additions:**
> **Workstream B7 — Error and degradation UX.** DESIGN already specifies STALE banners, force-clear recovery, and weather-unavailable warnings (§5.3, §5.6). This is a coherent concern that deserves its own workstream rather than being absorbed into B6's generic "workflow improvements." Scope: failure-mode messaging, recovery actions, degraded-state visibility.
>
> **Workstream B8 — Offboarding and override UX.** When a method is deprecated or a position is being closed against the system's recommendation, the tool should support the override cleanly and log the rationale. Currently implicit in B5 (journaling) but distinct: B5 is logging; B8 is the UX that enables the operator to override without defeating the logging.

### Finding 2.23 [ADD] [MEDIUM]
**PROP-V.D adoption rules** — Missing discretion discipline.

**Proposed addition:**
> A production method that requires operator discretion must state the discretion explicitly in its method card and log every instance of the discretion being exercised. Discretion without logging is how systems silently decay — the operator's judgment drifts, nobody notices, and six months later the system's recommendations are being routinely overridden with no record of why.

## PROP Section VI — Interaction model

### Finding 2.24 [EXPAND] [MEDIUM]
**PROP-VI.A Research → Operational** — "Promotion packages" mentioned but contents not specified.

**Proposed minimum promotion package specification:**
> A promotion package consists of:
> 1. **Method card** (per PROP-III.B as expanded by Finding 2.9), with all fields populated including operator explainability and evidence tier
> 2. **Signal-computation function** with type signatures and test fixtures (pytest-compatible)
> 3. **Evidence summary** with backtest results, sensitivity analysis (parameter perturbation ±25%), walk-forward results, and robustness across alternate universe definitions
> 4. **Operator-explainability text** in three forms (single sentence, paragraph, FAQ)
> 5. **Shadow-mode activation config** — the parameters under which the method first enters production in shadow form
> 6. **Parity test** demonstrating the computation function produces identical output against both research and production data models

### Finding 2.25 [ADD] [MEDIUM]
**PROP-VI.B Operational → Research feedback** — Five questions listed; missing one critical category.

**Proposed sixth category:**
> - **Directional operator overrides.** When the operator consistently moves stops in a particular direction relative to the method's recommendation (e.g., always tighter, always wider), this is a signal about either the method's calibration or the operator's risk preference. Both require research-branch investigation. Undirected overrides (noise) are less interesting; directional overrides carry information.

### Finding 2.26 [RESOLVE] [HIGH]
**PROP-VI.C shadow mode visibility** — Current text: *"optionally visible to the operator as secondary information."*

This is the single most important design choice in the entire document. Making it optional defeats the purpose — the operator cannot calibrate against hidden shadow signals, and unused infrastructure rots.

**Proposed edit:**
> Shadow signals must be visible to the operator by default, displayed clearly distinguished from primary recommendations (e.g., separate panel, different visual treatment, explicit "shadow" labeling). They must not drive primary recommendations. An operator who routinely finds the shadow signal would have produced a better outcome is the mechanism by which shadow methods earn promotion — this cannot happen if the shadow is invisible.

## PROP Section VII — Recommended strategic architecture

### Finding 2.27 [REVISE] [LOW]
**PROP-VII.B** — *"research-grade data vendor(s)"* (plural). Multiple vendors = integration surface area.

**Proposed edit:**
> A single research-grade data vendor initially. Multi-vendor reconciliation is a distinct engineering project and should be deferred until one vendor has been exhausted as a constraint on research conclusions.

## PROP Section VIII — Roadmap

### Finding 2.28 [REVISE] [HIGH]
**PROP-VIII entire section** — Four phases listed with no time estimates, no dependencies, and no acknowledgment that the developer is solo, part-time, and has a day job, a family of five, an MBSE project, firmware work, and other competing technical commitments.

The current Phase 2 (operational strengthening) is already in progress via DESIGN and should not be listed as a future phase. The current Phase 0 (governance and definitions) is listed as if it's a week of work; realistic estimate is 20–40 hours for the initial pass and then ongoing steady-state maintenance.

**Proposed full replacement of PROP-VIII:**
> **Phase 0 — Governance and definitions (ongoing, steady-state).**
> Signal-definition registry, method card template, and promotion criteria are authored and populated incrementally as methods enter consideration. No artificial deadline — this is ongoing work. Initial pass covers the candidates already identified (PROP §IX): 20–40 hours spread over 4–6 weeks of evening work. Steady-state maintenance: ≈1–2 hours per week per active research candidate.
>
> **Phase 1 — Research branch foundation (begins after current refactor stabilizes).**
> Minimum-viable research environment using existing free data sources (yfinance + manual delistings list). First milestone: reproduce one production signal (e.g., Minervini Trend Template, DESIGN §4.1) end-to-end in the research environment, producing identical bucket assignments. Estimated 40–80 hours of evening work. Norgate or equivalent paid data deferred until Finding 2.13 criteria are met.
>
> **Phase 2 — Operational strengthening (in progress).**
> Already underway via DESIGN. Focus on decision explanations, risk presentation, chart embedding, and the expanded operator workflows documented in DESIGN §6. Not a future phase; acknowledged as current work.
>
> **Phase 3 — First promotion cycle (contingent on Phases 1 and 2 both meaningfully complete).**
> Defined as: Phase 1 has reproduced a production signal and validated at least one research candidate end-to-end; Phase 2 has implemented the recommendation/action journaling (B5) that supports A5. Scope: one or two candidates only. Pocket Pivot is the obvious first candidate (see Finding 3.3 and 4.7). Shadow mode first, always.
>
> **Phase 4 — Not committed.**
> Portfolio overlays, short-side systems, and more ambitious multi-method stacks remain out of scope. Re-evaluate after Phase 3 delivers its first promoted method and produces operator-feedback data to inform direction.

## PROP Section IX — Initial candidate set

### Finding 2.29 [REVISE] [HIGH]
**PROP-IX highest-priority research list** — Misclassifies two candidates as research-requiring when they are near production-ready.

**Proposed reclassification:**
> **Fast-track candidates (minimal research required before shadow deployment):**
> - **Pocket Pivot detector** — detection rule is `vol[t] > max(vol[t-10:t] where close[i] < close[i-1])`, a single pandas expression. Only research question is confirmation-rule sensitivity (e.g., requiring close > open on signal day). Fast-track to shadow mode after a one-week validation study.
> - **Earnings-proximity blackout** — implementation is trivial once an earnings calendar is integrated; the "research question" is parameter tuning (blackout window width), not method validation. Reclassify as production-candidate pending parameter study.
>
> **Standard research candidates (full workstream required):**
> - Stable RS formulation (workstream A1)
> - Multi-horizon momentum ranking (workstream A1)
> - Buyable Gap-Up detector (workstream A2)
> - ATR/ADR-informed sizing and stop frameworks (workstream A3)
> - Regime and exposure throttles (workstream A4)
>
> **Research-only (no near-term promotion expected):**
> - FIP as live modifier (coupled to ranking research; see Finding 1.21)
> - AVWAP-based management logic
> - GEM/Faber portfolio overlays
> - Expanded short-selling frameworks
> - State-machine management systems
> - VCP formalization variants beyond the conservative baseline already in DESIGN §4.2

## PROP Section X — Final recommendation

### Finding 2.30 [KEEP] [HIGH]
Three-bullet closing summary is the clearest statement of strategy in either document. Preserve verbatim.

---

# Part 3 — Cross-document findings

Findings in this part cannot be assigned to CRIT or PROP alone because they concern consistency between the documents, gaps that neither addresses, or decisions that require coordinated revision across both.

## 3.1 Consistency issues

### Finding 3.1 [RESOLVE] [HIGH] — Operator psychology treatment
CRIT-II.2 places operator psychology in an "operator governance layer" separate from the alpha engine. CRIT-II.8 criticizes SRC for not integrating operator workflow structurally. PROP treats operator behavior as a research workstream (A5) *and* as product features (B5 journaling) — i.e., as a signal flowing between branches, not as a layer.

PROP's treatment is the more sophisticated one and should govern.

**Coordinated edit required:**
- CRIT-II.2 and CRIT-II.8: Replace with a single treatment that matches PROP's signal-flow model. Proposed text: *"Operator governance is not a layer inside the alpha engine; it is a signal that crosses the boundary between operator and system, flowing in both directions. The memo treats it as an appendix rather than as a flow; it needs to become structural on both sides of the boundary — research-side analytics (PROP §IV Workstream A5) and production-side UX and logging (PROP §V Workstreams B5 and B8)."*
- Finding 1.5 (this rebuttal) supersedes and integrates Findings 1.5 and the partial treatment in 2.17.

### Finding 3.2 [RESOLVE] [HIGH] — VCP standards inconsistency
CRIT-II.6 says VCP detection is under-specified and research-only. PROP-IX lists *"VCP formalization variants beyond a conservative baseline"* as research-only, which is consistent with CRIT. **But DESIGN §4.2 already has VCP criteria running in production.** The three documents together leave the reader unable to determine whether the current production VCP rules are adequate, research-only, or being demoted.

**Coordinated edit required:**
Add an explicit statement in both CRIT (as an erratum or clarifying note) and PROP §IX:
> The conservative VCP rules currently in production (DESIGN §4.2: prior trend ≥25%, price within 5% of 20MA, tightness as daily range ≤ 2/3 ADR for ≥2 days, volume contraction, orderliness, risk feasibility) are acceptable and should not be demoted. The research-only designation applies to more ambitious VCP formalizations — Minervini-style multi-contraction sequences with formal contraction-width ratios, cup-with-handle geometric fits, and similar fuzzy pattern-recognition extensions.

### Finding 3.3 [RESOLVE] [HIGH] — Norgate cost unacknowledged
CRIT-I.2 and CRIT-V retain list treat survivorship-bias-free data as first-order, implying Norgate. PROP-IV.B.1 endorses this. Neither document acknowledges the $630/yr cost for a personal tool or proposes a cost-earning path.

**Coordinated edit required:**
- CRIT-V retain list: Add parenthetical *"(subject to cost-earning path, see PROP §IV.B.1 as revised per rebuttal Finding 2.13)"*.
- PROP-IV.B.1: Apply Finding 2.13 in full.

### Finding 3.4 [RESOLVE] [HIGH] — Pocket Pivot has no committed fate
Pocket Pivot appears in SRC (with codeable formula), CRIT-V retain list, PROP-IX highest-priority research, and DESIGN implicitly (as a trigger-family example). In none is its fate committed: is it a production recommendation today, or a research candidate for later?

**Coordinated edit required:**
Commit across all three documents (and the forthcoming roadmap) that Pocket Pivot is a **fast-track candidate** per Finding 2.29, entering shadow mode in Phase 3 after a one-week validation study. Add corresponding method card to the signal registry (per PROP-III.B as revised by Finding 2.9) immediately upon beginning Phase 0.

### Finding 3.5 [RESOLVE] [MEDIUM] — Data-vendor handling asymmetry
PROP discusses research data vendors (IV.B.1) at length but says almost nothing about production data vendors. DESIGN shows the production tool uses yfinance. Neither CRIT nor PROP says whether yfinance is adequate for production decisions.

**Coordinated edit required:**
Add to PROP-V.B.1:
> **Production data vendor assessment.** The production tool currently uses yfinance (DESIGN §2.2). For EOD swing trading with 10–20% equity position sizing and explicit LOD stops, yfinance EOD data is adequate: its OHLCV accuracy on liquid US equities is high, its adjusted-price handling is acceptable for the signal types currently deployed, and its free-tier rate limits accommodate the current nightly pipeline's ≤500-ticker load. Production vendor upgrade is deferred unless a specific reliability incident or a new signal type requires it. This is a separate decision from the research-branch vendor question.

## 3.2 Gaps neither document addresses

### Finding 3.6 [ADD] [HIGH] — No demotion pipeline
Both documents describe the promotion pipeline (research → production). Neither describes the demotion pipeline (production method is challenged by shadow-mode variant or changed market regime, and must be demoted, deprecated, or retired). In real systems, demotion is the more common event than promotion — markets change faster than research produces new methods.

**Proposed addition to PROP — new section VI.D:**
> **PROP-VI.D Demotion and challenge pipeline.**
>
> A production method may be demoted, deprecated, or retired based on evidence from operation or research:
>
> - **Demotion to shadow:** when a challenging variant outperforms in shadow mode for a specified evaluation window (default: 6 months, ≥30 trade signals), the incumbent is demoted to shadow and the challenger promoted to primary. Both continue running.
> - **Deprecation:** a production method is marked deprecated when a superior replacement has been promoted. Deprecated methods continue to produce recommendations flagged as deprecated for the transition window (default 30 days).
> - **Retirement:** a deprecated method is retired after the transition window, removed from all operator-facing UI but preserved in the registry with status=retired for historical reproducibility.
> - **Emergency demotion:** when a production method produces a specified severity of operational failure (e.g., a recommendation that would have caused ≥3R loss with proper sizing), the method can be emergency-demoted to shadow by direct action. The method card logs the emergency and triggers a required research-branch review.

### Finding 3.7 [ADD] [HIGH] — No research time budget
Research time is unbounded in both documents. The developer has a day job, a family of five, an MBSE project (MBSEConvert), firmware development on TTS160, swing trading itself, and competing technical interests. Without an acknowledged time budget, the bifurcation risks becoming an excuse to perpetually defer hard methodological decisions by relegating them to a research branch that never gets worked on.

**Proposed addition to PROP — new section VII.D (or a top-level constraint section):**
> **PROP-VII.D Time-budget reality.**
>
> This project is developed part-time by a single developer with significant competing commitments. The bifurcated architecture is only valuable if both branches receive sustained attention; otherwise the research branch becomes a graveyard and the production branch evolves without the validation the bifurcation was meant to enforce.
>
> **Acknowledged constraint:** expected sustained developer attention is 4–8 hours per week averaged over a year, split roughly 70/30 production/research during Phases 0–2 and shifting to 50/50 once Phase 3 begins.
>
> **Implication 1:** scope ambition must match time budget. Methods that require more than a calendar month of evening work to validate should be questioned — they are likely either over-specified or better left to later phases.
>
> **Implication 2:** the signal-definition registry and method-card discipline are not overhead; they are the only mechanism by which intermittent work is cumulative rather than cyclically redone.
>
> **Implication 3:** burstiness is expected. A month with zero research progress is not a failure signal; a quarter with zero progress is.

### Finding 3.8 [ADD] [HIGH] — Failure modes of bifurcation itself
Both documents treat bifurcation as a pure win. It isn't. Known failure modes:

- Research branch becomes an unused graveyard (promotion never happens, research is pure cost)
- Production branch evolves faster than research can validate (operator needs drive production changes that bypass the promotion pipeline)
- Shared foundation bit-rots (signal registry goes stale; method cards aren't maintained; provenance fields get skipped)
- Parity tests become a maintenance burden that gets skipped first when time is short

Each of these has happened in organizations with far more resources than a solo developer.

**Proposed addition to PROP — new section VII.E:**
> **PROP-VII.E Failure modes and countermeasures.**
>
> | Failure mode | Leading indicator | Countermeasure |
> |---|---|---|
> | Research graveyard — promotions stop | No promotion package produced for >6 months | Quarterly self-review with explicit go/no-go on continuing research |
> | Production evolves around the pipeline | Production-only methods entering the signal registry at bronze tier without research validation | Rule: any signal producing operator-facing recommendations must have a registry entry, even if status=production-unvalidated |
> | Shared foundation bit-rot | Method cards with stale fields, missing versions, or referenced-but-nonexistent predecessors | Pre-commit hook validates registry structure; monthly manual audit |
> | Parity tests skipped | Test suite runtime exceeds pipeline tolerance, tests marked skip | Budget parity-test runtime as a first-class constraint; simplify or shard tests rather than skip |
> | Bifurcation discipline collapses under time pressure | Operator-facing changes made without touching the registry | Treat as a process violation even when the change is trivially correct; the discipline is the point |

### Finding 3.9 [ADD] [MEDIUM] — Source-of-truth correction protocol
DESIGN notes Minervini's *Trade Like a Stock Market Wizard* is treated as a reference but has not been formally adopted (RS methodology is an approximation pending book verification). Neither CRIT nor PROP addresses what happens when the primary source is acquired and found to disagree with implementation.

**Proposed addition to PROP — new section VI.E:**
> **PROP-VI.E Source-of-truth corrections.**
>
> When a primary source (book, paper, definitive publication) is acquired that corrects or refines a method currently implemented based on an approximation, the correction is handled as a standard research-to-production promotion cycle, not as a hotfix:
>
> 1. The correction is filed as a new method-card version (major version bump per PROP-III.B versioning rules, since output semantics change).
> 2. The corrected method enters research-branch validation against the same evidence criteria as any new method.
> 3. If validated, it enters shadow mode in production alongside the approximation.
> 4. If shadow-mode evidence supports the correction, the approximation is deprecated via the standard demotion pipeline (Finding 3.6).
>
> **Why not a hotfix:** source-of-truth corrections often turn out on investigation to be either (a) misremembered, (b) ambiguously specified in the source, or (c) context-dependent in a way the approximation accidentally captures. Treating them as hotfixes imports their uncertainty directly into production.

### Finding 3.10 [ADD] [MEDIUM] — Disciplined Swing Trader layer relationship
DESIGN specifies that *Disciplined Swing Trader* remains the operator-level methodology; Minervini and academic momentum work augment the signal-computation methodology. Neither CRIT nor PROP reaffirms this division explicitly, creating ambiguity about which source governs which concern.

**Proposed addition to PROP — new section I.A or an early paragraph in Section VII:**
> **Methodological sources, divided by concern:**
> - *Disciplined Swing Trader* (Lakes/peoplewish/Qullamaggie synthesis) governs the **operator-level** methodology: daily/weekly process, psychology, discipline, the "what should I do today" workflow.
> - Minervini, academic momentum research, and practitioner rule-sets (Morales/Kacher, Stockbee, Clenow, Gray-Vogel) govern the **signal-computation** methodology: how the universe is gated, how setups are detected, how trades are sized and managed.
>
> Both concerns are within scope. The bifurcated architecture implements this division physically: the research branch works on signal computation; the operational branch implements both signal output and operator workflow.

### Finding 3.11 [ADD] [LOW] — Paper-to-live transition
Both meta-documents and DESIGN assume EOD paper trading via Alpaca. The eventual transition to real money is itself a methodological event neither document addresses.

**Proposed addition to PROP — Phase 4 expansion or new Phase 5:**
> **Phase 5 — Real-money transition (deferred; re-evaluate after Phase 3).**
>
> Transition to real money is itself a methodological milestone, not merely a configuration change. Preconditions for Phase 5 consideration:
> - Phase 3 has delivered ≥3 promoted methods
> - Operator-behavior analytics (Workstream A5) shows stable recommendation-follow-through rates
> - Paper-trading win rate and expectancy track historical backtest expectations within a specified tolerance
> - Drawdown characteristics in paper match backtest drawdown characteristics
>
> Without these preconditions, paper-to-real transition is premature.

## 3.3 Stylistic consistency

### Finding 3.12 [REVISE] [LOW] — Tonal asymmetry
CRIT uses sharper rhetorical moves (*"that sequencing is backwards"*, *"it is serious, well-read, and unusually useful"*) than PROP, which is uniformly neutral. If the documents are for internal use only, this is fine. If either might be shared, the tonal gap is noticeable.

**Proposed action:** Match tone by softening CRIT slightly (see Finding 1.23) or sharpening PROP's executive summary. Recommendation: leave CRIT sharp — the sharpness is where its value comes from — and accept the tonal asymmetry as inherent to the genre difference (critique vs proposal).

### Finding 3.13 [ADD] [LOW] — Missing cross-references
CRIT never names the document it reviews (referred to as "the memo"). PROP never names CRIT (though its structure clearly responds to CRIT's findings). A future agent reading the documents needs explicit cross-references.

**Proposed action:**
- CRIT: first paragraph should state *"This critique reviews `Extending methodological basis.md` (the source memo, SRC). Its findings feed into the companion implementation proposal, PROP."*
- PROP: first paragraph should state *"This proposal implements the bifurcation strategy identified as necessary in the companion critique (CRIT §II.4). It does not assume familiarity with SRC beyond what CRIT summarizes."*

---

# Part 4 — Priority synthesis for agent consumption

If the downstream agent session must limit itself to a bounded set of changes across both documents, the following six are load-bearing. The rest are refinements.

| Rank | Finding | Document | Summary |
|---|---|---|---|
| 1 | 2.28 | PROP §VIII | Rewrite roadmap to reflect solo-developer pacing, acknowledge current work, and remove aspirational scope from Phase 4 |
| 2 | 2.9 | PROP §III.B | Expand signal-definition registry spec to concrete format (TOML), versioning (semver), required fields, and deprecation protocol |
| 3 | 2.13 | PROP §IV.B.1 | Bootstrap-first data strategy — yfinance + manual delistings, Norgate deferred until specific-study criteria met |
| 4 | 3.1 | Both | Reconcile operator governance treatment — operator is a signal flowing between branches, not a layer inside the alpha engine |
| 5 | 3.4 (also 2.29) | PROP §IX | Commit Pocket Pivot to fast-track path; reclassify earnings-proximity as production-pending-parameter-study |
| 6 | 3.8 | PROP §VII.E | Add failure-modes-of-bifurcation section with countermeasures |

Secondary high-priority findings that should be addressed in the same revision cycle:

- 1.5 (CRIT internal inconsistency on operator governance)
- 1.7 (CRIT should cross-reference PROP as its resolution)
- 1.20, 1.21 (CRIT retain/defer list corrections)
- 2.17 (PROP workstream ordering)
- 2.26 (PROP shadow mode must be visible by default)
- 3.2 (VCP consistency across CRIT, PROP, DESIGN)
- 3.6 (demotion pipeline — new PROP §VI.D)
- 3.7 (time-budget realism — new PROP §VII.D)

Findings tagged [LOW] are refinements that can be addressed opportunistically but should not delay the HIGH and MEDIUM changes.

---

# Part 5 — Agent handoff summary

The revised strategy and actionable roadmap developed in the downstream session should produce, at minimum:

1. **Revised PROP** incorporating Findings 2.28, 2.9, 2.13, 3.8, 3.6, 3.7, plus the medium-priority corrections listed in Part 4.
2. **Revised CRIT** addressing Findings 1.5, 1.7, 1.20, 1.21, plus internal consistency improvements.
3. **An initial signal-definition registry file** (`signal-registry.toml` or equivalent) with method cards populated for the six candidates in the revised PROP §IX fast-track and standard-research categories.
4. **A Phase 0 task list** extracted from the roadmap, sized for 20–40 hours of evening work, with no single task exceeding 4 hours.
5. **A lightweight catalog-maintenance protocol** (pre-commit hook, monthly audit checklist) addressing Finding 3.8 failure modes.

The revised documents should be internally consistent, should explicitly cross-reference each other and DESIGN, and should preserve the verbatim-keep sentences identified in Findings 1.2, 1.10, 1.11, 1.14, 2.1, 2.12, 2.21, 2.30.

The revised roadmap should be actionable in the sense that a subsequent agent session (or the developer directly) can pick up a task from Phase 0 and execute it without further strategic interpretation. Phase 0 tasks should be small enough and well-enough specified that they can be completed in a single evening.
