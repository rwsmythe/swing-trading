# Phase 12.5 #1 — OQ-F Multi-Leg Tier-1 Auto-Redirect — Brainstorm Return Report

**Date:** 2026-05-17
**Dispatch:** Phase 12.5 #1 OQ-F multi-leg tier-1 auto-redirect brainstorm
**Brief:** `docs/phase12-5-bundle-1-oqf-multi-leg-auto-redirect-brainstorm-dispatch-brief.md` (`37b584d`)
**Spec deliverable:** `docs/superpowers/specs/2026-05-17-phase12-5-bundle-1-oqf-multi-leg-auto-redirect-design.md`
**Branch:** `phase12-5-bundle-1-oqf-brainstorm`
**Worktree:** `.worktrees/phase12-5-bundle-1-oqf-brainstorm/`

---

## §1 Final HEAD + commit breakdown

**Final HEAD on branch:** `0d5ec4b`

| Commit (SHA short) | Type | Description |
|---|---|---|
| `5878541` | brainstorm draft | Initial 918-line spec; 4 operator-locks honored; pre-Codex |
| `d5c4b5d` | R1 fixes | 5 Major + 2 Minor resolved in-tree (touched-files audit, n=1 reroute, sandbox SAVEPOINT pattern, service API shape, CLI filter in-bundle, glyph removal, §15 split) |
| `dae9981` | R2 fixes | 3 Major + 2 Minor resolved (COUNT(DISTINCT discrepancy_id), environment threading, Case A reachability reframe, candidate_choices stale kwarg removed, location refs corrected) |
| `2458d13` | R3 fixes | 2 Major + 2 Minor resolved (positional-conn signature ordering, hybrid-row invariant §7.3.1, COUNT(*) → COUNT(DISTINCT) wording, payload→operator_custom_payload) |
| `5674ff8` | R4 fixes | 2 Major + 2 Minor resolved (shared validator helper, InvalidOverrideComboError typed exception, exception-specificity ordering, banner-clears semantics LOCK) |
| `ccde1f8` | R5 fixes | 2 Major + 1 Minor resolved (choice_code binding in validator, post-SELECT ambiguity_kind check, pre-stamp validator call in pivot, test description update) |
| `0d5ec4b` | R6 fixes | 1 Major + 1 Minor resolved (terminal-state shape-aware idempotency guard, sandbox snippet ordering fix) |

**Commit count:** 7 spec commits = 1 initial + 6 Codex-fix.

**No Co-Authored-By footer drift** — verified across all 7 commits.

---

## §2 Codex round chain (R1–R7 convergent shape)

| Round | Critical | Major | Minor | Verdict | Outcome |
|---|---|---|---|---|---|
| R1 | 0 | 5 | 2 | ISSUES_FOUND | All resolved in `d5c4b5d` |
| R2 | 0 | 3 | 2 | ISSUES_FOUND | All resolved in `dae9981` |
| R3 | 0 | 2 | 2 | ISSUES_FOUND | All resolved in `2458d13` |
| R4 | 0 | 2 | 2 | ISSUES_FOUND | All resolved in `5674ff8` |
| R5 | 0 | 2 | 1 | ISSUES_FOUND | All resolved in `ccde1f8` |
| R6 | 0 | 1 | 1 | ISSUES_FOUND | All resolved in `0d5ec4b` |
| R7 | 0 | 0 | 0 | **NO_NEW_CRITICAL_MAJOR** | Chain sealed |

**Chain shape:** monotonic Major taper (5 → 3 → 2 → 2 → 2 → 1 → 0). Operator override past default MAX_ROUNDS=5 invoked at R5 → R6 → R7 (matches Phase 10 writing-plans precedent of 6-round override).

**Cumulative finding disposition:**
- **15 Major findings raised** across R1-R6 → **15 RESOLVED with code-content fixes**; **ZERO ACCEPT-WITH-RATIONALE banked**.
- **10 Minor findings raised** across R1-R6 → **10 RESOLVED with code-content fixes**.
- **0 Critical findings** entire chain.

**Comparison precedents** (per CLAUDE.md status line):
- Phase 12 Sub-bundle C.B: 5 rounds, 1C/6M/2m resolved, ZERO accept-with-rationale.
- Phase 12 Sub-bundle C.C: 3 rounds, 0C/4M/1m resolved, ZERO accept-with-rationale.
- Phase 12 Sub-bundle C.D: 4 rounds, 0C/6M/5m resolved, ZERO accept-with-rationale.
- Post-Phase-12 Sub-bundle 1: 5 rounds, NO_NEW_CRITICAL_MAJOR, ZERO accept-with-rationale.
- Post-Phase-12 Sub-bundle 2: 3 rounds, 0C/2M/1m resolved, ZERO accept-with-rationale.
- **Phase 12.5 #1 (this dispatch): 7 rounds, 0C/15M/10m resolved, ZERO accept-with-rationale.** Higher Major count than precedents reflects the parameterization-vs-current-code-shape audit Codex performed in R1-R5 (override kwarg threading + signature ordering + hybrid row shape invariants) — Codex caught real binding-contract drifts each round.

---

## §3 Spec line count

| Phase | Lines |
|---|---|
| Brainstorm draft (`5878541`) | 918 |
| After R1 fixes (`d5c4b5d`) | 999 |
| After R2 fixes (`dae9981`) | 1066 |
| After R3 fixes (`2458d13`) | 1089 |
| After R4 fixes (`5674ff8`) | 1161 |
| After R5 fixes (`ccde1f8`) | 1200 |
| After R6 fixes (`0d5ec4b`) | **1236** (final) |

Brief target: 600-1000 lines. **Spec ended above range** at 1236 — driven by R3 M2's new §7.3.1 hybrid-row invariant block + R4 M1's shared validator helper + R5 M1's choice_code binding + R6 M1's terminal-state shape-aware guard. Each round expanded the LOCKED safety surface. The over-target line count signals the architectural depth Codex surfaced past brief's initial estimates — accept as appropriate; writing-plans will consume the locked design rather than re-derive.

---

## §4 Pre-locked operator decisions verbatim verification

Per brief §1, 4 operator decisions were pre-locked. Spec §2 carries them verbatim as binding clauses §2.1-§2.4. Verification:

- **§2.1 (auto-redirect posture = ON)** — spec preserves verbatim; ZERO alternatives designed; rationale text matches brief §1.1 verbatim.
- **§2.2 (confidence threshold = all-match-within-tolerance)** — spec preserves verbatim; per-leg consistency check coded explicitly into predicate §4.3 sub-condition 6; single-outlier flip to tier-2 covered in §10 Case C.
- **§2.3 (reuse `apply_tier2_resolution(split_into_partials)` for handler shape)** — spec preserves verbatim; brief's "DO NOT design dedicated new handler" lock preserved through n=1 reclassification design (§6.5) — no new handler key needed.
- **§2.4 (banner advisory only; NO dedicated review page)** — spec preserves verbatim; NEW base-layout VM field + helper; `/metrics/auto-redirects` V2-banked at §14.

**ZERO operator-lock re-litigation** — Codex did NOT challenge any of the 4 locks; all chain findings were on implementation details that respected the locks.

---

## §5 Open Questions disposition (brief §3 → spec §15)

Brief §3 enumerated 10 open questions. Spec §15.A LOCKS 7 of them via Codex chain + 3 remain in §15.B as advisory operator-decision items at writing-plans handoff:

### §15.A LOCKED (Codex chain resolved)

1. **§6.5 n=1 single-order multi-leg path** — LOCKED via ambiguity_kind reclassification (R1 M2 fix).
2. **§8.6 `--resolved-by <value>` CLI filter** — LOCKED IN-BUNDLE at T-1.10 (R1 M5 fix).
3. **§7.6 sandbox short-circuit gating granularity** — LOCKED gated-on-auto-redirect with SAVEPOINT ROLLBACK pattern (R1 M3 fix).
4. **§7 service API parameter naming** — LOCKED to existing `operator_custom_payload` + NEW override kwargs (R1 M4 + R3 M1 + R3 M2 fix).
5. **§11.2 briefing.md format change** — LOCKED YES; counter renders only when > 0 (R2 M1 fix).
6. **§12.3 canary observability** — LOCKED YES; ~+5 LOC + 1 test.
7. **§13.3 Brief §2.4 amendment** — LOCKED + V2.1 §VII.F amendment banked (no `_RESOLVED_BY_VALUES` constant exists).

### §15.B Still open (operator may override at writing-plans handoff)

1. **§4.4 price_tolerance threshold cadence.** Brainstorm default: $0.01 absolute. Operator may shift to `max($0.01, abs(price) * 0.001)`.
2. **§6.3 qty_tolerance asymmetry.** Predicate uses 1e-9; `_handle_split_into_partials` uses 1e-6. Brainstorm default: LOCK predicate=1e-9 (stricter is safe).
3. **§6.4 defensive N cap.** Brainstorm default: NO cap V1.

---

## §6 Codex Major findings ACCEPTED with rationale

**ZERO ACCEPT-WITH-RATIONALE banked** across all 15 Major findings + 10 Minor findings. Every finding resolved with code-content fixes.

This matches the cleanest record set by Phase 12 Sub-bundle C.D (which also had ZERO accept-with-rationale across 6 Major + 5 Minor + 2 pre-Codex findings) and post-Phase-12 Sub-bundles 1 + 2 (both ZERO accept-with-rationale).

---

## §7 Cumulative V2 candidates banked

Spec §14 enumerates 12 V2 candidates:

1. **Banner predicate window — 7-day rolling.**
2. **Banner predicate window — persists-until-acknowledged.**
3. **Dedicated `/metrics/auto-redirects` review page** (operator §1.4 V2 candidate).
4. **Schwab cassette recording for multi-leg fill** (operator-paired; deferred until production multi-leg fill surfaces).
5. **Defensive cap on N legs.**
6. **`_RESOLVED_BY_VALUES` Python constant formalization.**
7. **Promote `auto_redirect_recipe` to typed dataclass.**
8. **Per-leg `mismarked_quantity` consumption.**
9. **Operator-acknowledged-clear surface** (`swing journal reconciliation acknowledge-redirects`).
10. **Predicate on `n=1` single-order multi-leg — LOCKED IN V1** (moved from V2 candidate to V1 LOCK per R1 M2 + §6.5).
11. **Audit trail surfacing in `show-correction` epilog.**
12. **Other tier-2 ambiguity_kinds auto-redirect candidates** (e.g., `multi_match_within_window` with single-execution-bearing record).

---

## §8 Forward-binding lessons for writing-plans phase

Spec §16 enumerates 7 lessons + §11.2 added an 8th (counter row-vs-logical semantics) at Codex R2:

1. **Recipe-field discipline** — new optional fields default to None; existing tests pass without modification; discriminating regression asserts recipe=None on pre-existing fixtures.
2. **Override parameter threading** — new kwargs default to current behavior; no regression on manual path WITHOUT supplying the new kwargs.
3. **Free-text vs CHECK-enum columns** — `grep -n CHECK` on migration SQL for every new string value.
4. **Cross-column CHECK invariants** — every transition through service-layer code MUST satisfy.
5. **Sandbox short-circuit ALWAYS in inner** — C.C lesson #2 carry-forward.
6. **Helper invocation completeness** — every `BaseLayoutVM` subclass + every retrofit VM populates the new field.
7. **ASCII-only banner text** — CLAUDE.md Windows cp1252 gotcha.
8. **Counter ROW-vs-LOGICAL semantics** — reconciliation_corrections has N+1 rows per `_handle_split_into_partials` logical correction; metrics aggregating "auto-correction count" MUST use `COUNT(DISTINCT discrepancy_id)`.

**Codex-chain-surfaced additional lessons (writing-plans MUST inherit):**

9. **Validate override combos BEFORE state mutation** — any service entry that accepts caller-supplied override kwargs MUST validate combo invariants at function entry, BEFORE the first DB write. (Codex R5 M2 LOCK.)
10. **Shape-aware terminal-state idempotency** — when an override kwarg implies a specific persisted-row shape, the idempotent-return path MUST verify the existing row matches that shape; otherwise raise. (Codex R6 M1 LOCK.)
11. **Exception specificity ordering in catch blocks** — when introducing a new typed exception that's a subclass of a generic catch-all (e.g., `ValueError`), the specific exception's catch MUST come FIRST and re-raise; the generic catch comes second and handles data-rejection. (Codex R4 M2 LOCK.)
12. **Positional-vs-keyword signature audit at brainstorm time** — verify the current shipped code's signature ordering BEFORE writing pseudocode; do NOT assume a tidy keyword-only signature when the shipped code carries a positional first arg. (Codex R3 M1 LOCK.)

---

## §9 CLAUDE.md status-line refresh draft text

```
**Phase 12.5 #1 brainstorm SHIPPED 2026-05-17** at `<integration-merge-sha>` (integration merge of `phase12-5-bundle-1-oqf-brainstorm` via `--no-ff`; 7 spec commits = 1 initial + 6 Codex-fix; **7 Codex rounds → NO_NEW_CRITICAL_MAJOR** convergent monotonic-Major-tapering (R1 0C/5M/2m → R2 0C/3M/2m → R3 0C/2M/2m → R4 0C/2M/2m → R5 0C/2M/1m → R6 0C/1M/1m → R7 0C/0M/0m; operator override past default MAX_ROUNDS=5 at R5→R6→R7 matching Phase 10 writing-plans precedent); **ZERO ACCEPT-WITH-RATIONALE banked** — all 15 Major + 10 Minor resolved with code-content fixes (matches Phase 12 Sub-bundle C.D + post-Phase-12 Sub-bundle 1/2 clean-record precedent); ZERO Co-Authored-By footer drift across 7 commits; 1236-line spec at `docs/superpowers/specs/2026-05-17-phase12-5-bundle-1-oqf-multi-leg-auto-redirect-design.md` (above 600-1000 brief target by 236 lines — driven by R3 M2 hybrid-row invariant + R4 M1 shared validator helper + R5 M1 choice_code binding + R6 M1 terminal-state shape-aware guard). Spec designs the V2 follow-up from post-Phase-12 mapper-widening spec §6.6 — multi-leg auto-redirect classifier widening + `apply_tier2_resolution` parameterization with `applied_by_override`/`correction_action_override`/`resolved_by_override` triple + new `_validate_override_combo` shared helper + `InvalidOverrideComboError` typed exception + `BaseLayoutVM.recent_multi_leg_auto_correction_count` banner field + CLI `--resolved-by <value>` filter. **Schema v19 UNCHANGED** (verified §13 audit — corrections + discrepancies CHECK enums already accommodate `auto_applied` + `auto` + new free-TEXT `resolved_by='auto_tier1_multi_leg'`; cross-column CHECK satisfied by natural transition path). **Single-sub-bundle ship recommended** (§9.1; ~+320 LOC across 11 tasks; ~+85 fast tests + 1 slow E2E; 3-5 Codex rounds projected for executing-plans). 12 V2 candidates banked + 3 still-open operator-decision items at §15.B (tolerance cadence; qty_tolerance asymmetry; defensive N cap). 12 forward-binding lessons for writing-plans (4 directly Codex-surfaced beyond §16's original 8). Writing-plans dispatch UNBLOCKED.
```

(Insert actual integration merge SHA when orchestrator merges the branch.)

---

## §10 Sub-bundle decomposition recommendation

**RECOMMENDATION: single sub-bundle ship.** Per spec §9.1.

- Scope: ~+320 LOC across 11 tasks (T-1.1 through T-1.11).
- Tests: ~+85 fast tests + 1 slow E2E test.
- Codex round projection for executing-plans: 3-5 rounds (matches Phase 12 Sub-sub-bundle C ship precedents).
- Operator-witnessed gate surfaces: 5 (S1 pytest+ruff; S2 synthetic predicate matrix; S3 production fetch; S4 banner UI; S5 CLI filter).
- ZERO schema changes (per §13 audit).

Internal A/B split would impose cross-bundle pin discipline without meaningful test-isolation benefit (no schema migrations needing landing-then-consumption split; no cross-VM retrofit requiring multi-bundle dependency chain). Skip the split.

---

## §11 Schema impact verdict

**SCHEMA v19 UNCHANGED.**

Verified §13.1 audit:
- `reconciliation_discrepancies.resolution` CHECK enum already includes `operator_resolved_ambiguity` (final state for auto-redirect path).
- `reconciliation_discrepancies.ambiguity_kind` CHECK enum already includes `multi_partial_vs_consolidated`.
- Cross-column CHECK satisfied (`operator_resolved_ambiguity` ↔ ambiguity_kind NOT NULL).
- `reconciliation_discrepancies.resolved_by` is free TEXT — new `'auto_tier1_multi_leg'` value requires NO migration.
- `reconciliation_corrections.applied_by` CHECK enum already includes `'auto'`.
- `reconciliation_corrections.correction_action` CHECK enum already includes `'auto_applied'`.
- `trade_events.event_type` CHECK enum already includes `'reconciliation_auto_correct'`.

**ZERO new schema modifications.** EXPECTED_SCHEMA_VERSION stays at 19.

**Brief §2.4 deviation banked as V2.1 §VII.F amendment candidate:** brief referenced extending `_RESOLVED_BY_VALUES` Python constant; no such constant exists in the codebase. `resolved_by` is free TEXT both at schema layer + Python passthrough.

---

## §12 Composition-surface verification

Spec §3 module touch list audited post-R1 M1 fix:

**Touched files** (LOCKED):
- `swing/trades/reconciliation_classifier.py` — ClassificationResult extension + predicate + recipe synthesis + n=1 reclassification.
- `swing/trades/reconciliation_auto_correct.py` — override kwarg parameterization + shared validator + sandbox short-circuit + typed exception.
- `swing/trades/schwab_reconciliation.py` — pivot-loop branching + Pass-2 candidate-dict emit-shape extension (Codex R1 M1 correction: this file IS touched; the prior brainstorm draft had incorrectly listed it as NOT touched).
- `swing/web/view_models/metrics/shared.py` — BaseLayoutVM field addition.
- `swing/web/view_models/*.py` — ≥13 retrofitted base-layout VMs.
- `swing/web/templates/base.html.j2` — banner block.
- `swing/cli.py` — `--resolved-by <value>` CLI filter (Codex R1 M5 in-bundle LOCK).
- New helper module for `_fetch_recent_multi_leg_auto_correction_count`.

**Surfaces NOT touched** (verified at §3 post-fix):
- `swing/integrations/schwab/mappers.py` — mapper UNCHANGED.
- `swing/integrations/schwab/models.py` — `SchwabExecutionLeg` + `SchwabOrderResponse` UNCHANGED.
- Within `swing/trades/schwab_reconciliation.py`: `_compute_execution_price` + `_resolve_match_quantity` + `_is_execution_bearing_candidate` + Path B sentinel emit UNCHANGED.
- `swing/web/routes/schwab.py` (`/schwab/status` + `/schwab/setup`) UNCHANGED.
- `swing/data/migrations/0019_*.sql` UNCHANGED.
- `swing/trades/reconciliation_ambiguity_choices.py` — operator menu UNCHANGED (menu still surfaces for tier-2 cases where predicate declines).

---

## §13 Worktree teardown status

**Branch:** `phase12-5-bundle-1-oqf-brainstorm` — 7 spec commits ahead of `origin/main`.

**On-disk worktree:** `.worktrees/phase12-5-bundle-1-oqf-brainstorm/`. Branch matches cleanup-script regex `phase\d+[-_]` so `cleanup-locked-scratch-dirs.ps1 -DeregisterFirst` will identify it post-merge.

**Marker file:** `.copowers-subagent-active` will be torn down with this return report commit.

**Post-merge action items** (orchestrator inheritance):
1. Operator-paired integration merge of `phase12-5-bundle-1-oqf-brainstorm` to `main` via `--no-ff`.
2. Update CLAUDE.md status-line per §9 draft text + insert actual merge SHA.
3. Worktree teardown via `cleanup-locked-scratch-dirs.ps1 -DeregisterFirst` (operator-driven).
4. Writing-plans dispatch brief draft for Phase 12.5 #1 — inherits spec § + the 12 forward-binding lessons (§8 above).

---

## §14 Codex-chain insight summary (return report supplement)

Beyond §2's tally, key Codex-surfaced insights worth capturing:

- **R1 M1** caught an internal contradiction the brainstorm-author missed: `schwab_reconciliation.py` was listed as UNCHANGED but the design REQUIRED touching it for both pivot-loop branching + Pass-2 emit-shape extension. Lesson: brainstorm-author cannot rely on CLAUDE.md status-line text for module-location facts (the text mentioned `_pivot_classify_and_dispatch_for_run` was in `reconciliation_auto_correct.py` — actual location via grep is `schwab_reconciliation.py:418`).
- **R3 M1** caught a positional-vs-keyword signature drift in pseudocode — brainstorm-author proposed a tidy keyword-only signature; shipped code has `conn` as positional first arg. Lesson: signature pseudocode MUST match current shipped ordering (grep + audit).
- **R3 M2 → R4 M1 → R5 M1 → R6 M1** is a 4-round cascade tightening the `_validate_override_combo` guard. Each round Codex found a NEW way the developer-bug guard could be bypassed: outer-only enforcement (R4 M1) → choice_code unbound (R5 M1) → terminal-state shape-blind (R6 M1). The final §7.3.1 + §7.3.1.a block carries 5-deep defensive layers; writing-plans inherits the discipline.
- **R4 M2** caught a real subtle bug: pivot's `except (ValidatorRejectedError, ValueError)` would absorb developer-bug `InvalidOverrideComboError` (subclass of `ValueError`) into silent manual-tier-2 stamp, hiding the bug from operator + delaying detection. Lesson: when introducing typed exceptions that subclass generic catch-all classes, the specific catch MUST come FIRST and re-raise.

These 4 insights compound into the forward-binding lessons §16 + §8 above.

---

*End of return report. Phase 12.5 #1 brainstorm CLOSES. Writing-plans dispatch UNBLOCKED.*
