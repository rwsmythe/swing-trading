# Tranche B-research session 2a — Implementer Dispatch Brief

**Audience:** Fresh Claude Code instance with no prior conversation context.
**Mission:** Execute the first two Phase 0 "Next" tasks from `research/phase-0-tasks.md` — evaluate ≥2 free earnings-calendar sources, then decide the historical-candidate data source. Pure documentation output. No code, no harness build, no study execution.
**Expected duration:** 3–5 hours.
**Prepared:** 2026-04-24 by orchestrator instance.

---

## 0. Read first

1. `CLAUDE.md` — project conventions, gotchas, the `## Strategy` section (pointing at V2.1 + research branch layout). Note Windows+gitbash environment and `yfinance` rate-limit gotchas.
2. `reference/Future Work/2026-04-23-bifurcated-strategic-implementation-proposal-v2.1.md` — governing strategy. Focus on §V (Research and Verification branch), particularly §V.E (bootstrap-first data strategy, time-boxed manual delistings), §V.F (research evidence standard), and §III principle 7 (time-budget anchor).
3. `reference/Future Work/2026-04-23-rebuttal-response-for-implementors.md` — binding clarifications. Focus on §1 (minimum viable governance), §3 (research infrastructure only as needed), §4 (manual delistings time-boxed), and the Anti-patterns list.
4. `research/README.md` — research-branch intro.
5. `research/method-records/earnings-proximity-exclusion.md` — the method record this study validates. Note the `blackout_trading_days` parameter, the four variant values {3, 5, 7, 10}, and the "Validation notes" caveat about free-calendar source reliability.
6. `research/studies/earnings-proximity-exclusion.md` — the study design. Note the parity standard (fixture identity + toleranced vendor-backed equivalence) and the "Data" section which names this exact evaluation task as a Phase-0 prerequisite.
7. `research/phase-0-tasks.md` — task list. You are executing the first two items in the "Next" section.
8. `docs/tranche-b-research-brief.md` and `docs/tranche-b-research-session-2a-brief.md` (this file) for style precedent. The research-branch pattern is minimum-viable docs-only through the scaffolding stage; your session carries that forward.

**Skill posture.** Do NOT invoke `copowers:*` wrapper skills. This is pre-study data-source evaluation, not design work or code execution. `copowers:adversarial-critic` applies to Session 2c's evidence summary (not this session). Invoke `superpowers:verification-before-completion` before declaring done.

---

## 1. Strategic context (compressed)

The project runs a bifurcated architecture (research + operational) on a minimum-viable shared foundation per V2.1. The first decision-grade study — earnings-proximity exclusion — is designed in `research/studies/earnings-proximity-exclusion.md` and needs data before it can run. This session produces that data-decision layer.

Two decisions to document:

1. **Which free earnings-calendar source** (one of yfinance, Finviz, Yahoo Finance calendar scrape, or another candidate you identify) is most reliable for date precision across the operating universe.
2. **Where historical candidate data comes from** — either the repo's own `candidates` table (if it has enough history) or a synthetic-replay harness built atop yfinance EOD data.

Both decisions feed Session 2b (harness build). You do NOT build the harness in this session.

**Posture throughout:**

- **Bootstrap-first (V2.1 §V.E).** Free sources only. Do not propose a paid-data decision unless the free-source evaluation actively demonstrates a specific-study blocker per V2.1 §V.E criteria.
- **Time-boxed manual delistings (rebuttal §4).** If any source gap requires manual intervention, scope the manual maintenance explicitly with an expiration condition.
- **Minimum viable (V2.1 §IX).** Do not build infrastructure to systematize the evaluation; a short comparison note is the deliverable, not a harness.
- **Anti-patterns — "infrastructure displacement" (rebuttal Anti-patterns list)** applies especially here. You are evaluating sources, not writing a vendor-abstraction layer.

---

## 2. Session scope

### In scope — one commit with three or four artifacts

| # | Artifact | Kind |
|---|----------|------|
| T1 | `research/notes/earnings-calendar-sources.md` — comparison note per source | Docs |
| T2 | `research/notes/historical-candidate-source-decision.md` — decision memo | Docs |
| T3 | Update `research/phase-0-tasks.md` — move the two tasks from "Next" to "Done" | Docs |
| T4 | (if applicable) Track this brief | Docs |

### Explicitly out of scope

- Building the study harness. That is Session 2b.
- Running the study. That is Session 2c.
- Any code under `swing/` or `research/`. Docs only.
- Evaluating paid data sources. Bootstrap-first per V2.1 §V.E.
- Building any vendor-abstraction layer, source-comparison tooling, or calendar-diff utility. The evaluation is an operator-facing reasoning exercise, not a test harness.
- Proposing changes to the study design in `research/studies/earnings-proximity-exclusion.md`. The study is approved as designed. If evaluation reveals a study-design concern, flag it in the return report — do not edit the study file.
- Proposing changes to the method record `research/method-records/earnings-proximity-exclusion.md`. Same treatment.

### Expected branching outcomes

Two shapes your evaluation might land on:

- **Shape A — one clearly-superior free source exists for date precision.** Document the comparison, name the winner, note reliability caveats, commit the decision. Clean.
- **Shape B — no free source is clearly reliable enough for the study's needs.** Document why, surface specific failure modes, and the decision memo explicitly states "free-source evaluation fails V2.1 §V.E criteria → paid-data decision escalated to orchestrator." You do NOT unilaterally pick a paid source.

If you find yourself tempted to build a "small reliability-checker script" to automate the comparison, stop. The evaluation is spot-check + documentation, not automation.

---

## 3. Binding conventions

- **Branch:** `main`.
- **Commits:** conventional-commits (`docs(research): …`). No Claude co-author footer. No `--no-verify`. No amending.
- **Tests:** fast suite green (no code changed; sanity-check with `python -m pytest -m "not slow" -q` before commit).
- **Ruff:** N/A.
- **Phase isolation:** N/A (no `swing/` changes; `research/` is not in the read-only list).

---

## 4. Task specifications

### T1 — Earnings-calendar source evaluation

Create `research/notes/earnings-calendar-sources.md`. The directory `research/notes/` does not yet exist; create it.

Evaluate at minimum three candidate sources:

1. **yfinance** — `Ticker.calendar`, `Ticker.get_earnings_dates()`. Library version installed in this repo per `pyproject.toml`.
2. **Finviz CSV export** — existing `data/finviz-inbox/*.csv` files contain some earnings-adjacent columns; check what's actually available across the historical exports in that directory.
3. **Yahoo Finance calendar scrape** — publicly-visible earnings calendar at `https://finance.yahoo.com/calendar/earnings`. HTML scrape, not API.

Additional sources you can evaluate if time permits (not required): Nasdaq earnings calendar (publicly visible), EarningsWhispers (partial free tier), Zacks (partial free tier). The brief does not require these; you may skip.

**What to evaluate per source:**

- **Date-precision reliability** — for EOD swing trading, the load-bearing question is "does the source get the calendar date right?" (not the before/after-market timing). Do a spot-check against at least 10 tickers × ≥3 months of history using whatever authoritative reference you can reach at no cost. Suggested reference: company press releases indexed via web search for each spot-check ticker-quarter pair, or the company's investor-relations page. If time-boxing per spot check becomes excessive, reduce sample size and flag.
- **Universe coverage** — does the source have rows for tickers the pipeline's Finviz universe contains? Try ≥5 representative tickers (large-cap, mid-cap, small-cap).
- **Ergonomics** — rate limits (yfinance especially), CSV format stability, HTML-scrape fragility, authentication requirements.
- **Failure modes** — missing data, silently-wrong data, rate-limiting, schema drift.

**Format of the deliverable file** (suggested structure; adapt as the evaluation dictates):

```markdown
# Earnings-calendar source evaluation

**Date:** 2026-MM-DD
**Author:** <implementer session-id>
**Purpose:** Evaluate free earnings-calendar sources for the earnings-proximity-exclusion study (`../studies/earnings-proximity-exclusion.md`). Bootstrap-first per V2.1 §V.E.
**Scope:** Date-precision reliability only (EOD trading; intraday timing out of scope).

## Sources evaluated

### Source 1 — <name>

- **Access pattern:** <Python lib call / HTTP endpoint / CSV column>
- **Sample size checked:** <N tickers × M months>
- **Date-precision hits / misses / unknowns:** <X / Y / Z>
- **Universe coverage:** <what was found for the 5 representative tickers>
- **Ergonomics:** <rate limits, format stability, auth>
- **Failure modes observed:** <bullets>
- **Verdict:** <pass / fail / marginal, with criterion>

### Source 2 — <name>

...

## Comparison table

| Source | Date accuracy | Universe coverage | Ergonomics | Verdict |
|---|---|---|---|---|
| ... |   |   |   |   |

## Recommendation

<One of:>
- **Pick source X** for the earnings-proximity study. Rationale: ...
- **None of the evaluated free sources meet V2.1 §V.E criteria.** Escalate to orchestrator for paid-data decision. Specific failure: ...

## Reliability caveats for the chosen source (if any)

<Known failure modes that the study harness and evidence summary must account for. The study's parity standard ["toleranced vendor-backed equivalence ... hand-checked spot set of ≥10 tickers × ≥3 calendar months"] inherits these caveats.>
```

**Acceptance:** three sources evaluated, each with a date-precision spot-check number. A recommendation. Reliability caveats identified for whichever source the recommendation names (or, in Shape B, an escalation memo).

**Note — you can import `yfinance` and make real calls for evaluation purposes.** This session is not under the `swing/` Phase-isolation rule. However:

- Be mindful of yfinance rate limits (CLAUDE.md documents these).
- If a network call fails transiently, retry sparingly; do not build retry infrastructure.
- If you discover a failure mode worth documenting (e.g., yfinance returns stale calendar), capture it as a finding rather than working around it.

### T2 — Historical-candidate source decision

Create `research/notes/historical-candidate-source-decision.md`.

**Context.** The study needs historical candidate data — tickers that entered the A+ bucket on various `action_session_date`s, with entry/stop recommendations. Two options per the Phase 0 task:

- **Option A — Repo's own `candidates` table.** Use real pipeline output. Pros: high verisimilitude. Cons: limited history (project is active refactor; pipeline hasn't been running continuously); may not cover enough trading days to produce statistically meaningful parameter-sweep results.
- **Option B — Synthetic replay.** Generate historical candidates by running the A+ criteria against yfinance EOD data over a longer window (e.g., past 2–3 years). Pros: more history; more statistical power. Cons: requires re-implementing (or importing) the A+ criteria against historical data; introduces look-ahead risk if not carefully handled; doesn't exercise the real pipeline's output shape.

**What to investigate and document:**

1. **How much history does the repo's `candidates` table actually have?** Query the DB at `%USERPROFILE%/swing-data/swing.db` (read-only — do not mutate). Report row count, distinct `action_session_date` count, date range, distinct A+ ticker count.
2. **Is the history enough for the study's statistical needs?** A rough calculus: the study evaluates 4 variants + baseline against 4 metrics (expectancy, gap-through rate, gap-through magnitude, signal volume). For expectancy to be estimable with reasonable confidence, you typically want ≥30 trades per variant. 4 variants × 30 = 120 trades minimum; 200–300 is more comfortable. Compare to the repo's actual A+ trade count.
3. **What would a synthetic replay actually require?** Sketch (do not implement) the components: historical EOD bars via yfinance, a port of the A+ criteria computation against those bars, a port of the stop-and-sizing logic, plus the earnings-calendar integration from T1. How much of the logic can be imported from `swing/evaluation/`, `swing/trades/`, and `swing/recommendations/` (which are production code consumed read-only in the research branch per CLAUDE.md)?
4. **Make a decision.** State the choice explicitly with rationale.

**Decision criteria (stated here to reduce implementer latitude — these are the orchestrator's rulings):**

- Prefer Option A if the repo has ≥120 distinct A+ trade signals across ≥60 trading days. Sufficient for a minimum-viable study; avoids Option B's look-ahead-risk setup burden.
- Prefer Option B if Option A is insufficient AND the port-import sketch in (3) shows that ≥70% of the logic can be reused from `swing/` read-only. Build the minimum replay to fill the gap.
- Escalate to orchestrator if BOTH Option A is insufficient AND Option B would require substantial new logic (more than a Session 2b can reasonably contain per V2.1 §III.7 time-budget). A paid-data or synthetic-data decision at that scale needs orchestrator sign-off.

**Format of the deliverable file:**

```markdown
# Historical-candidate source decision

**Date:** 2026-MM-DD
**Author:** <implementer session-id>
**Purpose:** Pick the data source for the earnings-proximity-exclusion study's historical candidates.

## Repo `candidates` table audit

- Rows: <N>
- Distinct action_session_dates: <N>
- Date range: <YYYY-MM-DD> to <YYYY-MM-DD>
- Distinct A+ tickers: <N>
- Trade signals equivalent (aplus bucket rows): <N>

## Statistical adequacy

<Does the repo's history meet the ≥120 / ≥60 threshold?>

## Synthetic-replay sketch (if Option A insufficient)

- Components needed: <list>
- Estimated reusable from `swing/`: <%>
- Estimated new logic: <components>
- Rough effort: <hours>

## Decision

<One of:>
- **Option A — repo `candidates` table** (sufficient)
- **Option B — synthetic replay** (Option A insufficient; replay viable)
- **Escalate to orchestrator** (Option A insufficient; Option B substantial)

## Rationale

<Why, citing evidence from the audit and sketch above.>

## Implications for Session 2b (harness build)

<What Session 2b's harness will read from; any dependencies this decision creates.>
```

**Acceptance:** A clear decision (A / B / escalate) with the audit numbers and, if applicable, the replay sketch.

**Important — database connection.** The repo's SQLite DB lives at `%USERPROFILE%/swing-data/swing.db` (per CLAUDE.md invariants). On the Windows/gitbash environment this is `C:/Users/rwsmy/swing-data/swing.db`. Connect via `sqlite3` stdlib or via the project's existing `swing.data.db.connect` helper. Read-only access; do NOT mutate.

### T3 — Update `research/phase-0-tasks.md`

The two tasks you just completed move from "Next" to "Done" with the commit date. Follow the existing formatting. The remaining "Next" tasks ("Build the study harness," "Run the study," "Write evidence summary") stay in "Next."

Update pattern:

```markdown
## Done

- [x] Adopt V2.1 as governing strategy (Tranche A, 2026-04-23).
- [x] Create research-branch scaffolding: directory, README, method-record template (Tranche B-research, 2026-04-23).
- [x] First method record: earnings-proximity exclusion (Tranche B-research, 2026-04-23).
- [x] First study design: earnings-proximity parameter sweep (Tranche B-research, 2026-04-23).
- [x] Evaluate ≥2 free earnings-calendar sources for date-precision accuracy (Tranche B-research 2a, 2026-04-24). See `notes/earnings-calendar-sources.md`.
- [x] Decide historical-candidate data source (Tranche B-research 2a, 2026-04-24). See `notes/historical-candidate-source-decision.md`.
```

### T4 — Track this brief

Confirm `docs/tranche-b-research-session-2a-brief.md` is untracked (pre-commit) and stage it. Also stage the new `research/notes/` directory and its contents plus the updated `research/phase-0-tasks.md`.

---

## 5. Commit

One commit covering all four tasks.

```bash
git add research/notes/ research/phase-0-tasks.md docs/tranche-b-research-session-2a-brief.md
git status
```

Commit message:

```
docs(research): evaluate earnings-calendar sources and decide historical-candidate source

- research/notes/earnings-calendar-sources.md — free-source evaluation
  per V2.1 §V.E bootstrap-first; <N> sources assessed for date-precision
  reliability; <chosen source | escalation note>.
- research/notes/historical-candidate-source-decision.md — pick between
  repo candidates table and synthetic replay; <decision>.
- research/phase-0-tasks.md — move the two completed tasks to Done.
- Track docs/tranche-b-research-session-2a-brief.md.

Sessions 2b (harness build) and 2c (run + evidence summary + adversarial
review) depend on these decisions.
```

Adjust the `<placeholders>` in the body to reflect actual findings.

Run `python -m pytest -m "not slow" -q` before commit. Expected green (no code changed).

---

## 6. Done criteria

- One commit on `main` with the message above.
- `research/notes/earnings-calendar-sources.md` committed with ≥3 sources evaluated and a clear recommendation (or escalation).
- `research/notes/historical-candidate-source-decision.md` committed with an audit + decision (A / B / escalate).
- `research/phase-0-tasks.md` updated with the two tasks in Done.
- This brief tracked.
- Fast suite green.
- Return report produced.

---

## 7. Return report format

```
## Tranche B-research session 2a return report

### Commit landed
- <SHA> docs(research): evaluate earnings-calendar sources and decide historical-candidate source

### Tests
- After: <N> passing, 0 failing (fast suite). No change from 568 baseline expected.

### Earnings-calendar source evaluation — summary
- Sources evaluated: <list>
- Spot-check scope: <N tickers × M months>
- Date-precision outcomes: <summary>
- Recommendation: <chosen source | escalation>
- Key caveats: <bullets>

### Historical-candidate source decision — summary
- Repo `candidates` audit: rows=<N>, distinct dates=<N>, A+ signals=<N>, date range=<range>
- Statistical adequacy: <yes/no vs. ≥120/≥60 threshold>
- Decision: <A | B | escalate>
- Rationale: <brief>

### Deviations from brief
<Empty if none.>

### Items flagged but not done (scope discipline)
<Any adjacent observations the evaluation surfaced that are out of scope for this session.>

### Open questions for orchestrator
<Anything the brief under-specified, or that the evaluation needs the orchestrator to rule on before Session 2b proceeds.>
```

---

## 8. If you get stuck

- If one of the three required sources is un-evaluatable (e.g., a scrape endpoint blocks, a library raises an exception you can't resolve quickly), document the barrier in the comparison file as a finding and continue with the remaining sources. Three is a minimum; if only two evaluate cleanly, the decision can still land — note the gap explicitly.
- If the repo's `candidates` table is empty or near-empty (pre-Phase-3 refactor state, or pipeline never ran in this workspace), Option A is clearly insufficient — do the replay sketch anyway to inform Session 2b's scope.
- If the rebuttal-response Anti-patterns list feels like it's forbidding something you want to do (e.g., "just build a small validator script"), it probably is. Defer and document.
- If you find a study-design concern (e.g., the chosen source can't cover the full variant-window's lookback), flag in "Open questions for orchestrator" — do not edit the study design.
- If you find yourself computing trade-level backtest statistics, stop — that is Session 2c's job. This session is data-source evaluation only.
