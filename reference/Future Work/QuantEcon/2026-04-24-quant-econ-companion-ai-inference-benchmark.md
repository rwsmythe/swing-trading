# QuantEcon Program — AI-Inference Benchmark Companion

**Date:** 2026-04-24
**Companion to:** [`./2026-04-24-quant-econ-future-research-program.md`](2026-04-24-quant-econ-future-research-program.md), [`./2026-04-24-quant-econ-companion-trigger-purpose-three-branch.md`](2026-04-24-quant-econ-companion-trigger-purpose-three-branch.md), [`./external-references.md`](external-references.md)
**Status:** Forward-looking strategic memo; **starting point for further discussion** with future sessions.
**Audience:** Future Claude Code / Codex sessions consulted on edge-decay measurement, plus the developer.

---

## What this captures

A clarifying conversation 2026-04-24 surfaced a measurement criterion that doesn't appear in the QuantEcon program's Theme 2 (decay detection) toolkit because it's specific to the post-LLM era and post-dates the canonical quant-decay literature. This companion captures the criterion, its rationale, and its methodology complications, so future sessions can engage with it productively.

This is **not a method to deploy yet.** It's a measurement framework that becomes relevant when the operational system is mature enough to benchmark against alternatives.

---

## The criterion — performance above AI inference

**Definition.** Track the operational system's output against what a typical AI-using retail participant would produce by querying a contemporary general-purpose LLM (Claude, GPT, Gemini, etc.) with a defensibly-typical prompt. The delta — system output minus AI-inference baseline — is a forward-leaning crowding metric.

**Reasoning chain (from the 2026-04-24 conversation):**

1. AI tools (Claude Code, ChatGPT, etc.) are universally available.
2. Many retail traders entering the market in 2026+ will use AI inference directly for trading recommendations rather than build rigorous tools.
3. AI training bias produces correlated outputs across users — many people querying similar prompts get similar responses.
4. Therefore, AI inference becomes a dominant channel by which methods get crowded.
5. **If the operational system beats AI inference, the methodology has runway** — the edge isn't yet absorbed into AI-trained correlated-behavior.
6. **If AI inference catches up to or beats the operational system, that is a decay signal** — the methodology has been absorbed into LLM training corpora and is being widely deployed via AI assistants.

This is a new mechanism for crowding that the canonical quant literature (Hamilton, Bai-Perron, CUSUM, structural break tests) does not address because it predates LLMs.

---

## Why this is sharper than "above-market returns" alone

The QuantEcon program's Path B trigger (per [`2026-04-24-quant-econ-companion-trigger-purpose-three-branch.md`](2026-04-24-quant-econ-companion-trigger-purpose-three-branch.md)) is "operational system produces net-positive returns above a relevant market benchmark." That trigger has a known weakness: above-market returns can be entirely momentum-factor beta (cheap via momentum ETFs).

**Above-AI-inference is stricter.** The reference population is more relevant to the actual competitive landscape:

- **Above SPY** = "you're not just buying-and-holding."
- **Above factor ETFs** = "you're not just doing what a momentum ETF does."
- **Above AI inference** = "you're not just doing what every AI-aided retail participant does."

The third is the closest match to the actual marginal competitor in 2026+ retail markets. It's not a replacement for the prior two checks — it's a complementary check that adds an AI-era crowding signal the others can't capture.

---

## Methodology complications — honest list

Before this criterion can be operationalized, six real complications need handling:

### 1. Production LLMs sandbag financial advice

Claude, ChatGPT, Gemini are all trained to refuse direct trading recommendations or wrap them in heavy disclaimers. The naive prompt "what should I trade today?" gets refusal or generic "consult a financial advisor" output. The benchmark prompt design must be defensible — neither sandbagged ("be vague") nor over-engineered ("here's all my market data, here's the universe, here's the criteria"). The right design is "what a typical AI-using retail trader would actually prompt with," which is itself an empirical question worth a small separate study.

### 2. Non-determinism in LLM output

Same prompt, same model, different responses (unless temperature=0, which biases output). The benchmark needs a sampling protocol — average over N queries, document the variance. Not blocking but requires explicit methodology.

### 3. Prompt-engineering as confound

A naive prompt and a retrieval-augmented prompt with full market context produce wildly different baselines. The choice of prompt structure IS the methodology. Once committed, it must be versioned and held stable to allow temporal comparison.

### 4. Direction of causation when AI inference catches up

If the AI-inference benchmark improves over time relative to the operational system, three things could be happening:

- **Crowding (the central hypothesis).** AI training has absorbed methods like the operational system; many people now produce similar output; edge decays.
- **Methodology validation.** The operational system's approach is becoming the dominant paradigm because it's correct; many people know about it; edge is being slowly diluted but the methodology remains sound.
- **General capability improvement.** The LLM has gotten smarter at reasoning about anything, including markets. The benchmark moves up because the benchmark improved, not because crowding happened.

Distinguishing these matters because the response differs:
- (1) requires demoting affected methods per V2.1 §VII.E.
- (2) requires accepting some edge dilution but continuing operations.
- (3) requires recognizing the benchmark is non-stationary and recalibrating.

Distinguishing them empirically is hard. May require running the benchmark across multiple LLM model versions and comparing the rate-of-catchup against the rate-of-general-capability-gain in those models on unrelated benchmarks.

### 5. AI tooling improves rapidly — benchmark is a moving target

Claude Opus 4.7 today; Opus 5 within 6–12 months. The benchmark must be versioned ("vs Claude Opus 4.7", "vs Claude Opus 5") and tracked across versions. Cross-version comparison is comparing different things and must be acknowledged as such. Possible mitigation: track multiple model families simultaneously (one Claude version, one GPT version, one open-source model) so cross-family agreement filters out idiosyncratic model effects.

### 6. The criterion is decay-detection, not edge-validation

Beating AI inference doesn't mean the operational system has edge in absolute terms. It means the operational system's edge isn't yet absorbed by AI inference. The system could be losing to SPY while still beating AI inference, in which case "this method has runway" is misleading. **This criterion belongs alongside above-market returns as a complementary check, not a replacement.**

---

## Where this fits in the QuantEcon program

The criterion belongs as an addition to **Theme 2 (Method-decay detection)** alongside the canonical decay-detection toolkit (structural break tests, CUSUM, rolling Sharpe stability, crowding metrics). Specifically:

- **Existing Theme 2 crowding metrics** (13F overlap, short-interest curation, ETF flow concentration, retail-sentiment proxies) measure where money already is. These have known limitations: data is expensive or proprietary, signals lag, retail-sentiment proxies are crude.
- **AI-inference benchmark** is a forward-leaning crowding signal that measures where retail attention is heading via the dominant tool channel. Cheap to implement (API key + stable prompt template). No proprietary data dependency.

**Operational complexity classification (per QuantEcon Q4):** L2 for the operator-visible output (delta vs. AI inference, trended over time, with model-version annotations). L3 for the underlying methodology (prompt design, sampling protocol, version-comparison normalization).

**This criterion does NOT change the QuantEcon program's sequencing.** It still belongs in Theme 2's "minimum-viable Phase R1" build, alongside performance-based decay detection. The crowding-metrics sub-theme that the QuantEcon doc flags as potentially-deferred-due-to-cost gets a viable concrete implementation (the AI-inference benchmark) that the canonical version (13F + short-interest + flow) lacks.

---

## AI's role in this project — operator drives, agent serves

A clarifying conversation 2026-04-24 surfaced what the recursive concern from earlier in this companion actually amounts to, and what it does not amount to.

**Two patterns of AI use in trading work, only one of which this project follows:**

- **AI as active calculator on the trading problem.** Operator queries the LLM with market data and asks for trading decisions. LLM produces recommendations. Output is non-deterministic, non-auditable, varies by prompt and model version. The agent is effectively promoted to principal — what the agent's table of weights prioritizes drives the output.
- **AI as passive knowledge library for building deterministic systems.** Operator queries the LLM for "what's the canonical way to compute X," "is this implementation correct," "what are the known yfinance gotchas." The information informs deterministic Python code that the operator (or implementer) writes, tests, commits, and runs reproducibly. The principal-agent structure is preserved: operator drives, agent serves.

This project is the second pattern. Trading decisions are made by deterministic tooling that produces the same output for the same inputs every time. Audit trail, reproducibility, and accountability hold.

**The principal-agent framing is more fundamental than the lookup-vs-calculation framing.** The operator drives the paths the agent takes rather than letting the agent drive the problem through its own table of weights. Operator sets goals, methodology choices, gating decisions, scope boundaries, tradeoff judgments. Agent executes within the operator's framing using its knowledge as a resource.

**What the recursive concern actually is.** Not "AI does the trading." The narrower concern: when the operator consults Claude as a passive knowledge library, the methodology population Claude surfaces is biased by Claude's training corpus. If two methodologies exist — Method A (well-documented in books, papers, Substacks) and Method B (known only to a small circle with no public documentation) — Claude will surface Method A and miss Method B. Two AI-aided developers building independently might converge on similar method choices not because they're copying each other, but because they're pulling from the same Claude-shaped knowledge tree.

**Why this concern is narrow in practice:**

- Implementation specifics still diverge — different RS thresholds, different MA lookbacks, different VCP tightness criteria. The space of parameter choices isn't pinned down by the literature even when the literature is shared.
- Operational discipline is non-fungible. Pre-registration, adversarial review, defer-on-weak-signal are protocol moves most AI-assisted retail developers won't adopt. The discipline is itself a differentiator.
- The combination of methods + operator's individual judgment (when to enter, exit, size) creates high-dimensional choice space that AI inference can't fully replicate even with shared methodology vocabulary.

**Blindspot nuance — operator-drives has its own failure mode.** "Operator drives, agent serves" doesn't mean "operator is omniscient." The operator's table-of-weights also has blindspots, and one thing the agent's table-of-weights might surface is something the operator wouldn't think to ask about. Letting the agent drive gives the agent's blindspots dressed up as objectivity; operator-driven discipline accepts the operator's blindspots in exchange for audit trail and accountability. Both have costs. Mitigation: periodically invite the agent to surface things the operator might have missed, with the operator retaining the decision to act or not. That is a different conversational pattern from execution-by-spec — closer to "what am I not asking that I should be?" than to "execute this spec."

---

## Connection to V2.1's three-branch architecture

Per [`2026-04-24-quant-econ-companion-trigger-purpose-three-branch.md`](2026-04-24-quant-econ-companion-trigger-purpose-three-branch.md), the project has three branches: Operational, Applied Research, Basic Research.

The AI-inference-benchmark criterion lives across all three:

- **Operational:** the system that's being benchmarked. Surfaces the delta-vs-AI-inference as a status signal.
- **Applied Research:** can use the benchmark as part of a study's evaluation criteria. E.g., "does adding earnings-proximity exclusion improve performance vs AI-inference baseline by ≥X%?"
- **Basic Research:** developing the AI-inference-benchmark methodology itself, characterizing its drift across model versions, distinguishing the three causation candidates from §"Methodology complications" item 4.

It's a measurement framework, not a method. It applies to whatever is being measured.

---

## Open discussion topics for future sessions

1. **What constitutes a "defensibly-typical" benchmark prompt?** This is empirical — survey what AI-using retail traders actually prompt with, then commit to a representative one. Subject to evolution as user behavior shifts.
2. **What model(s) should the benchmark target?** Single dominant model (Claude Opus current), or a basket (Claude + GPT + open-source)? Basket is more robust but more expensive and harder to interpret.
3. **At what cadence is the benchmark run?** Daily (high overhead), weekly (matches operator workflow), monthly (low resolution for fast-decaying signals)?
4. **How to handle LLM refusals?** When the model refuses to answer, does that count as "no benchmark data this period," or is the refusal itself a signal (e.g., the model has been trained to be especially cautious about a setup type, suggesting market awareness)?
5. **Should the benchmark be archived for forensic review?** A decay event detected via the benchmark gains interpretability if you can replay "what was the AI inference saying around the time the edge disappeared?" Storage is cheap; archival of LLM outputs is technically simple.
6. **Methodology-population convergence — empirical magnitude unknown.** The "AI's role in this project" section names the narrow recursive concern: AI-aided developers consulting the same passive knowledge library converge on similar methodology choices. How large is this convergence in practice? An empirical study would compare methodology choices made by AI-aided vs. non-AI-aided developers solving similar problems. This is itself a meta-research question; not actionable now, but worth posing for any future session that takes the AI-inference benchmark operational.

---

## Cross-references

- QuantEcon program (governing): [`./2026-04-24-quant-econ-future-research-program.md`](2026-04-24-quant-econ-future-research-program.md)
- Path A/B + three-branch companion: [`./2026-04-24-quant-econ-companion-trigger-purpose-three-branch.md`](2026-04-24-quant-econ-companion-trigger-purpose-three-branch.md)
- External references: [`./external-references.md`](external-references.md)
- Governing project strategy: [`../2026-04-23-bifurcated-strategic-implementation-proposal-v2.1.md`](../2026-04-23-bifurcated-strategic-implementation-proposal-v2.1.md)
- Current operational state: `CLAUDE.md` (repo root)
