# Proposal — orchestrator-spawned implementer sub-agents (dispatch-relay automation)

**Author:** orchestrator. **Routes to:** CHARC (architecture pass — this is a dispatch-topology / standing-process change, a §3 tripwire and harness-architecture which is CHARC-owned). **FYI:** RD (it touches the comms/authority topology RD is a peer in). **Decision:** operator ratifies after CHARC's pass. **Status:** proposal + design + open questions for the architecture seat — NOT adopted; the current operator-paste model stays until ratified.
**Origin:** operator-raised 2026-06-13 ("rather than me creating a new CC window… spawn an implementer sub-agent"); operator concurred with routing it to CHARC. (Cross-ref: the operator's `83baa4b1` already logged this as the first organic validation of the harness-architecture boundary — the orchestrator routing an exec-model decision UP to CHARC rather than self-adopting.)

## The change
Today: orchestrator drafts brief + paste-ready prompt → **operator hand-pastes it into a fresh CC window** → implementer executes → **operator relays the return report** → orchestrator QAs. Proposed: on the operator's dispatch "go," the **orchestrator spawns the implementer via the Agent tool** (with the model/effort it would otherwise recommend), the sub-agent's final message returns to the orchestrator as the tool result, and the orchestrator QAs it exactly as today.

**Motivation (operator's own observation):** the manual relay is a low-value pass-through — the operator rarely finds anything actionable in the prompt, and anything actionable is answered by the orchestrator or escalated anyway. The return report comes to the orchestrator regardless of who carries it. Automating the mechanical hop cuts operator overhead with little loss.

## What is PRESERVED (the load-bearing disciplines, unchanged)
- **Operator authorization:** the operator still commissions and still says "dispatch it" — that "go" *is* the authorization. The orchestrator spawns ONLY on that word, never self-initiates. The authority boundary (operator-mediated dispatch) holds.
- **Orchestrator QA-against-disk** of every return, **convergence verification** from the persisted real `.copowers-findings.md` transcript (not the sub-agent's claim), the **three-eye merge gate** (CHARC + RD diff QA), and the **no-false-green full-suite re-run on the merged head** — all unchanged.
- **Model/effort recommendation** (the just-banked convention): now *set* by the orchestrator on the Agent call rather than handed to the operator — but announced in chat and vetoable before spawn.
- **No comms-lock violation:** the implementer's return is *information* to the orchestrator (it already flows to the orchestrator, just via the operator today); it is NOT a post to a director inbox, and `decision_request` stays operator-only.

## Material risks / open questions for CHARC's pass
1. **The Codex-to-convergence gate (the central one).** Codex is reachable from a sub-agent via the raw `wsl.exe … codex …` Bash call. But: (a) the copowers *Skill* wrapper may be hook-blocked for sub-agents (`block-copowers-during-subagent.sh`), and (b) nested sub-agent spawning (`subagent-driven-development` spawns task-subagents) may not work two levels deep — so the implementer-subagent would likely **execute the plan inline (TDD) and hand-run Codex rounds via Bash**, losing the skill's round/marker/convergence structure. **Backstop:** the orchestrator verifies convergence by reading the persisted *real* transcript at QA, so a sub-agent that fudged "converged" is caught. **Question for CHARC:** is hand-run Codex (orchestrator-verified) acceptable, or must the copowers skill structure be preserved (which may force the implementer to remain a top-level instance)?
2. **Authority topology.** The implementer returns to the orchestrator, not the operator. Does routing the *return* directly to the orchestrator erode the information-vs-authority line, given operator authorization still gates the *dispatch*? (Orchestrator view: no — authority stays at the "go"; only the mechanical relay moves.)
3. **Visibility.** The operator loses the live-window view of work in flight. **Mitigant:** `run_in_background: true` lets the operator watch progress; the orchestrator summarizes on return.
4. **Worktree conventions.** The Agent tool's `isolation: worktree` creates its own temp worktree, which may not match our `.worktrees/<name>` + editable-install verify-command + cleanup-script coverage. **Recommendation:** do NOT use Agent isolation; instruct the sub-agent to create/use `.worktrees/<name>` per the existing convention.
5. **Context.** A sub-agent's transcript does NOT load into the orchestrator — only its final report does (same as reading the operator's relay today). Context-neutral-to-positive.
6. **Failure handling** (new orchestrator responsibility): sub-agent death on terminal API error (Agent returns null), WSL-Codex unreachable, or a stalled sub-agent. The operator-window model had the operator notice a stuck implementer; the sub-agent model makes detection/recovery the orchestrator's job.

## Reconciliation with in-flight comms work
This composes with CHARC's settled-but-deferred **Stage-2 orchestrator-inbox + session-registry** design (`56a01af2`) and the **transport-vs-tracker convention** (`01919b24`). The sub-agent return is a transport mechanism; the session-registry could track spawned implementer sub-agents. CHARC should reconcile this proposal with that design so they don't conflict.

## Proposed scope + staging
Applies to writing-plans, executing-plans, and non-Codex tasks (research/audits/grounding — these are the cleanest, no review gate). **Stage it:** non-Codex + writing-plans first; executing-plans once the Codex-gate handling is proven.

## Pilot
Run it on the **next dispatch (likely 18-B writing-plans)** in parallel-observable mode (`run_in_background` so the operator can watch), to de-risk the Codex-gate handling on one real arc before flipping to the standing default.

## Rollback
Trivial — revert to the operator-paste model at any time; no durable state change.

## Ask
CHARC architecture pass (verdict + conditions, esp. on open question #1 and the authority-topology #2). FYI RD. Operator ratifies. On ratification, the orchestrator banks it in `orchestrator-context.md` (§Paste-ready initial prompt / a new §Dispatch execution) + memory, and updates the model/effort convention to "orchestrator sets the knob on the Agent call, announced + vetoable."
