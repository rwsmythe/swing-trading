# Harness Scaffold — writing-plans dispatch brief

**Authored:** 2026-06-16 by CHARC. **Phase:** copowers **writing-plans** — turn the converged design spec into the implementation plan. **Audience:** a fresh orchestrator → an implementer cell it dispatches. **This is harness-architecture work (CHARC-owned), dogfooded by the swing harness — NOT a swing application arc.**

## 1. The input (binding design)
`docs/superpowers/specs/2026-06-16-generic-harness-scaffold-design.md` (`94859ba1`) — the **adversarial-critic-converged** design spec (Codex R1 7-major + 5-minor resolved, R2 clean). It is binding; do not redesign. If a spec section is ambiguous against live code, STOP-and-ask (recipe §5).

## 2. The deliverable
`docs/superpowers/plans/2026-06-16-generic-harness-scaffold-plan.md` — a task-decomposed implementation plan (TDD-or-equivalent), each task carrying its files, the failing test / acceptance check, and the commit message. The plan describes building the scaffold in a **NEW authored clean-room repo** (spec Approach A). The plan lands in THIS (swing) repo's `docs/superpowers/plans/`; the actual scaffold is built in the new repo at the executing phase.

## 3. The dogfooding source — what to EXTRACT FROM (read these; the spec §3 split is the guide)
The generic core is extracted from swing's live artifacts; decide generic-vs-swing-specific per spec §3:
- comms: `scripts/role_mail.py`, `scripts/comms_ui.py`, `scripts/start_directors.ps1`, the `UserPromptSubmit` unread hook + `.claude/settings.json`;
- role protocols: `docs/orchestrator-context.md`, `docs/implementer-dispatch-recipe.md`, `docs/tool-director-context.md` (the CHARC charter), `scripts/director_bootstrap_charc.md`, `.claude/agents/implementer-*.md` (the cell shape);
- **the orchestrator inbox + session registry to BUILD:** `docs/comms-stage2-orchestrator-inbox-design.md` (swing's SETTLED-but-DEFERRED Stage-2 spec — the scaffold realizes it; this is the most substantial build piece).

## 4. Binding scope / locks (from the spec — preserve every one)
- **Approach A:** authored new repo, not fork-and-strip; **zero app/domain content** (no chess / COA / trading / finance — spec §10 + the §8 genericity guard).
- **The ~14-file manifest** (§4); the **four seams** (§3: application, domain cells, review/gate mechanism, launcher defaults — 1-3 interview-filled, 4 a tuned default).
- **Genericity guard (§8):** a grep-based build test with the banned-vocab / allowed-substrate-vocab / file-scope-exception lists — this is itself a planned, tested deliverable.
- **Orchestrator inbox + session registry (§5.1):** built from the Stage-2 design — the `session_id`-keyed liveness registry, the hook contract + degraded mode, the claim/addressing semantics (shared-inbox default), `launch_role.ps1` (role-parameterized, charc + orchestrator), the three hooks (UserPromptSubmit/SessionStart/SessionEnd).
- **Review/gate seam (§5.3):** the mechanism-agnostic contract + the **minimal default** (operable minute-one) + the optional `codex-reviewer.md` reference (§5.4).
- **The kernel + staged bootstrap (§5.5):** `charc-charter.md` + `charc-bootstrap.md` + the 5-step bootstrap checklist; the staged guarantee (CHARC-op on a bare clone; orchestrator+implementer after the orchestrator bring-up).
- **Zero hard runtime deps** (core stdlib; the UI is an optional `[web]` extra).

## 5. The new-repo logistics — the plan MUST address (and flag the operator decision)
Where the new repo lives + how it is created (an empty sibling repo the operator inits, vs. CHARC inits at executing). The plan states the assumption + flags any decision the operator must make BEFORE executing (e.g. the repo name + location). Do NOT create the repo in writing-plans (plan-only).

## 6. Review tier + cell
- **Writing-plans Codex review = `review-fast`** (plans/docs tier). **FLAG for executing:** building the scaffold is **`review-strong`** — it is harness "production" code (comms infra + the registry + the genericity-guard test).
- **Cell recommendation: `implementer-opus-xhigh`** (writing-plans / high-reasoning-density — the generic-extraction decomposition, the registry build-from-a-deferred-spec, and the seam contracts are judgment-dense).

## 7. Gate
Orchestrator QA of the plan against the spec + `review-fast` to convergence (`NO_NEW_CRITICAL_MAJOR`; persist every response) → **CHARC reviews the plan** (CHARC verifies the plan faithfully decomposes the spec, every seam/lock preserved, the genericity guard + the registry build planned correctly) → operator → executing-plans (a separate dispatch). The implementer reports to the orchestrator in chat; it does NOT post to any director mailbox (standing rule).
