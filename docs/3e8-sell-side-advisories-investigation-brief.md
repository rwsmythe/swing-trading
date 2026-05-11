# 3e.8 — Sell-side advisories investigation brief

**Audience:** Fresh Claude Code instance with no prior conversation context.

**Mission:** Investigate the current sell-side / trim / take-profit advisory surface in the swing-trading project; reconcile against Minervini SEPA + Disciplined Swing Trader + Qullamaggie commentary doctrine; produce a structured analysis document with specific recommendations including trade-maturity-stage gating per Tier-3 #6 doctrine. **Output is a Markdown analysis document, NOT code.** Subsequent implementation (if any recommendation is approved) routes through a separate brainstorm/dispatch cycle.

**Expected duration:** ~2-4 hr investigation + ~30-45 min dispatch overhead. Total ~2.5-4.75 hr.

**Skill posture:**
- Invoke `superpowers:subagent-driven-development` directly (NOT via the `copowers:executing-plans` wrapper).
- DO NOT invoke `superpowers:writing-plans` or `copowers:brainstorming` — this is an investigation, not a design.
- Adversarial review via `copowers:adversarial-critic` after the analysis doc lands. Codex catches factual errors in doctrine reconciliation + missing-gap claims + recommendation-classification routing. Iterate to NO_NEW_CRITICAL_MAJOR. Expected 2-3 rounds.

---

## §0 Read first

### §0.1 Backlog entry
- `docs/phase3e-todo.md` §3e.8 — "Sell-position indications for winning trades (INVESTIGATION; operator-surfaced 2026-05-08)"

### §0.2 Code surface (existing sell-side advisory rendering — read-only context)

- `swing/trades/advisory.py` — current advisory rule surface. Read end-to-end. This is the source-of-truth for what advisories the framework emits today (trail-MA at 20MA pre-+2R, 10MA post-+2R per Phase 3d Tier-3 #6 doctrine; exit-below-MA-on-volume; etc.).
- `swing/web/templates/partials/open_positions_row.html.j2` — dashboard advisory rendering. Each open-positions row has an advisory column populated from `OpenPositionsRowVM.advisories: tuple[AdvisorySuggestionVM, ...]`.
- `swing/web/view_models/open_positions_row.py` (or `dashboard.py`) — VM construction; locate the `advisories=` builder call to understand the full pipeline from `swing/trades/advisory.py` rules → VM → template.
- `swing/data/repos/daily_management.py` — Phase 8 `action_taken` enum + `daily_management_records` schema. The `action_taken` field captures operator post-fact decisions; survey what discrete actions are enumerated (e.g., `no_action`, `tighten_stop`, `partial_exit`, `full_exit`, etc.). The full enum is in the schema CHECK constraint OR in a Python type alias somewhere — find it.
- `swing/data/migrations/0016_phase8_daily_management.sql` — confirms the `action_taken` enum at the DB-level CHECK constraint.

### §0.3 Reference materials (doctrine sources)

**Available to read directly:**

- `reference/methodology/` — source-of-truth transcriptions of methodology (Minervini SEPA + Disciplined Swing Trader). Read END-TO-END. These are the BINDING references — any production change driven by methodology routes through V2.1 §VII.F source-of-truth correction protocol per CLAUDE.md `## Strategy`.
- `reference/Future Work/2026-04-23-bifurcated-strategic-implementation-proposal-v2.1.md` — §VII.F is the source-of-truth correction protocol; consult before recommending any change to operational classification logic.

**Available via MCP server (per CLAUDE.md memory):**

- **Qullamaggie MCP server** — locally-running at `http://localhost:9871/mcp`. Tools: `mcp__qullamaggie__*`. Knowledge base of Kristjan Kullamägi's trading commentary (437 stream sessions, Oct 2019 – Dec 2021; ~2.5M words). **Reference-only**, NOT a source-of-truth. Use for: cross-checking sell-side discipline patterns Kullamägi articulates that map to Minervini sell rules; identifying confluence vs divergence across the three sources. Use the `mcp__qullamaggie__query_trading_rules` + `mcp__qullamaggie__search_transcripts` tools for sell-side rule lookup.

**NOT available directly (per CLAUDE.md memory):**

- "Trade Like a Stock Market Wizard" (Minervini) — physical copy only; not available as PDF or transcribed text. Rely on the `reference/methodology/` transcriptions for whatever Minervini sell-side rules are captured there. If the transcriptions are incomplete, flag the gap explicitly in the analysis (do NOT guess at Minervini's specific rules; cite what's in `reference/methodology/` or note absence).
- "Disciplined Swing Trader" — PDF should be available; check `reference/methodology/` or similar for the transcription.

### §0.4 Tier-3 #6 framing (BINDING context for maturity-stage gating)

- `docs/orchestrator-context.md` — search for "Tier-3 #6" and read every reference. Established framing:
  - **Trade-maturity stages:** new (~0R) → maturing → mature (+1.5R-2R, default 20MA trail) → well-mature (+2R+, upgrade to 10MA trail).
  - **Operator framing:** "trade has to prove itself" (Minervini) — different sell-side discipline applies at each maturity stage.
  - DHC trade is currently approaching +1.5R / 20MA trail-MA decision territory; investigation should produce decision guidance applicable to DHC + future trades at the same stage.

### §0.5 LOCKED DESIGN DECISIONS (DO NOT re-litigate)

Locked by orchestrator + operator in-thread design lock 2026-05-10:

1. **Output is a Markdown analysis document at `docs/3e8-sell-side-advisories-investigation.md`.** No code change in this dispatch.
2. **Single dispatch covering all 3 phase3e-todo subtasks** (survey + reconciliation + recommendations). Operator-locked vs phased.
3. **Tier-3 #6 trade-maturity-stage gating IS in scope.** Recommendations cover both standalone sell-side advisories AND per-maturity-stage gating. Subsumes the deferred Tier-3 #6 work item.
4. **Recommendations must classify each as either:**
   - **Advisory-message-only** (extends `swing/trades/advisory.py` rule set; emits a new advisory message to dashboard; does NOT change classification or stop-management logic). Routes through ordinary brief-then-dispatch path.
   - **Classification-altering** (changes A+ vs sub-A+ logic, changes initial-stop derivation, changes maturity-stage thresholds, etc.). Routes through V2.1 §VII.F source-of-truth correction protocol.
   - For each recommendation, the analysis MUST explicitly state which classification + cite V2.1 §VII.F if applicable.
5. **No actual implementation in this dispatch.** If any recommendation is operator-approved post-investigation, it gets a separate brainstorm/writing-plans/executing-plans cycle.
6. **Doctrine sources to consult (in priority order):**
   1. `reference/methodology/` — primary source-of-truth (highest authority)
   2. `reference/Future Work/2026-04-23-bifurcated-strategic-implementation-proposal-v2.1.md` — governance protocol
   3. Qullamaggie MCP — reference cross-check (lower authority; explicitly NOT source-of-truth per CLAUDE.md memory)
   4. `docs/orchestrator-context.md` Tier-3 #6 framing — project-internal binding context
7. **Citation discipline:** every claim about a doctrine rule MUST cite the source file/section/page (or Qullamaggie transcript ID + key phrase). Unverifiable claims (e.g., "Minervini says X" without a transcription source) MUST be flagged as `[UNVERIFIED — physical-copy-only claim; flag for operator]`.
8. **Analysis doc structure (binding):**
   - **§1 Current sell-side advisory surface** — exhaustive enumeration of every advisory the framework emits today; per-rule trigger condition + UI surface + per-row vs aggregate emission. Source code citations.
   - **§2 Doctrine reconciliation** — for each known doctrine rule (Minervini SEPA sell-side; DST take-profit; Qullamaggie cross-check), document whether the framework currently implements it + per-rule "implemented / partially-implemented / not-implemented" classification + citations.
   - **§3 Identified gaps** — synthesis of §2 findings; ordered by operational urgency. Each gap is a specific behavioral pattern the framework misses.
   - **§4 Recommendations** — for each gap, specific proposed advisory rule (with trigger condition + emission surface + maturity-stage gating per Tier-3 #6) + classification (advisory-message-only OR classification-altering per §0.5 #4) + estimated implementation effort.
   - **§5 Tier-3 #6 advisory state-machine integration** — synthesis of how the recommended advisories should gate on maturity stage (new / maturing / mature / well-mature). Specific per-stage advisory matrix.
   - **§6 Operator decision points** — explicit list of operator-approval needs (which recommendations to commission for implementation; which to defer; which to drop).

---

## §1 Strategic context

This is an investigation, not implementation. The deliverable is operator-actionable analysis — operator decides which recommendations (if any) to commission for subsequent implementation.

**Schema state (binding):** Production DB at schema_version 16 post-3e.10 ship at HEAD `fa0a0ac`. No schema work in scope; investigation only.

**What's NOT in scope:**

- Any code change (recommendations land via separate dispatches)
- Any schema change
- Any V2.1 §VII.F source-of-truth correction submission (recommendations may surface candidates; submission is a separate operator action)
- Sell-side advisory implementation
- Trade-maturity state-machine implementation
- Buy-side criteria modification

**Operator urgency context:** DHC is approaching +1.5R / 20MA trail-MA decision territory. The investigation should produce decision guidance applicable to DHC's current state — not just abstract recommendations for the future. This urgency informs §3 prioritization (which gaps to surface first).

---

## §2 Worktree + binding conventions

### §2.1 Worktree
- **Branch:** `3e8-sell-side-advisories-investigation`
- **Worktree directory:** `.worktrees/3e8-sell-side-advisories-investigation/` at repo root.
- **BASELINE_SHA:** `fa0a0ac` (HEAD of `main` post-3e.10 housekeeping).

### §2.2 Marker-file workflow
- After worktree creation: `New-Item -ItemType File c:\Users\rwsmy\swing-trading\.copowers-subagent-active`
- After analysis doc lands + before invoking adversarial-critic: `Remove-Item c:\Users\rwsmy\swing-trading\.copowers-subagent-active`

### §2.3 Commits
- Conventional prefix:
  - `docs(investigation): Stage A — <description>` for Stage-A survey commit
  - `docs(investigation): Stage B — <description>` for Stage-B reconciliation commit
  - `docs(investigation): Stage C — <description>` for Stage-C recommendations commit
  - `docs(investigation): Stage D — <description>` for Stage-D Tier-3 #6 + operator-decision-points commit
  - `docs(investigation): assemble final analysis doc` for the integration commit
  - `fix(investigation): Codex RN Major #X (internal) — <description>` for Codex-driven fixes
- **NO Claude co-author footer**, **NO `--no-verify`**, **NO `--amend`**.
- **TDD does NOT apply** — investigation doesn't have a test surface. The Codex review is the quality gate.

### §2.4 Branch isolation + ownership
- Commits on branch only; no push to origin from worktree.
- **Implementer owns:** investigation reading + analysis-doc drafting → marker-file removal → adversarial-critic → return report.
- **Operator owns:** review of the analysis doc per §5 (the deliverable IS the gate).
- **Orchestrator owns:** integration merge to main + post-merge housekeeping.

### §2.5 Verify command
N/A — no runtime verification needed for an investigation doc.

---

## §3 Investigation tasks

### §3.1 Stage A — Current sell-side advisory surface enumeration

**Acceptance criteria:**

- (A.AC.1) §1 of analysis doc enumerates every sell-side / trim / take-profit advisory the framework emits today.
- (A.AC.2) For each advisory: (a) rule definition + trigger condition; (b) source code location (file:line); (c) UI surface (dashboard column / per-trade detail / pipeline-emitted briefing / etc.); (d) emission cadence (per-render / per-pipeline-run / per-trade-event).
- (A.AC.3) Includes the Phase 8 `action_taken` enum + Phase 6 cadence-review surfaces if applicable.
- (A.AC.4) Distinguishes ADVISORIES (framework-emitted suggestions to operator) from OPERATOR ACTIONS (post-fact captures of what operator did).

**Suggested commit:** `docs(investigation): Stage A — current sell-side advisory surface survey`

### §3.2 Stage B — Doctrine reconciliation

**Acceptance criteria:**

- (B.AC.1) §2 of analysis doc covers Minervini SEPA sell-side rules + DST take-profit rules + Qullamaggie sell-side commentary.
- (B.AC.2) For each known doctrine rule, classify framework-implementation state: `implemented` / `partially-implemented` / `not-implemented` / `[UNVERIFIED — physical-copy-only claim; flag for operator]`.
- (B.AC.3) Citation discipline per §0.5 #7 — every doctrine claim cites a source.
- (B.AC.4) Confluence vs divergence across the three doctrine sources flagged where present.

**Suggested commit:** `docs(investigation): Stage B — doctrine reconciliation against Minervini + DST + Qullamaggie`

### §3.3 Stage C — Identified gaps + Recommendations

**Acceptance criteria:**

- (C.AC.1) §3 of analysis doc — synthesis of §2 findings; gaps ordered by operational urgency (DHC's current trail-MA decision context informs prioritization).
- (C.AC.2) §4 of analysis doc — for each gap, specific proposed advisory rule:
  - Trigger condition (precise SQL-or-code-expressible)
  - Emission surface (which UI element)
  - Maturity-stage gating per Tier-3 #6 (new / maturing / mature / well-mature)
  - Classification: advisory-message-only OR classification-altering (per §0.5 #4)
  - Estimated implementation effort (hours)
  - V2.1 §VII.F routing if classification-altering

**Suggested commit:** `docs(investigation): Stage C — gaps + recommendations with maturity-stage gating`

### §3.4 Stage D — Tier-3 #6 integration + operator decision points

**Acceptance criteria:**

- (D.AC.1) §5 of analysis doc — synthesis of how recommended advisories gate on Tier-3 #6 maturity stages. Per-stage advisory matrix (which rules apply at which stage).
- (D.AC.2) §6 of analysis doc — explicit operator-decision list:
  - Which recommendations to commission for implementation (operator approves; goes to brainstorm/writing-plans cycle)
  - Which recommendations to defer (operator banks; not actioned)
  - Which recommendations to drop (operator rejects; closes investigation thread on that gap)
  - For each: a one-line "operator decision required" framing
- (D.AC.3) DHC-specific decision guidance for current trade state (the analysis should be operator-actionable for DHC right now, not just abstractly).

**Suggested commit:** `docs(investigation): Stage D — Tier-3 #6 advisory matrix + operator decision points`

### §3.5 Stage E — Final analysis doc assembly

**Acceptance criteria:**

- (E.AC.1) Final `docs/3e8-sell-side-advisories-investigation.md` document compiled with §1-§6 per §0.5 #8 structure.
- (E.AC.2) Doc length: ~600-1500 lines depending on doctrine + recommendation depth (proxy for thoroughness; not a hard target).
- (E.AC.3) All `[UNVERIFIED ...]` flags surface to operator-attention.
- (E.AC.4) Citations all anchor to source-file paths or Qullamaggie transcript IDs.

**Suggested commit:** `docs(investigation): Stage E — final analysis doc assembly`

---

## §4 Adversarial review (Codex)

### §4.1 Setup (IMPLEMENTER runs this — convention per orchestrator-context "Executing-plans dispatch convention" 2026-05-02)

After the analysis doc lands at branch HEAD:

1. `Remove-Item c:\Users\rwsmy\swing-trading\.copowers-subagent-active`
2. Invoke `copowers:adversarial-critic` with:
   - `PHASE`: `3e8-sell-side-advisories-investigation`
   - `SPEC_PATH`: `docs/3e8-sell-side-advisories-investigation-brief.md`
   - `PLAN_PATH`: `docs/3e8-sell-side-advisories-investigation.md` (the analysis doc itself)
   - `BASELINE_SHA`: `fa0a0ac`
3. Iterate until **NO_NEW_CRITICAL_MAJOR**.
4. Per-round fixes commit as `fix(investigation): Codex RN Major #X (internal) — <description>`.
5. Expected convergence: **2-3 rounds**.

### §4.2 Pre-empt list

Codex review value-add for an investigation doc concentrates on:

- **Citation correctness.** Each doctrine claim cites a source. Codex checks that the cited source actually exists at the cited path/line.
- **Misattribution.** Don't attribute Qullamaggie's framing to Minervini or vice versa. Each rule's authoritative source MUST be cited.
- **`[UNVERIFIED ...]` flag completeness.** Any Minervini-specific claim NOT in `reference/methodology/` MUST carry the flag. Codex catches missing flags.
- **Classification routing.** Each recommendation's classification (advisory-message-only OR classification-altering) MUST be explicit. Codex catches missing classifications.
- **Tier-3 #6 maturity-stage coverage.** Per-stage advisory matrix should cover all 4 stages (new / maturing / mature / well-mature) for each recommendation.
- **Operational relevance to DHC.** The investigation should produce decision-applicable guidance for DHC's current state, not just abstract framework recommendations. Codex catches over-abstract recommendations missing operator-applicable specificity.
- **Internal contradiction.** A recommendation in §4 should align with the gap in §3 it addresses.

---

## §5 Operator review surfaces

After NO_NEW_CRITICAL_MAJOR, the analysis doc is the deliverable for operator review:

- **Surface 1 — Read the analysis doc end-to-end.** Operator reads `docs/3e8-sell-side-advisories-investigation.md` start to finish.
- **Surface 2 — Triage `[UNVERIFIED ...]` flags.** Operator confirms / corrects any physical-copy-only claims that the implementer flagged.
- **Surface 3 — Decide on each recommendation.** Per §6 of the analysis doc, operator marks each recommendation as `commission` / `defer` / `drop`. Output is operator's decision list.
- **Surface 4 — DHC-specific decision.** Operator confirms whether the investigation provided actionable guidance for DHC's current trade state.
- **Surface 5 — Identify follow-up dispatches.** Operator identifies which `commission`-marked recommendations need brainstorm-cycle vs straight-to-implementation cycle.

No browser surfaces; no pytest verification (no test surface for investigation doc).

---

## §6 Return report shape

After operator review (or directly after NO_NEW_CRITICAL_MAJOR if operator review happens later), draft a return report with:

1. Final HEAD on branch
2. Commit count breakdown (Stage A-E impl / Codex-fix)
3. Codex round chain
4. Final analysis doc length (lines)
5. Number of `[UNVERIFIED ...]` flags surfaced
6. Number of recommendations + classification breakdown (advisory-message-only / classification-altering)
7. Number of operator-decision items surfaced in §6 of the analysis doc
8. Doctrine sources actually consulted (which `reference/methodology/` files; how many Qullamaggie transcripts queried; which CLAUDE.md memory items consulted)
9. Per-stage deviations from the brief
10. Codex Major findings ACCEPTED with rationale
11. Worktree teardown status

---

## §7 First-step paste-ready prompt for the implementer

```
You are taking over as implementer for the swing-trading 3e8-sell-side-advisories-investigation dispatch.

WORKING DIRECTORY: c:\Users\rwsmy\swing-trading\.worktrees\3e8-sell-side-advisories-investigation
BRANCH: 3e8-sell-side-advisories-investigation
BASELINE_SHA: fa0a0ac

Step 1 — Read the dispatch brief end-to-end:
  docs/3e8-sell-side-advisories-investigation-brief.md

It locks 8 design decisions (§0.5) that you do NOT re-litigate. Five investigation stages produce a single analysis document at docs/3e8-sell-side-advisories-investigation.md:
  - Stage A: current sell-side advisory surface survey
  - Stage B: doctrine reconciliation (Minervini + DST + Qullamaggie)
  - Stage C: gaps + recommendations with classification + maturity-stage gating
  - Stage D: Tier-3 #6 advisory matrix + operator decision points
  - Stage E: final analysis doc assembly

Step 2 — Read CLAUDE.md + docs/orchestrator-context.md (binding conventions; Tier-3 #6 framing).

Step 3 — Read reference materials:
  - reference/methodology/ — primary source-of-truth (READ END-TO-END)
  - reference/Future Work/2026-04-23-bifurcated-strategic-implementation-proposal-v2.1.md §VII.F
  - swing/trades/advisory.py — current advisory surface
  - swing/data/repos/daily_management.py + Phase 8 action_taken enum
  - swing/web/templates/partials/open_positions_row.html.j2

Step 4 — Verify worktree state:
  git rev-parse HEAD                  # expect fa0a0ac
  git status                          # expect clean

Step 5 — Use the qullamaggie MCP server (mcp__qullamaggie__*) to cross-check sell-side rules. Available tools: query_trading_rules, search_transcripts, get_setup_criteria, etc. Reference-only per CLAUDE.md memory.

Step 6 — Execute Stages A-E via superpowers:subagent-driven-development. Citation discipline per §0.5 #7 binding. Flag physical-copy-only claims as [UNVERIFIED ...].

Step 7 — After Stage E lands, run the adversarial review YOURSELF (per §4.1):
  - Remove-Item c:\Users\rwsmy\swing-trading\.copowers-subagent-active
  - Invoke copowers:adversarial-critic with PHASE=3e8-sell-side-advisories-investigation,
    SPEC_PATH=docs/3e8-sell-side-advisories-investigation-brief.md,
    PLAN_PATH=docs/3e8-sell-side-advisories-investigation.md,
    BASELINE_SHA=fa0a0ac
  - Iterate rounds + land Codex-fix commits until NO_NEW_CRITICAL_MAJOR.

Step 8 — Draft return report per §6 + signal orchestrator. Operator reviews the analysis doc per §5; orchestrator handles integration merge.

DO NOT:
  - Push to origin from inside the worktree
  - Merge to main (orchestrator action)
  - Use --amend or --no-verify
  - Add Claude co-author footer to commits
  - Skip the marker-file removal before invoking copowers
  - Make code changes (this is investigation-only; code changes route through separate dispatches)
  - Submit V2.1 §VII.F source-of-truth correction submissions (analysis surfaces candidates; submission is operator action)
  - Guess at Minervini-specific rules not in reference/methodology/ (flag as [UNVERIFIED ...])
```

---

## §8 Dispatch metadata

- **Brief author:** Orchestrator session 2026-05-10 (post-3e.10-ship).
- **Brief commit:** TBD.
- **Brief HEAD context:** `fa0a0ac` on main.
- **Worktree path (binding):** `.worktrees/3e8-sell-side-advisories-investigation/`.
- **Baseline test count:** 2183 fast (1 skipped).
- **Baseline ruff count:** 18 (E501 only).
- **Expected post-dispatch test count:** 2183 (unchanged — no code changes).
- **Expected post-dispatch ruff count:** 18 (unchanged — no code changes).
- **Expected analysis doc length:** ~600-1500 lines.
