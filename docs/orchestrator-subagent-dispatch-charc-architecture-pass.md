# CHARC architecture pass — orchestrator-spawned implementer sub-agents

**Date:** 2026-06-14. **Subject:** `docs/orchestrator-subagent-dispatch-automation-proposal.md` (orchestrator-authored). **Routed to CHARC** as a dispatch-topology / standing-process change (harness architecture, §2.8). **Decision:** operator ratifies; this is the engineering verdict + binding conditions, not the ratification. **FYI:** RD.
**Grounding:** proposal + the Agent-tool semantics + the recent comms/convention decisions read on disk. **Verdict: PASS with conditions, STAGED.**

---

## Verdict
The proposal is architecturally sound. It preserves every load-bearing discipline — operator authorization stays at the dispatch "go," orchestrator QA-against-disk, the three-eye merge gate, the no-false-green merged-head re-run, and the comms information-vs-authority taxonomy — and automates only the *mechanical* relay (paste-in / paste-back), which the operator correctly identifies as a low-value pass-through. PASS, conditioned and staged below.

## One pre-read of mine the proposal CORRECTED (banked honestly)
I had earlier flagged "orchestrator context growth" as a cost. The proposal is right and I was wrong: the **Agent tool returns only the sub-agent's final message** as the tool result — the sub-agent's full transcript stays isolated and does NOT load into the orchestrator's context. So the orchestrator receives exactly what it gets today (the return report), via the tool result instead of the operator's paste. **Context-neutral, not a cost.** Concern withdrawn.

## Answers to the two open questions
- **#1 — the Codex-to-convergence gate (the central one): hand-run Codex (orchestrator-verified) is ACCEPTABLE — I do NOT require the copowers skill structure be preserved — BUT staged (see C-a).** Forcing the implementer to remain a top-level instance solely to keep the skill wrapper would over-constrain; the skill's *value* is (a) the round/converge discipline and (b) the auditable persisted transcript, and both survive a hand-run loop IF the dispatch enforces them and the orchestrator independently verifies convergence from the *real* `.copowers-findings.md` at QA (C-c). The skill structure is preventive; the orchestrator's transcript-read is detective — for the lighter phases that backstop is sufficient; for executing it must be proven before the flip (C-a).
- **#2 — authority topology: NO erosion. Approved.** The implementer's return is *information* (a return_report-class artifact) that already flows to the orchestrator — the operator merely relays it today. Authority lives at the operator's dispatch "go" and the merge "go," both unchanged. The taxonomy distinguishes info (flows freely) from authority (operator-mediated); automating an info relay touches neither. (The separate *visibility* question is reserved to the operator, below — visibility ≠ authority.)

## Binding conditions (operator bakes these into the adopted procedure on ratification)
- **C-a — STAGE exactly as proposed; do not flip executing-plans until proven.** Non-Codex tasks (research/audits/grounding) + writing-plans first. Executing-plans converts to sub-agent dispatch ONLY after the hand-run-Codex handling is demonstrated to converge correctly on a real lighter-phase arc. Executing is the three-eye-gated production-code phase — it's the last place to absorb an unproven dispatch change.
- **C-b — NO Agent `isolation: worktree`.** It auto-creates a temp worktree that bypasses our `.worktrees/<name>` location, the editable-install verify command, the cleanup script, and the home-dir-leakage convention's coverage. The sub-agent is instructed to create/use `.worktrees/<name>` per the existing convention, exactly as a window implementer does.
- **C-c — Codex convergence is the orchestrator's HARD, transcript-verified gate.** For any sub-agent that runs Codex, the dispatch prompt explicitly enforces the round → persist-each-response → iterate-to-`NO_NEW_CRITICAL_MAJOR` discipline (since the skill scaffolding may be absent), and the orchestrator verifies convergence by reading the persisted REAL `.copowers-findings.md` at QA — never the sub-agent's "converged" claim. (This is the existing convergence-verification discipline; it becomes load-bearing here.)
- **C-d — failure handling is the orchestrator's documented responsibility.** The window model let the operator notice a stuck implementer; the sub-agent model makes detection + recovery the orchestrator's job: Agent-returns-`null` (sub-agent died on a terminal API error), WSL-Codex unreachable, and stall/no-return (needs a timeout, since `run_in_background` notifies on completion but not on a hang). The adopted procedure specifies detect → recover (re-dispatch) or escalate to the operator.
- **C-e — model/effort knob: orchestrator sets it on the Agent call, ANNOUNCED in chat + vetoable before spawn.** Honors the just-settled convention (orchestrator owns the implementer rec) while preserving the operator's cost-oversight veto. The announce-then-spawn handshake is required, not optional.

## Reserved to the operator (NOT my call)
**The visibility trade.** Today the operator sees the raw prompt and the raw return because they relay them; under sub-agents the operator sees the orchestrator's QA'd summary (and may watch a `run_in_background` stream, though in practice won't read it in full). The authority boundary holds regardless — this is purely how much live in-flight visibility the operator wants to keep. The operator's own motivation (the relay is low-value) suggests the trade is worth it, but it's the operator's to set.

## Reconciliation with the deferred Stage-2 comms work
No conflict. The sub-agent return (implementer → orchestrator via the Agent tool result) is a *different channel and different roles* than the Stage-2 orchestrator-inbox (other roles → orchestrator). The session-registry was designed to track concurrent orchestrator *sessions/windows*; a sub-agent is an in-session Agent invocation, not a separate window — so the sub-agent model actually *reduces* implementer-window-tracking needs and is orthogonal to the orchestrator-inbox/registry design. Both can proceed independently.

## Endorsement of the pilot
The proposed pilot — run the next dispatch (18-B writing-plans) in `run_in_background` observable mode — is the right first step: it's a writing-plans phase (the approved-now tier, no executing-gate risk) AND it lets the operator watch, de-risking both the Codex-gate handling and the visibility trade on one real arc before any standing flip. Endorsed. 18-B's CHARC commissioning pass (it's a tripwire arc) and this pilot can ride the same dispatch.

## On ratification
The orchestrator banks the adopted model in `orchestrator-context.md` (a new §Dispatch execution) + memory, and updates the model/effort convention per C-e. CHARC's conditions C-a..C-e are part of the adopted procedure; RD is FYI'd (the topology touches the comms taxonomy it's a peer in).
