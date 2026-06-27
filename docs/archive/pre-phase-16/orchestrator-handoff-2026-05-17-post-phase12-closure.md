# Orchestrator handoff — 2026-05-17 (post-Phase-12-closure; standalone post-Phase-12 brainstorm dispatch queued)

You are taking over as orchestrator for the Swing Trading project at the **post-Phase-12-closure** breakpoint. Phase 12 is fully shipped: Sub-bundle A (Schwab operational-pain mini-bundle; 2026-05-15) + Sub-bundle B (Schwab web-UI-friendliness; 2026-05-15) + Sub-bundle C (auto-correct reconciliation architectural pivot via 4 sub-sub-bundles A+B+C+D; closed 2026-05-17 at `bd1a62b`). No further Phase 12 sub-bundles queued. The next architectural dispatch is **standalone post-Phase-12 Schwab mapper execution-grain widening + T-B.7 follow-up + housekeeping micro-fixes** — scope operator-approved 2026-05-17; brainstorm dispatch pending your draft + operator commission.

The prior orchestrator is handing off NOW because:

1. **Phase 12 is at a CLEAN closure breakpoint.** All queued sub-bundles SHIPPED + housekeeping pushed + production state clean (7 discrepancies dispositioned at C.D operator-witnessed gate; CVGI fill 9 = $5.23; LION fill 15 = $12.70; Phase 10 banner count=0). 4 NEW C.D-arc lessons folded into `orchestrator-context.md` (operator pushback recovery + classifier soft-block per-invocation + inline-gate-fix durable pattern + Pass-1 limit-vs-fill defect family).
2. **Scope decision is BANKED for the next dispatch.** Operator concurred 2026-05-17 in plain chat: standalone bundled dispatch including (a) headline V2 mapper widening for `orderActivityCollection[].executionLegs[].price`; (b) classifier consumer updates lifting Pass-2-tier-1-FORBIDDEN; (c) reconciliation comparator at `swing/trades/schwab_reconciliation.py:693`; (d) backward-compat fall-through; (e) CLAUDE.md gotcha amendment marking Pass-2-tier-1-FORBIDDEN as V2-RESOLVED; (f) T-B.7 `/schwab/status` web counterpart from Sub-bundle B deferred; (g) 2 housekeeping micro-fixes (stale CVGI date attribution + historical audit row backfill-OR-leave-as-is operator-decision).
3. **Brainstorm dispatch is the NEXT deliverable.** No spec yet; brainstorm produces it. You draft the brainstorm dispatch brief + provide an inline implementer-dispatch prompt; operator commissions a fresh implementer.

## ⚠ Critical bootstrap framing

**claude-mem may still be DISABLED** for the operator's evaluation window (started 2026-05-10). You will NOT see SessionStart claude-mem injection blocks. Do NOT attempt `mcp__plugin_claude-mem_mcp-search__*`. Auto-memory dir (`~/.claude/projects/c--Users-rwsmy-swing-trading/memory/MEMORY.md` + linked files) IS still loaded.

**Chrome MCP is AVAILABLE** for browser-driven gates (not needed for brainstorm phase; relevant for post-brainstorm executing-plans dispatches if T-B.7 web work lands).

**Fast suite runs `-n auto` by default** at ~75-80s wall-clock post-Phase-12-C.D (~4363 fast tests on main HEAD).

**Operator dispatches implementers themselves** (per durable preference `feedback_orchestrator_vs_implementer_execution.md`). Orchestrator drafts the brief + provides inline dispatch prompt as fenced code block; operator dispatches when ready.

**Always provide an inline dispatch prompt** with every brief (per durable preference `feedback_always_provide_inline_dispatch_prompt.md`).

**Commit brief BEFORE inline dispatch prompt** (per durable lesson at `effb995` + auto-memory `feedback_commit_brief_before_inline_prompt.md`). Workflow: Write brief → `git add` + `git commit` SAME orchestrator turn → ONLY THEN provide inline prompt.

**Operator-paired gate driving — one command at a time** (operator's stated preference 2026-05-15). For brainstorm phase: N/A (brainstorm is implementer-side; orchestrator drafts + commissions). Relevant for the eventual executing-plans gate post-brainstorm.

**Explicit `Co-Authored-By` footer suppression in dispatch prompts** (NEW C.B forward-binding lesson #7; reinforced by C.C + C.D ZERO-drift outcomes — pattern is durable). The dispatch prompt MUST explicitly cite CLAUDE.md "No Claude co-author footer" convention with reference to the C.B R1 fix-bundle recurrence-prevention precedent.

**Pre-Codex orchestrator-side review discipline** (NEW C.C forward-binding lesson #6; reinforced by C.D's 2 absorbed Majors). For brainstorm phase: N/A (Codex runs on brainstorm output as part of `copowers:brainstorming` skill). Relevant for post-brainstorm executing-plans dispatches.

**Once operator-witnessed gate passes, integration merge is orchestrator action.** Do NOT ask "shall I proceed with merge."

## Step 1 — Read these in order

1. **This brief end-to-end** — captures Phase 12 closure + post-Phase-12 dispatch readiness + 4 NEW C.D-arc lessons inheritance.

2. **`CLAUDE.md` status line** — single-paragraph; updated through Phase 12 Sub-sub-bundle C.D SHIPPED at `bd1a62b` + housekeeping at `4bab6ee`. **Authoritative current-state summary.** Includes Pass-2-tier-1-FORBIDDEN gotcha amendment covering Pass-1 family + 2 NEW Gotchas section entries (Windows cp1252 stdout encoder family + synthetic-fixture-vs-production-emitter shape drift).

3. **`docs/phase3e-todo.md`** top entries in TOP-DOWN order:
   - **Phase 12 Sub-sub-bundle C.D SHIPPED entry** (just-shipped 2026-05-17 at `bd1a62b`; 10-surface operator-witnessed gate THE BIG ONE; 3 orchestrator-inline gate-fixes; 7 production discrepancies dispositioned; Sub-bundle C arc closer aggregate banked).
   - **Phase 12 Sub-sub-bundle C.C SHIPPED entry** (predecessor 2026-05-16 at `0b9d253`).
   - Earlier entries (C.B + C.A + Phase 12 A/B etc.).

4. **`docs/orchestrator-context.md`** — durable orchestrator-role conventions. Section "Lessons captured" updated 2026-05-17 with 4 NEW C.D-arc lessons:
   - Operator-architectural-pushback mid-gate triggers STOP-and-recover, not push-through.
   - Production-write classifier soft-block fires PER-INVOCATION even after AskUserQuestion authorization.
   - Orchestrator-inline gate-fix is a durable Phase-12-arc pattern (3 cumulative instances).
   - Pass-1 tier-1 entry_price_mismatch inherits limit-vs-fill defect from Pass-2-tier-1-FORBIDDEN family.
   - "Currently in-flight work" CURRENT STATE POINTER refreshed to 2026-05-17 + cap-drift note (active section ~48 entries vs ~30 cap; banked as maintenance-pass dispatch).

5. **`docs/phase12-bundle-C-D-return-report.md`** (`df71bf4` on the now-deleted branch; preserved on main post-merge) — implementer return report from C.D; §10 forward-binding lessons; §5 V2.1 §VII.F amendment candidates.

6. **`docs/phase12-bundle-C-D-tier2-cli-and-backfill-executing-plans-dispatch-brief.md`** (`047e3db`) — most recent dispatch brief; format precedent for the next dispatch.

## Step 2 — Standard bootstrap verification

```bash
git log --oneline -10                       # expect 4bab6ee at HEAD
git status                                  # expect clean (4 phase12-bundle-c-* worktree husks on disk; cleanup-script handles)
git worktree list                           # expect just main + on-disk husks (registration removed for the C.D one; A/B/C still registered pending cleanup-script -DeregisterFirst pass)
python -m pytest -m "not slow" -q | tail -5    # expect ~4363 fast pass + 3 pre-existing phase8 walkthrough failures + 5 skipped
ruff check swing/ --statistics | tail -3        # expect 18 E501
python -c "from swing.data.db import EXPECTED_SCHEMA_VERSION; print(EXPECTED_SCHEMA_VERSION)"   # expect 19
python -c "from swing.trades.reconciliation_backfill import run_backfill, BackfillSummary; print('C.D backfill OK')"
python -c "from swing.trades.reconciliation_ambiguity_choices import get_choice_menu; print('C.D menu OK')"
swing --help    # bare console entry (verifies editable install — operator recovered via pip install -e --force-reinstall on 2026-05-17 after install state broke)
```

Expected state on main HEAD `4bab6ee`:
- Phase 12 CLOSED. Sub-bundle C closed via 4 sub-sub-bundles A+B+C+D (cumulative ~88 commits / 14 Codex rounds / +494 fast tests / 1 ACCEPT-WITH-RATIONALE total).
- Schema v19 (unchanged since C.A 2026-05-15).
- 7 production discrepancies (39-45) all in terminal states; banner count=0.
- 4 phase12-bundle-c-* worktree husks pending operator's `cleanup-locked-scratch-dirs.ps1 -DeregisterFirst`.

## Step 3 — Post-Phase-12 dispatch scope (operator-approved 2026-05-17)

The next dispatch is a **standalone post-Phase-12 bundled dispatch**. Operator concurred with the prior orchestrator's recommended scope (8 items):

### Headline architectural items (must-have)

1. **Mapper widening** — extend `SchwabOrderResponse` dataclass at `swing/integrations/schwab/models.py` + mapper at `swing/integrations/schwab/mappers.py:223-230` to surface `orderActivityCollection[].executionLegs[].price` / quantity / datetime per execution leg. Current `order.price` field stays (still load-bearing for stop_mismatch trigger comparison + audit) + gains a sibling field for execution-grain data.
2. **Classifier consumer — lift Pass-2-tier-1-FORBIDDEN.** Update `_classify_unmatched_fill_shared` at `swing/trades/reconciliation_classifier.py` to allow tier-1 emission when Pass-2 execution-leg data resolves the journal-fill match.
3. **Reconciliation comparator — execution-grain at `swing/trades/schwab_reconciliation.py:693`.** Use execution-leg VWAP (or single-leg price if only one) for `entry_price_mismatch` / `close_price_mismatch` comparison instead of order-level limit.
4. **Backward-compat fall-through** — when `orderActivityCollection` is missing/empty (older orders, exotic types), explicit-branch to order-level fall-back OR tier-2 `unsupported` emit (operator-decision in brainstorm). Discriminating test for both paths.
5. **CLAUDE.md `Pass-2-tier-1-FORBIDDEN` gotcha amendment** — mark as RESOLVED-by-V2 + retain historical context for the V1 limit-vs-fill lessons.

### Bundled small item (cheap to include)

6. **T-B.7 `/schwab/status` web counterpart** — Sub-bundle B deferred. Web equivalent of `swing schwab status` CLI; HTMX form-driven status page mirroring `/schwab/setup` pattern. Touches the same Schwab integration module + uses the same VM scaffolding from Sub-bundle B.

### Housekeeping micro-fixes (fold in at no extra cost)

7. **Status-line stale CVGI date attribution** — fix 2026-04-27 → 2026-05-08 per operator's TOS-confirmed actual entry date (the 2026-04-27 was DHC's date; CVGI was 2026-05-08).
8. **Historical audit row backfill OR leave-as-is — operator-decision deferred to brainstorm.** The 3 CVGI/LION correction chains (ids 1+2+3+4+5+6) recorded the WRONG `schwab_said_value` field (the limit, not the actual execution). Recommend **leave-as-is** + document — the override-correction chain heads already record the correct operator-truth value; the wrong "Schwab said" intermediate row is forensically honest about what V1 saw.

### 6 OQs the brainstorm will need to resolve

A. **Backward-compat path when execution-leg data unavailable**: order-level fall-back vs tier-2 unsupported.
B. **Multi-leg journal-fill mapping**: VWAP comparator vs leg-by-leg audit surfacing; V2 candidate for tier-1 → `split_into_partials` auto-redirect.
C. **Tolerance window for execution-grain**: current `price_tolerance=0.01` rounds at cent precision; execution-leg prices are often 4dp.
D. **Stop-fill handling**: FIRED-stop path (vs WORKING-stop comparison currently sound) — same execution-grain extraction or defer?
E. **Schwab API field-shape verification**: confirm `orderActivityCollection[].executionLegs[].price` exists + reliably populated across LMT/MKT/STOP/STOP_LIMIT order types; may require cassette-recording (operator-paired session).
F. **Tier-1 confidence threshold**: with execution-grain data, when N Schwab orders cumulatively sum to journal qty + individual VWAPs align with journal price within tolerance, can classifier auto-emit tier-1 instead of tier-2 `multi_partial_vs_consolidated`?

## Step 4 — Drafting the brainstorm dispatch brief (your first major deliverable)

The brainstorm uses `copowers:brainstorming` skill (wraps `superpowers:brainstorming` with adversarial Codex review after spec drafted; 4-6 Codex rounds expected given the spec depth + 6 OQs). Output is a spec doc.

### What the brainstorm dispatch brief MUST include

Mirror `docs/phase12-bundle-C-C-auto-correction-service-and-flow-pivot-executing-plans-dispatch-brief.md` STRUCTURE but for a BRAINSTORM not executing-plans:

1. **§0 Inputs** — pointer to scope above (Step 3); link to CLAUDE.md gotchas for Pass-2-tier-1-FORBIDDEN + Windows cp1252 + synthetic-fixture-shape drift (all relevant context); link to `swing/integrations/schwab/mappers.py:223-230` + `swing/trades/schwab_reconciliation.py:693` + `swing/trades/reconciliation_classifier.py` as code anchors.
2. **§1 Scope LOCK** — 8-item bundle per Step 3 above; explicitly note housekeeping micro-fixes can be deferred to writing-plans phase if brainstorm scope concentrates on architectural items.
3. **§2 Open questions (6 OQs)** — per Step 3 list above; structure each as: question + tentative recommendation + binding-vs-deferrable disposition.
4. **§3 Empirical context** — CVGI + LION limit-vs-fill divergences (operator-witnessed at C.D gate 2026-05-17); 3 production correction chains preserve the V1 evidence; cite specific values ($5.30 limit vs $5.2244 fill; $12.75 limit vs $12.6999 fill).
5. **§4 Architectural invariants to preserve** — `stop_mismatch` apples-to-apples comparison (do NOT break); `correction_set_id` audit-trail discipline; reject-caller-held-tx contract at service layer; sandbox short-circuit at inner; idempotency contract; per-(ambiguity_kind, choice_code) handler dispatch (extending menu may be needed if V2 enables `multi_partial_vs_consolidated` tier-1 auto-redirect).
6. **§5 Out of scope (do NOT propose)** — schema changes (use existing `actual_value_json` envelope); new validators; new sub-classifiers (extending existing OK); web Tier-2 surface (already deferred to V2 separately); Schwab token encryption (V2-banked); multi-account picker (V2-banked).
7. **§6 Forward-binding lessons inherited** — 4 NEW C.D-arc lessons + earlier Sub-bundle C arc lessons all load-bearing.
8. **§7 Brainstorm dispatch metadata** — subagent_type `general-purpose`; `copowers:brainstorming` skill invocation; expected 4-6 Codex rounds; spec output path `docs/superpowers/specs/2026-05-17-schwab-mapper-execution-grain-widening-design.md`.

### Pre-empt the brainstorm-specific implementer gap class

Per the 3 cumulative orchestrator-inline gate-fix instances from Phase 12 arc:
- **Brainstorm MUST explicitly enumerate test fixture vs production emitter shape concerns** — the C.D `field_name='fill_match'` defect surfaced because tests planted `field_name='price'`. The brainstorm should require: for any NEW classifier/service test fixtures, the planted discrepancy uses production-shape values (real `discrepancy_type` + real `field_name` emitted by `schwab_reconciliation.py:454-689`).
- **Brainstorm MUST address Schwab cassette recording** — the Schwab cassette runbook is V2 PLANNED (per CLAUDE.md gotcha). If the brainstorm scopes V2 mapper widening, cassette recording becomes operator-paired session pre-req. Spec should enumerate which order types need cassette coverage.

## Step 5 — Operator preferences (durable; carry over)

- **Implementer-dispatch is the default** per `feedback_orchestrator_vs_implementer_execution.md`.
- **Once operator-witnessed gate passes, integration merge is orchestrator action.** Do NOT ask "shall I proceed with merge."
- **Worktree-isolated dispatch briefs MUST specify `.worktrees/<branch>/` path explicitly** (binding convention).
- **Implementer runs adversarial-critic via `copowers:executing-plans` wrapper** (for executing-plans phase post-brainstorm).
- **Multi-choice format for design questions** (AskUserQuestion preferred).
- **Spec is canonical over brief on cosmetic typos.**
- **Production-write classifier soft-block** — `reconcile-backfill --apply`, `override-correction`, `resolve-ambiguity` against production are all production-writes; operator pre-authorizes via plain-chat "yes" when classifier blocks (expect PER-INVOCATION blocks per NEW lesson).
- **Always provide an inline dispatch prompt** (per `feedback_always_provide_inline_dispatch_prompt.md`).
- **Commit brief BEFORE inline dispatch prompt** (per `feedback_commit_brief_before_inline_prompt.md` + orchestrator-context lesson at `effb995`).
- **Operator-paired gate driving — one command at a time.** For brainstorm phase: N/A. Relevant for post-brainstorm executing-plans gate.
- **Explicit `Co-Authored-By` footer suppression in dispatch prompts.**
- **Pre-Codex orchestrator-side review** for executing-plans dispatches (N/A for brainstorm; Codex auto-runs).

## Step 6 — When the brainstorm dispatch brief gets drafted

Threading reminders:

1. **Scope is OPERATOR-LOCKED at the 8-item bundle.** Do NOT re-litigate scope; the brainstorm refines WITHIN scope.
2. **6 OQs must be addressed in spec.** Each OQ gets a recommended-with-rationale answer + binding-vs-deferrable disposition.
3. **CVGI + LION empirical evidence is BINDING** — falsifies the operator-locked "order/limit ≈ execution" assumption.
4. **stop_mismatch architecture is sound — do NOT propose changes there.**
5. **Schema must remain v19** — V2 mapper widening fits in `actual_value_json` envelope OR adds a new dataclass field on `SchwabOrderResponse`; should NOT need new tables or column ALTERs.
6. **HTMX gotcha trinity for T-B.7 web surface** — HX-Request propagation; HX-Redirect-vs-303-swap; HX-Redirect-target-unrouted. All 3 inherited from Phase 5 + Phase 6 + Phase 12 Sub-bundle B.
7. **Inline-gate-fix pattern is RECOGNIZED PATH for brainstorm output** — brainstorm spec can document the pattern (Brainstorm §4 architectural invariants) so executing-plans dispatches inherit awareness.

## Step 7 — Pending operator-action items (NOT orchestrator-blocking)

- **4 phase12-bundle-c-* worktree husk cleanup** (A + B + C + D) — operator's `cleanup-locked-scratch-dirs.ps1 -DeregisterFirst` pass.
- **Schwab refresh-token renewal** — token from Sub-bundle B S5 issuance 2026-05-15T17:05:00+00:00 expires 2026-05-22T17:05:00+00:00. Operator re-auths via `/schwab/setup` web form OR `swing schwab setup` CLI before brainstorm executing-plans gate (~5 days remaining at handoff).
- **17 V2.1 §VII.F amendments cumulative across Sub-bundle C arc** — operator-paced batch processing.
- **Editable install fragility** — operator recovered on 2026-05-17 via `pip install -e ".[dev,web]" --force-reinstall --no-deps` after `swing.exe` console entry point crashed with `ModuleNotFoundError: No module named 'swing'`. Root cause likely Python 3.14 patch upgrade + editable shim staleness; banked as operator-environment-setup-fragility-not-code-defect.

## Step 8 — Quick reference summary

| Artifact | Path / commit |
|---|---|
| C.D dispatch brief (last prior brief) | `docs/phase12-bundle-C-D-tier2-cli-and-backfill-executing-plans-dispatch-brief.md` (`047e3db`) |
| C.D return report | `docs/phase12-bundle-C-D-return-report.md` (on main post-merge `bd1a62b`) |
| C.D integration merge | `bd1a62b` |
| C.D housekeeping (status line + 2 NEW gotchas + Pass-2-FORBIDDEN amendment) | `4bab6ee` |
| Post-Phase-12 brainstorm dispatch brief | TBD (your first deliverable) |
| Post-Phase-12 spec output target | `docs/superpowers/specs/2026-05-17-schwab-mapper-execution-grain-widening-design.md` (TBD) |
| Cross-phase backlog | `docs/phase3e-todo.md` (active; archive at `docs/phase3e-todo-archive.md`) |
| Orchestrator-role context | `docs/orchestrator-context.md` (updated 2026-05-17 with 4 NEW C.D-arc lessons) |
| Previous handoff brief | `docs/orchestrator-handoff-2026-05-16-post-phase12-bundle-C-C.md` (`e53cb59`) |

## Step 9 — Closing note from prior orchestrator

This handoff caps a focused 2-cycle session that drove the Phase 12 closure end-to-end:

1. **Sub-sub-bundle C.D triage + operator-witnessed gate** — 10-surface gate THE BIG ONE; production-write surfaces against operator's REAL DB; 3 orchestrator-inline gate-fixes for Windows cp1252 stdout encoder issues + synthetic-fixture-vs-production-emitter field_name shape drift; **operator architectural pushback surfaced the limit-vs-fill defect mid-gate** (S3a CVGI tier-1 wrote $5.30 when actual fill was $5.2244 per operator's TOS Net Price) → orchestrator STOPPED, queried operator TOS data, surfaced architectural finding (Pass-1 inherits limit-vs-fill defect from Pass-2-tier-1-FORBIDDEN family), recovered via tier-3 `override-correction` (3 correction chain heads at ids 3+4+6 restored fills to operator's TOS values). 7 production discrepancies dispositioned in clean terminal states; Phase 10 banner cleared to 0.
2. **Phase 12 closure + post-Phase-12 scope decision** — operator concurred with bundled scope (8 items) for next dispatch (mapper widening + classifier consumer + comparator + back-compat + gotcha amendment + T-B.7 follow-up + 2 housekeeping micro-fixes).
3. **Editable install recovery** — operator hit `ModuleNotFoundError: No module named 'swing'` post-gate when restarting `swing web`; root cause was editable-shim staleness post-Python-3.14-patch + package-source growth from Phase 12 arc; operator recovered via `pip install -e ".[dev,web]" --force-reinstall --no-deps`. Banked as environment-setup-fragility not-code-defect.

**Key story arcs of this session:**

1. **Operator architectural pushback is load-bearing — STOP-and-recover, not push-through.** The CVGI + LION limit-vs-fill divergences would have CORRUPTED operator's journal if the gate had proceeded without operator pushback. Mid-gate STOP + investigation + tier-3-override-back recovery is the architecturally-correct pattern. **NEW lesson #1 banked.**
2. **Production-write classifier soft-block fires PER-INVOCATION** even after AskUserQuestion authorization with explicit scope preview. Recovery is plain-chat operator "yes" per blocked-invocation. **NEW lesson #2 banked.**
3. **Inline-gate-fix is a durable Phase 12 arc pattern (3 cumulative instances).** Triviality threshold for inline-fix is well-defined; pattern saves a separate dispatch cycle. **NEW lesson #3 banked.**
4. **Pass-1 tier-1 entry_price_mismatch inherits limit-vs-fill defect family** — CLAUDE.md `Pass-2-tier-1-FORBIDDEN` gotcha AMENDED to cover Pass-1 family; V2 mapper widening priority BUMPED. **NEW lesson #4 banked.**

The next dispatch is the brainstorm for V2 mapper widening + Sub-bundle B follow-up + housekeeping micro-fixes (8-item bundle, operator-approved scope). Brief should be ~250-300 lines given the brainstorm scope is more bounded than C.D's executing-plans was. Adversarial review expected 4-6 Codex rounds. Schema unchanged (v19); package surface adds 1-2 fields on `SchwabOrderResponse` + new web route group for T-B.7.

**Operator preference reaffirmed via this session:** the pre-Codex orchestrator-side review discipline (saved 1-2 Codex rounds on C.C + 2 absorbed Majors on C.D) is now durable + applies to executing-plans dispatches. Brainstorm dispatch doesn't need it (Codex auto-runs).

Good luck.

---

*End of handoff brief. Post-Phase-12-closure orchestrator transition. Phase 12 CLOSED (A+B+C shipped; Sub-bundle C closed via 4 sub-sub-bundles). Standalone post-Phase-12 Schwab mapper execution-grain widening brainstorm dispatch UNBLOCKED — your first deliverable. Operator-paced.*
