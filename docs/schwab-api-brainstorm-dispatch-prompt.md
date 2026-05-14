# Schwab API brainstorm — implementer dispatch prompt

This is the prompt the orchestrator sends to a fresh implementer agent (e.g.,
via the Agent tool with `subagent_type: "general-purpose"`, foreground, no
worktree) to commission the Schwab API integration brainstorm. The companion
dispatch brief lives at [docs/schwab-api-brainstorm-dispatch-brief.md](schwab-api-brainstorm-dispatch-brief.md);
this prompt frames the dispatch + points the implementer at it.

Operator-paced — operator dispatches when ready. The orchestrator does NOT
auto-dispatch.

---

## Prompt body (copy-paste-ready)

```
You are dispatched as the Schwab API integration brainstorm implementer for
the Swing Trading project. You have no prior conversation context. Your
working directory is c:\Users\rwsmy\swing-trading on Windows. The git branch
is `main` and HEAD is at c4252d3.

Your sole deliverable is a brainstorm spec at
docs/superpowers/specs/<YYYY-MM-DD>-schwab-api-design.md (where the date is
your brainstorm-completion date), landed as a single commit on main.

## Step 1 — Read the dispatch brief end-to-end FIRST

The dispatch brief at `docs/schwab-api-brainstorm-dispatch-brief.md` is the
canonical scope document for this brainstorm. It covers:

- §0 Read list (12 ordered sources to absorb before drafting)
- §1 Strategic context (BINDING orchestrator-distilled framing — source-
  ladder already shipped at Phase 9 Sub-bundle C; Phase 10 metrics consume
  transparently; Schwab Developer Portal access blocks live verification;
  OAuth complexity vs Finviz precedent; Trader API + Market Data API
  endpoint surface; operator-flagged yfinance ladder elective)
- §2 Brainstorm scope (auth, endpoints, pipeline integration, source-ladder
  write path, audit, schema posture, token redaction inheritance from
  Finviz, operator setup, 11 open questions)
- §3 OUT-OF-SCOPE explicit disclaimers (no schema-locking, no code, no
  automated order placement, market-data ladder conditional on §2.9 Q11)
- §4 Binding conventions (single commit, ~600-1100 lines, 3-6 Codex rounds)
- §5 21 adversarial-review watch items
- §6/§7/§8 done criteria + return-report format + stuck-recovery

Read it cover to cover. Treat it as the single source of truth for scope.
Do NOT skim. Do NOT invent scope it disclaims. Do NOT skip §1.1 (the
source-ladder-is-already-shipped framing) — that constraint changes what
the spec can re-design vs must inherit.

## Step 2 — Read the §0 sources the brief enumerates

The brief's §0 lists 12 reads in order. Honor that order. Skim CLAUDE.md
gotchas + Finviz precedent in detail; the rest you may scan if dense. The
key prior-art that must shape your spec:

- swing/integrations/finviz_api.py (~280 lines) + its 4 test files —
  the closest API-integration precedent. Mirror cassette discipline +
  token-redaction layering + signature-hash drift detection.
- swing/data/repos/account_equity_snapshots.py — read the
  _SOURCE_PRECEDENCE constant + get_latest_snapshot_on_or_before with
  with_provenance=True. The source-ladder you'd otherwise design is
  already shipped.
- swing/trades/account_equity_snapshots.py — record_snapshot(source=...)
  is the service the API write path calls.
- docs/superpowers/plans/2026-05-05-finviz-api-integration-plan.md (67k
  tokens; do not read whole — search for §A resolved-during-planning,
  §E endpoint reference, §G cassette runbook, §H algorithm spec; those
  patterns transfer to Schwab spec).
- docs/superpowers/specs/2026-05-06-phase9-risk-policy-reconciliation-design.md
  (~1090 lines) — closest spec-format precedent. Mirror the section
  structure: §A resolved items / §B file map / §C SQL deferred / §D
  open questions / §E endpoint / §F write-path / §G adversarial / §H
  verification.

## Step 3 — Skill posture (HARD CONSTRAINTS)

Invoke `copowers:brainstorming` via the Skill tool. That skill wraps
`superpowers:brainstorming` with adversarial Codex MCP review. Iterate to
NO_NEW_CRITICAL_MAJOR. Default MAX_ROUNDS=5; if a 6th round produces ≤1
new Major + 0 new Critical, you may accept-with-rationale + document.

DO NOT invoke `superpowers:writing-plans` — schema-locking + task
decomposition are out of brainstorm scope. The orchestrator dispatches
writing-plans separately AFTER your spec lands + operator triages your
open questions.

DO NOT invoke `superpowers:executing-plans`,
`superpowers:test-driven-development`, or
`superpowers:using-git-worktrees`. This is design-only on main; no code,
no tests, no worktree.

DO NOT invoke `superpowers:using-superpowers` again — you've already been
oriented to skills via your session-start system reminder.

## Step 4 — Operator-flagged dimension that MUST be a first-class open question

The operator surfaced at brainstorm-dispatch time that they want
`schwab_api > yfinance` market-data source-ladder considered as a real V1
candidate, not silently deferred. The brief threads this through §1.5,
§1.9, §2.9 Q11, §3, and §5 watch items 19-21. Treat Q11 as binding
operator-decidable scope input. The spec MUST present V1 INCLUDE and V1
EXCLUDE branches concretely, with consequences enumerated for each.

If you decide to draft for ONE branch (rather than dual-branch the spec),
pick the operator-recommended branch (V1 INCLUDE per §1.9) + flag the
unchosen branch's deferred design at §2.9 Q11. Do NOT silently lock
either way.

## Step 5 — Done criteria

1. Spec lives at docs/superpowers/specs/<YYYY-MM-DD>-schwab-api-design.md
   covering the brief's §2.1–§2.9.
2. ≥3 Codex rounds reaching NO_NEW_CRITICAL_MAJOR.
3. Spec section structure mirrors the Phase 9 brainstorm spec format;
   locked decisions vs open questions explicitly delimited.
4. Spec line count in the 600-1100 range. Tight beats padded; if you
   exceed 1100, re-scope by deferring more endpoint detail to writing-
   plans Task 0.b live verification.
5. Single commit landed on main: `docs(schwab-api): integration brainstorm spec`.
   No Claude co-author footer. No --no-verify. No amending.
6. Return report formatted per brief §7.

## Step 6 — Adversarial review watch items (highlights)

The brief §5 enumerates 21 watch items. The 6 most-leverage ones for
Codex's first-pass scrutiny:

- #1 Source-ladder is consumed not designed (re-design = FAIL).
- #2 Token redaction inherited verbatim from Finviz (silently re-inventing = FAIL).
- #3 OAuth refresh-token rotation handled (silent on rotation = FAIL).
- #6 Order placement explicit-disclaim (carelessly extensible architecture = FAIL).
- #11 Audit trail completeness (covers EVERY API call including auth = FAIL if not).
- #19 Market-data ladder coherence (V1 INCLUDE only — must mirror equity-snapshot precedent).

## Step 7 — If you get stuck

The brief §8 covers stuck-recovery. Key points:

- §1 strategic-context BEATS Schwab Developer Portal docs when they conflict.
- ACCEPT-with-rationale + flag in §2.9 open questions when Codex finds
  things requiring operator input. Do NOT stall waiting for orchestrator
  clarification — open questions are the right disposition.
- DO NOT propose schema SQL. DO NOT write Python code. If you start
  drafting `CREATE TABLE schwab_oauth_state (...)` or `class SchwabClient:`,
  STOP and re-read brief §3 OUT-OF-SCOPE.
- If Schwab API publicly-documented endpoint shapes contradict each other
  across community-maintained references, synthesize a working assumption
  + flag as §2.9 open question for operator-paired live verification at
  executing-plans Task 0.b. Mirror Finviz §A.1 precedent.

## Step 8 — Return shape

When done, produce a return report per brief §7. The orchestrator
consumes this for next-step decision (operator triage on open questions
+ writing-plans dispatch). Include the spec sha, line count, Codex round
summary, three highest-leverage decisions, auth + token storage decision
summary, pipeline integration decision summary, schema candidates
deferred to writing-plans, all 11 open questions with chosen-default-or-
deferred-disposition, inherited disciplines from Finviz precedent,
capture-needs feedback for downstream phases, and any deviations from
brief that warrant flagging.

Begin by reading docs/schwab-api-brainstorm-dispatch-brief.md end-to-end.
```

---

## Dispatch envelope notes (for orchestrator reference)

- **Subagent type:** `general-purpose`. Specialized agents (`Explore`, `Plan`,
  etc.) lack the tool surface needed (Skill, Bash for git commit, MCP for Codex).
- **Foreground vs background:** foreground (default). Brainstorm output dictates
  next-step decisions (operator open-question triage + writing-plans dispatch);
  parallelism gives little value here.
- **Worktree:** none. Single-commit design dispatch on main; no concurrent risk.
- **Model:** defer to harness default. Brainstorms benefit from strong reasoning;
  no need to pin Opus explicitly unless harness defaults differ.
- **Expected duration:** 90-180 minutes including 3-6 Codex rounds.
