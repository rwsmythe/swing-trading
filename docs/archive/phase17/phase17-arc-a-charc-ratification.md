# Phase 17 Arc 17-A — CHARC ratification of the `EvaluationBehaviorPolicy` 4th seam

**Status:** RATIFIED 2026-06-12 by CHARC (Director of Tool Development). Operator-relayed
(a ratification is an APPROVAL → operator-carried per the comms §2.5 taxonomy; the mailbox
carries information, not authority). This file is the **durable, auditable record** of the
ruling — the wording below is BINDING and is baked into the implementation plan
([`docs/superpowers/plans/2026-06-12-phase17-arc-a-single-eval-orchestration.md`](superpowers/plans/2026-06-12-phase17-arc-a-single-eval-orchestration.md))
by the writing-plans amendment that accompanies this commit.

**Context:** the writing-plans engineer surfaced (Codex R1 C4, correctly flagged not absorbed)
that the plan adds a 4th injection seam — `EvaluationBehaviorPolicy(spy_failure_mode /
dedup_error_rows / preserve_held_close)` — beyond the three §3-named seam categories
(universe-augmentation / output / conn-fetcher). The orchestrator routed it to CHARC as a
possible §3 departure per the commissioning brief's STOP-and-flag instruction.

---

## Ratification (CHARC, verbatim)

> The `EvaluationBehaviorPolicy` 4th seam is RATIFIED as within the 17-A brief's section-3
> shape: it is the section-4(b) mechanism (intentional difference = injected-seam parameter)
> materializing for the 4 newly-discovered divergences. Three binding conditions:
>
> **C1 — EXPLICIT CONSTRUCTION, NO DEFAULTS** (CORRECTS the orchestrator reconstruction, which
> had "defaults reproduce the pipeline path" — REJECTED). The policy dataclass declares EVERY
> field required, with NO default values; BOTH adapters construct the policy explicitly, stating
> every field at the call site. A defaulted field is a silent-inheritance channel — exactly the
> disease this arc exists to cure, reborn as configuration. (A test asserting the dataclass has
> no field defaults is cheap and binding.)
>
> **C2 — POST-RULING PRUNING.** After the Task-C checkpoint, the policy's final field set equals
> EXACTLY the operator-ruled-intentional set. UNIFY-ruled: the field is DELETED, both sides
> collapse to shared code, and the Phase-0 harness DIVERGENCE-n assertion is migrated to a parity
> assertion IN THE SAME TASK (adopting the orchestrator's sharpening). INTENTIONAL-ruled: the
> field stays, with a 1:1 discriminating test naming its ruling. The return report carries the
> complete field-to-ruling map. No silent unification, no silent preservation.
>
> **C3 — CONTAINMENT** (ADOPTING the orchestrator's reconstruction as an explicit third condition;
> it was implicit in the ratification rationale). `EvaluationBehaviorPolicy` stays a FLAT dataclass
> of scalar policy flags passed as ONE parameter to the single orchestration function; shared code
> branches ONLY on the policy value (adapters never special-case around it); no strategy/handler
> hierarchy, no registry, no new module beyond the sanctioned `orchestration.py`, no additional
> seam categories. Anything beyond a flat policy dataclass (new module, new seam category, schema,
> dependency) → STOP and route back to CHARC; the tripwire is not spent.
>
> **GOVERNANCE NOTE for the Stage-2 friction ledger:** a director cannot reply to the orchestrator
> on the bus (no orchestrator inbox in V1 — BY DESIGN for approvals, which must stay
> operator-carried; but it also forces verbal relay for pure-information replies). This exchange is
> evidence instance #1 for that gap. No build proposed — logged per the staging plan's evidence bar.

---

## Plan-compliance deltas (what the amendment changes)

| Condition | Pre-amendment plan state | Required change |
|---|---|---|
| **C1** | Canonical API declares `EvaluationBehaviorPolicy` WITH defaults (`spy_failure_mode="raise"`, `dedup_error_rows=True`, `preserve_held_close=True`); `orchestrate_evaluation(... behavior=EvaluationBehaviorPolicy())`; Task 1.1 Step-1 test asserts `EvaluationBehaviorPolicy()` defaults `== ("raise", True, True)`. | All three fields become REQUIRED (no defaults); `behavior` is a required keyword arg (no default instance); Task 1.1 test asserts the dataclass has NO field defaults (`all(f.default is MISSING and f.default_factory is MISSING for f in fields(...))`); the runner adapter (Task 1.3) constructs the policy stating every field explicitly (`EvaluationBehaviorPolicy(spy_failure_mode="raise", dedup_error_rows=True, preserve_held_close=True)`), never `EvaluationBehaviorPolicy()`. The CLI adapter (Task 2.2) already states all three explicitly — keep it so. |
| **C2** | Task-C protocol: unify → "unconditional shared code" (field RETAINED); no field-to-ruling map mandated. | Unify → the field is DELETED from the dataclass; the final field set == the intentional set; the DIVERGENCE-n assertion is migrated to a parity assertion in the SAME task; intentional → field stays + a 1:1 discriminating test names its ruling; the return report carries the complete field-to-ruling map. Edge case to encode: if EVERY divergence is ruled unify, the policy dataclass is empty and the seam is removed entirely. |
| **C3** | Architecture already flat-dataclass / one-param / branch-on-policy; STOP-and-flag in Phase-isolation conventions. | Bake the C3 wording verbatim into the Binding conventions; add "adapters never special-case around the policy value" explicitly. |
