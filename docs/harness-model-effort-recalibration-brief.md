# Commissioning Brief — Harness model/effort recalibration (Fable 5 / Opus 5 / Sonnet 5)

**From:** CHARC → the Phase-21 orchestrator. **Authorized:** operator, in-session 2026-08-03.
**Source evidence:** the model-specific prompting guides at `platform.claude.com/docs/en/build-with-claude/prompt-engineering/` (`claude-prompting-best-practices` + the Fable-5 / Opus-5 / Sonnet-5 sub-pages), reviewed by CHARC 2026-08-03 against the harness on disk.
**§3 tripwire:** NOT crossed — docs + `.claude/agents` config only; zero `swing/` code, zero schema, no new dependency/process/carve-out. Self-certify in the commit.
**Review tier:** `review-fast` (docs/config; no production code) — codex-auto-review NOT required (§2.9 binds production arcs only).

---

## §0 The binding window — DO NOT land mid-arc

This rider executes **in the same window already reserved for the recipe tier repoint** (operator-ruled 2026-07-30, deferred until no implementer is mid-convergence): **after the 21-B merge, before the next dispatch.** Renaming tiers or shifting effort defaults under an in-flight implementer changes the invocation underneath it — the 21-D self-modification class. **Do both items in ONE pass**: the tier repoint and this recalibration touch the same file.

## §1 The allocation (operator-ruled)

| Tier | Model / effort | Grounding |
|---|---|---|
| **Directors** (CHARC, RD) | **Fable 5 / high** | Fable's documented strengths are the director job verbatim: navigating ambiguity, long-horizon autonomy, "manages ongoing communication with long-running subagents and peer agents." `high` is the documented default; `xhigh` reserved for capability-sensitive passes (phase-close audits) at the director's discretion. Already live for CHARC (operator set 2026-08-03). |
| **Orchestrator** | **Opus 5 / high**, with **two named xhigh escalations** | Docs: "coordinates teams of subagents well… writer-verifier patterns"; review "accuracy holds at lower effort." The old Opus-4.x-era `xhigh` default is retired — generation uplift covers it. **Escalate to xhigh for: (1) the merge-integration/composition step (the ONLY place the composition class is caught — harness-architecture §5.1), (2) phase-close QA.** |
| **Implementers** | **Opus 5 / Sonnet 5 by task** — existing five-cell library, aliases already resolve | Cells pin generic `model: opus` / `model: sonnet` (verified on disk 2026-08-03) — no re-pins needed. The selection model (by task, not phase) is unchanged. |

## §2 The work items

1. **`docs/implementer-dispatch-recipe.md`** — in the SAME pass as the tier repoint:
   - Orchestrator default line: Opus xhigh → **Opus 5 high + the two named xhigh escalations** (§1).
   - Effort-ladder recalibration note: **Sonnet 5 at `med` ≈ Sonnet 4.6 at `high`** (the docs' own cross-model mapping), so `implementer-sonnet-med`'s task ceiling shifts up a notch; do NOT add a sonnet-low cell (Sonnet 5 "respects effort strictly at the low end" — under-thinking risk on moderately complex tasks).
   - **Opus-5 dispatch-prompt hygiene (NEW, and the doc-backed part):** dispatch prompts must NOT carry legacy self-verification prods ("double-check your answer," "add a final verification step," "use a subagent to verify your own work") — Opus 5 self-verifies unprompted and these now cause OVER-verification at real token cost. **THE DISCRIMINATING RULE, stated in the recipe verbatim: an instruction is removable only if it compensates for a MODEL limitation; never if it encodes a PROJECT fact or a CROSS-AGENT evidence gate.** The merged-head suite run, the banner check, the trailer audit, QA-on-disk are evidence gates between agents — they stay, all of them.
2. **`.claude/agents/implementer-sonnet-med.md`** — description up-scoped one notch per the mapping (it now handles what sonnet-high used to); other four cells' descriptions verified still accurate, edited only if wrong.
3. **`docs/orchestrator-context.md`** (orchestrator's own content) — the default-effort line + a short Opus-5 note: subagent-damping guidance (delegate for genuinely independent sizeable tracks; no subagents to verify own work) and the verification-prod removal rule.
4. **Memory** — update `feedback_dispatch_model_effort_recommendation` to the new defaults (orchestrator posts the fact; the memory file is updated by whoever owns it at next touch).
5. **One-time grep, report-only:** briefs/bootstraps/recipe for reproduce-your-reasoning phrasing (Fable's `reasoning_extraction` refusal category). Adjudications/return reports are work product — fine. Report hits; do not mass-edit.
6. **CHARC-side (mine, not yours):** the director bootstraps gain Fable's anti-overplanning line; done by CHARC directly.

## §3 Sweep safety (D21 — binding)

Before committing: grep `tests/` + `swing/` + `scripts/` for every touched filename (`implementer-dispatch-recipe.md`, the cell filenames, `orchestrator-context.md`). Run the fast suite AFTER the change lands — a tracked-config edit is not suite-neutral by assumption. The green claim postdates the last commit of the pass.

## §4 Explicitly OUT of scope

- **The prescriptiveness audit** (Fable docs: "skills developed for prior models are often too prescriptive… consider removing") — **deferred to the Phase-21 close as its own item**, governed by the §2.1 discriminating rule, one artifact at a time, each trim observed under a live dispatch before the next. A bulk trim of instructions with forensic provenance is the D21 class applied to words.
- Any `swing/` code, any schema, the shadow engine, the review-tier RIGOR (run-to-convergence unchanged — tier the model/effort, never the rigor).
- RD's charter/bootstrap content — CHARC flags the Fable line to RD; RD writes his own.

## §5 Return

Orchestrator QAs, then posts the return report to CHARC. Confirm in it: which window the pass executed in (naming the 21-B merge SHA it followed), the tier repoint landed in the same pass, the suite number postdating the last commit, and the grep results from §2.5.
