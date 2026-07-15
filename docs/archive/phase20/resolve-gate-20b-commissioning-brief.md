# Commissioning Brief — 20-B: gate the general `discrepancy resolve` (D22)

**From:** CHARC. **To:** the Phase-20 orchestrator. **Arc:** 20-B ([`phase20-scope-charc.md`](phase20-scope-charc.md)). **Committed:** 2026-07-14. **No deadline pressure** (calm-cadence; sequenced after 20-A per the scope — 20-A is CLOSED, so clear to run).
**§3 verdict:** expected SUB-TRIPWIRE — the gate belongs at the CLI layer (`swing/cli.py:3632`, `discrepancy_resolve_cmd`); if the plan concludes a service-layer check inside `swing/trades/` is genuinely required, that is the carve-out lane already §3-passed for this phase's recon work — note it in the plan's self-cert rather than routing back. NO schema (v31).

## §0 References

- **Register D22** (charter §4) — the founding entry: `discrepancy resolve 73 --resolution acknowledged_immaterial` exits 0 on ANY `pending_ambiguity_resolution` row, bypassing the choice menu + the correction row (surfaced by the 19-F reproduction 2026-07-04).
- **Code:** `swing/cli.py:3632` `discrepancy_resolve_cmd` (the ungated general command) · `:2973` `discrepancy_resolve_ambiguity_cmd` (the tier-2 choice-menu flow + the 19-F FK-orphan short-circuit) · the cross-references between them at `:3009/:3042/:3131`.
- The D-22 ruling of record: **FK-orphan rows PASS ungated; a legitimate (subject-rows-exist) `pending_ambiguity_resolution` row REFUSES with an actionable message → the choice-menu flow, or an explicit `--force`** (with the reason recorded — the audit trail must say the gate was consciously overridden).
- Post-20-A context: ambiguous matches now DEMOTE to tier-2, so pending tier-2 rows occur MORE often — the gate's surface grows; this is why D22 rides this phase.

## §1 Requirements

1. **The gate:** `discrepancy_resolve_cmd` targeting a `pending_ambiguity_resolution` discrepancy whose subject row(s) EXIST refuses (exit non-zero, message naming the id + pointing to `resolve-ambiguity` and to `--force`). FK-orphans (the 19-F detection logic — REUSE it, do not fork a second orphan predicate) pass exactly as today.
2. **`--force`:** proceeds, and the resolution's audit surface (reason/notes) records the forced bypass — never a silent identical outcome.
3. **Non-pending rows:** byte-identical behavior to today (the gate touches ONLY the pending+subject-exists case).
4. Tests: pre/post arithmetic per case — orphan passes (unchanged) · legit-pending refuses (NEW) · legit-pending + `--force` proceeds with the recorded bypass · non-pending unchanged · the refusal message names the right escape hatches. Fixtures via raw production-shape INSERT (the 18-B.1 seeding discipline).

## §2 Gates

RD **light** plan-stage note (audit semantics of the forced-bypass record — one look, not a gate unless he objects); review-strong + codex-auto-review; suite + ruff + merged-head no-false-green; **operator CLI witness**: a live refusal on a seeded pending row + the `--force` path + an orphan pass-through. The ORCHESTRATOR posts the return to `charc,rd` after its QA.

## §3 Sizing + cells

Small. Writing-plans + executing both `implementer-opus-high` (or fold to a single executing dispatch if the orchestrator judges the design fully settled — its call within the standing disciplines).
