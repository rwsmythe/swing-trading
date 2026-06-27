# Post-Phase-12 Schwab Mapper Execution-Grain Widening + T-B.7 + Housekeeping Brainstorm — Implementer Brief

**Audience:** Fresh Claude Code instance dispatched as the post-Phase-12 mapper-execution-grain-widening brainstorm implementer. No prior conversation context.

**Mission:** Produce a design spec for the standalone post-Phase-12 architectural bundle that closes out the V1 Schwab limit-vs-fill defect family + lands the Phase 12 Sub-bundle B deferred `/schwab/status` web counterpart + folds in two zero-cost housekeeping micro-fixes. The architectural headline is widening `swing/integrations/schwab/mappers.py` to surface `orderActivityCollection[].executionLegs[]` execution-grain data so the reconciliation classifier + comparator can operate on EXECUTION prices instead of LIMIT/STOP-TRIGGER prices — empirically falsified at the Phase 12 Sub-sub-bundle C.D operator-witnessed gate (2026-05-17) on real CVGI + LION trades.

**Brief:** `docs/post-phase12-schwab-mapper-execution-grain-widening-brainstorm-dispatch-brief.md` (this file).

**Sequencing:** Phase 12 CLOSED 2026-05-17 at `bd1a62b` (Sub-bundle C.D integration merge) + `4bab6ee` (post-merge housekeeping: status line + 2 NEW gotchas + Pass-2-tier-1-FORBIDDEN gotcha amendment covering Pass-1 family). 4 NEW C.D-arc orchestrator lessons + handoff at `4b392fc`. No further Phase 12 sub-bundles queued. This dispatch is **standalone post-Phase-12 work** — not a sub-bundle of any active phase; bundles the architectural V2 mapper widening (operator-locked next-architectural-dispatch slot per Phase 12 Sub-sub-bundle C.D OQ-4 + plan §I.1) with the Sub-bundle B T-B.7 deferred web counterpart and 2 cheap housekeeping items.

**Expected duration:** 150-300 minutes including 4-6 adversarial Codex rounds. Architectural design surface is bounded (1 mapper extension + 1 classifier consumer + 1 comparator + 1 web route group + 2 docs touches); 6 explicit open questions (§2.9) enumerated up-front with tentative recommendations + binding-vs-deferrable dispositions. Convergent chain shape per Phase 12 Sub-bundle C brainstorm 9-round precedent → expect 4-6 rounds.

---

## §0 Read first

In this order:

1. **`CLAUDE.md`** at repo root — project conventions + gotchas. Especially:
   - **Pass-2-tier-1-FORBIDDEN gotcha** AMENDED at `4bab6ee` to cover BOTH Pass-1 family (CVGI + LION 2026-05-17 falsification) AND Pass-2 family. This is the architectural-rationale anchor.
   - **2 NEW gotchas at `4bab6ee`**: Windows PowerShell cp1252 stdout encoder family + synthetic-fixture-vs-production-emitter shape drift (orchestrator-inline gate-fix #1 + #2 + #3 source).
   - 12 Schwab gotchas from Phase 11 Sub-bundle D T-D.4 (token redaction, sandbox short-circuit gating, source-artifact reference shape, schwabdev camelCase kwarg discipline, etc.).
   - 2 Phase 12 Sub-bundle B gotchas (Schwab OAuth web setup flow at `/schwab/setup` — Outcome B manual token exchange; CLIENT_ID + CLIENT_SECRET storage cfg-cascade).
   - HTMX gotcha trinity (HX-Request propagation + HX-Redirect-vs-303-swap + HX-Redirect-target-unrouted; T-B.7 web counterpart will inherit).
2. **`docs/orchestrator-context.md`** sections "Currently in-flight work" + "Recent decisions and framings" + "Lessons captured" — last section has the 4 NEW C.D-arc lessons banked at 2026-05-17:
   - **Lesson #1**: Operator-architectural-pushback mid-gate triggers STOP-and-recover, not push-through (CVGI + LION limit-vs-fill defect was caught mid-gate; this brainstorm exists BECAUSE of that pushback).
   - **Lesson #2**: Production-write classifier soft-block fires PER-INVOCATION even after AskUserQuestion authorization.
   - **Lesson #3**: Orchestrator-inline gate-fix is a durable Phase-12-arc pattern (3 cumulative instances during C.D).
   - **Lesson #4**: Pass-1 tier-1 entry_price_mismatch inherits limit-vs-fill defect from Pass-2-tier-1-FORBIDDEN family — V2 mapper widening priority BUMPED. **This brainstorm IS the V2 mapper widening response.**
   - Plus all 23 Schwab-arc forward-binding lessons (Phase 11 A 5 + B 7 + C 5 + D 0 + Phase 12 A 5 + B 12 = 34 → carry through Sub-bundle C arc adds ~12 more → ~46 cumulative).
3. **`docs/phase3e-todo.md`** top entries in TOP-DOWN order:
   - **Phase 12 Sub-sub-bundle C.D SHIPPED entry** (2026-05-17 at `bd1a62b`; **CRITICAL ARCHITECTURAL FINDING** section is the binding empirical evidence — read end-to-end).
   - **Phase 12 Sub-sub-bundle C.C SHIPPED entry** (2026-05-16; predecessor).
   - **Phase 12 Sub-bundle B SHIPPED entry** (2026-05-15; T-B.7 deferred candidate banked).
   - Sub-bundle C arc-closer aggregate (4 sub-sub-bundles A+B+C+D shipped 2026-05-15 → 2026-05-17).
4. **`docs/superpowers/specs/2026-05-15-phase12-bundle-C-auto-correct-reconciliation-design.md`** — Sub-bundle C spec (1444 lines; LOCKED at `d682c25`). Critical sections:
   - **§4.3 entry_price_mismatch / close_price_mismatch classification** — Shape A persisted-JSON-only vs Shape B full match-tuple predicate (LOCKED through 4-round Codex tightening sequence).
   - **§8.4 Pass-2-tier-1-FORBIDDEN LOCK** — the V1 ceiling this brainstorm proposes to LIFT for execution-grain data.
   - **§4.4 determinism principle** — when in doubt, classify as tier-2 (binding).
   - **§5 auto-correction service architecture** — `apply_tier1_correction` consumer the comparator feeds.
5. **`swing/integrations/schwab/mappers.py:175-242`** — `map_orders_to_fill_candidates(...)` is the V1 mapper. Lines 223-230 are the order-grain `price` field extraction (LIMIT or STOP-TRIGGER fall-back). This is what V2 widening extends.
6. **`swing/integrations/schwab/models.py:133-180`** — `SchwabOrderResponse` dataclass (8 fields; order-grain). This is what V2 widening adds sibling fields to.
7. **`swing/trades/schwab_reconciliation.py:660-720`** — the reconciliation comparator that emits `entry_price_mismatch` / `close_price_mismatch` / `unmatched_open_fill` / `unmatched_close_fill`. Line 693 is the `abs(so.price - float(f.price)) > price_tolerance` comparator. This is what V2 widening switches to execution-leg VWAP.
8. **`swing/trades/reconciliation_classifier.py:155-215`** — `_classify_unmatched_fill_shared` (tier-2-always under V1 per Pass-2-tier-1-FORBIDDEN LOCK at §8.4). This is what V2 widening may LIFT for execution-grain data.
9. **`reference/schwab-api/account-specification.md:1791-1800`** — Schwab API spec documents `orderActivityCollection[]` with `executionLegs[]` containing `legId` / `price` / `quantity` / `mismarkedQuantity` / `instrumentId` / `time` fields. This is the upstream contract the V2 mapper consumes. **Verify field-shape reliability across order types (LMT / MKT / STOP / STOP_LIMIT) is an explicit open question at §2.9 OQ-E** — may require cassette-recording in operator-paired session.
10. **Production empirical evidence (BINDING)** — production state as of `bd1a62b` post-gate cleanup 2026-05-17:
    - **CVGI fill_id=9** restored to `$5.23` (operator's TOS Net Price = $5.2244; journal recorded as $5.23 from memory at entry-time; Schwab LIMIT price = $5.30; correction chain at `reconciliation_corrections.correction_id=3+4` shows tier-1 wrong-correct → tier-3 override-back).
    - **LION fill_id=15** restored to `$12.70` (operator's TOS Net Price = $12.6999; journal recorded as $12.70 from memory; Schwab LIMIT price = $12.75; correction chain at `correction_id=5+6` shows tier-1 wrong-correct → tier-3 override-back).
    - **Spec MUST work each of these two cases end-to-end** as discriminating examples for the V2 mapper + classifier + comparator (mirrors Sub-bundle C brainstorm's CVGI 41 + DHC 39 + VSAT 40 discriminating-walkthrough precedent).

---

## §0 Skill posture

- Invoke **`copowers:brainstorming`** (which wraps `superpowers:brainstorming` with adversarial Codex review). Iterate to `NO_NEW_CRITICAL_MAJOR`.
- DO NOT invoke `superpowers:writing-plans` — schema sketches + module sketches are NOT plan tasks.
- DO NOT invoke `superpowers:executing-plans` — design-only.
- DO NOT invoke `superpowers:test-driven-development` — no code changes.
- DO NOT invoke `superpowers:using-git-worktrees` — no code changes; spec doc commit only.

---

## §1 Strategic context (ORCHESTRATOR-DISTILLED + OPERATOR-LOCKED — do NOT re-litigate)

### §1.1 Operator-locked architectural framing (DO NOT re-litigate)

1. **Execution price IS the truth for fill-grain reconciliation.** Schwab API exposes execution-grain data via `orderActivityCollection[].executionLegs[].price`. The V1 mapper currently reads ONLY the order-grain `order.price` (LIMIT or STOP-TRIGGER fall-back). Empirically falsified twice on 2026-05-17 at C.D gate (CVGI $5.30 limit vs $5.2244 fill = $0.0756 delta; LION $12.75 limit vs $12.6999 fill = $0.0501 delta). The architectural fix is the V2 mapper widening to surface execution-leg data.
2. **`stop_mismatch` architecture is SOUND — do NOT propose changes there.** The `_find_working_stop_for_ticker` path at `swing/trades/schwab_reconciliation.py` compares journal `current_stop` (operator-set trigger) vs Schwab `stopPrice` (operator-set trigger via WORKING-only orders); both sides are trigger thresholds, apples-to-apples. The defect is fill-grain ONLY.
3. **Backward-compat is a binding question — fall-back vs tier-2-unsupported is OQ-A** (§2.9). When `orderActivityCollection` is missing/empty (older orders, exotic order types, edge cases): brainstorm picks between order-level fall-back (preserves V1 behavior with documented caveat) and tier-2 `unsupported` emit (defers to operator with clear explanation). Discriminating tests required for both paths.
4. **Schema MUST stay at v19.** V2 mapper widening fits in existing `actual_value_json` envelope (per Phase 9 Sub-bundle B spec §3) OR adds a new dataclass field on `SchwabOrderResponse` — should NOT need new tables, column ALTERs, or migration v19→v20. If brainstorm surfaces a need for schema change, STOP + escalate to orchestrator BEFORE encoding in spec (C.A return report lesson #7 + 2026-05-15 lesson at `657b8a0`).
5. **Audit-trail integrity preserved.** Historical `reconciliation_corrections` rows recorded V1's WRONG `schwab_said_value` (the limit, not the execution). These chain heads at `correction_id=3+4+6` are FORENSIC RECORDS of what V1 saw — do NOT propose retroactive rewriting (OQ-G; operator's recommended disposition is "leave-as-is + document").
6. **Multi-leg VWAP vs leg-by-leg audit is OQ-B** (§2.9). Operator may have multi-leg fills (Schwab partial-fills consolidated into single journal entry). V1 brainstorm recommendation: classifier emits tier-1 with VWAP as `correction_target.price` when `len(executionLegs) >= 2` AND sum of `executionLegs[].quantity` == journal qty. V2 future-work candidate: tier-2 `multi_partial_vs_consolidated` auto-redirect to `split_into_partials` choice. Brainstorm picks V1 LOCK + flags V2 candidate.

### §1.2 Concrete current-state evidence (2 historical correction chains; classifier discriminating examples)

Production state at dispatch time (2026-05-17 post-`bd1a62b` cleanup):

- **CVGI correction chain (`reconciliation_corrections.correction_id=3,4`):** journal `fills.fill_id=9` operator-typed-from-memory at $5.23; Schwab LIMIT price = $5.30; V1 tier-1 auto-correct (per `apply_tier1_correction` at C.D gate S3a) wrote $5.30 → operator pushback "actual TOS Net Price is $5.2244" → tier-3 `override-correction` restored to $5.23 (chain head correction_id=4 records `operator_truth_value_json={"price": 5.23}`). **V2 expected behavior**: mapper surfaces `executionLegs[0].price = 5.2244`; comparator compares journal $5.23 vs Schwab execution $5.2244 with `price_tolerance=0.01` → `abs(5.23 - 5.2244) = 0.0056 < 0.01` → **NO discrepancy emitted** (sub-cent rounding; tolerable). Spec MUST walk this case end-to-end.
- **LION correction chain (`reconciliation_corrections.correction_id=5,6`):** journal `fills.fill_id=15` operator-typed-from-memory at $12.70; Schwab LIMIT price = $12.75; V1 tier-1 auto-correct wrote $12.75 → operator pushback "actual TOS Net Price is $12.6999" → tier-3 override-back to $12.70 (chain head correction_id=6). **V2 expected behavior**: mapper surfaces `executionLegs[0].price = 12.6999`; comparator compares journal $12.70 vs Schwab execution $12.6999 with `price_tolerance=0.01` → `abs(12.70 - 12.6999) = 0.0001 < 0.01` → **NO discrepancy emitted** (sub-cent rounding; tolerable). Spec MUST walk this case end-to-end.

**Tolerance window (OQ-C) is sensitive here**: with execution-grain data at 4dp precision, the V1 `price_tolerance=0.01` may still be appropriate (false-positives from sub-cent broker-side rounding are 99% of historical TOS observed deltas), OR brainstorm may recommend tightening to `0.001` to catch even sub-cent legitimate discrepancies. Brainstorm picks + locks.

### §1.3 Binding integrations

This bundle consumes shipped Phase 6 + Phase 7 + Phase 9 + Phase 11 + Phase 12 Sub-bundle A/B/C surfaces:

- **`SchwabOrderResponse` (Phase 11 Sub-bundle B):** 8-field dataclass at `swing/integrations/schwab/models.py:133-180`. V2 widening adds sibling field(s) for execution-grain data — likely an optional `executions: list[SchwabExecutionLeg] | None = None` field on the existing dataclass, OR a NEW companion dataclass. Brainstorm picks. Per spec §A.0 LOCK from Sub-bundle A: NO new schema; new fields/dataclasses are package-level, not DB-level.
- **`map_orders_to_fill_candidates` mapper (Phase 11 Sub-bundle B; lines 175-242):** V2 widening extends the function body to extract `executionLegs[]` from `raw["orderActivityCollection"][i]["executionLegs"]` (per Schwab API spec at `reference/schwab-api/account-specification.md:1791-1792` — field shape: `legId` / `price` / `quantity` / `mismarkedQuantity` / `instrumentId` / `time`). Defensive parsing required — array may be missing/empty/malformed.
- **`run_schwab_reconciliation` comparator (Phase 12 Sub-bundle C):** the comparator at line 693 (`abs(so.price - float(f.price)) > price_tolerance`) consumes `so.price` (order-grain). V2 widening switches to execution-grain VWAP — `so.executions[0].price` if single-leg OR `sum(leg.price * leg.quantity) / sum(leg.quantity)` if multi-leg.
- **`reconciliation_classifier.py:_classify_unmatched_fill_shared` (Phase 12 Sub-sub-bundle C.B):** currently tier-2-always per Pass-2-tier-1-FORBIDDEN LOCK at spec §8.4. V2 widening may LIFT this LOCK conditionally — when `executionLegs[]` data is present + classifier-confidence is high (OQ-F at §2.9; threshold for auto-redirect to tier-1 from tier-2 `multi_partial_vs_consolidated`).
- **Sub-bundle B web architecture (`swing/web/routes/schwab.py`):** `GET /schwab/setup` + `POST /schwab/setup` shipped 2026-05-15 with Outcome B manual token exchange. T-B.7 `/schwab/status` follows the same HTMX form-driven discipline (HX-Request propagation; HX-Redirect-vs-303-swap; HX-Redirect-target-unrouted gotcha trinity).
- **CLI `swing schwab status` (Phase 11 Sub-bundle D):** the web counterpart at T-B.7 mirrors the CLI's per-environment 3-state output (CONFIGURED / PROVISIONAL / NOT_CONFIGURED) + refresh-token TTL with severity escalation + recent-call audit summary. View-model + template work; no new logic.

### §1.4 Apply existing DROP rules

Inherits from prior phases — no new DROP rules unique to this bundle:

- **No magnitude-based threshold** (Sub-bundle C §1.1 lock #3).
- **No new schema** (Sub-bundle A §A.0 LOCK; Sub-bundle C arc preserved through B+C+D — V2 mapper widening MUST fit in existing envelope).
- **No re-litigating execution-vs-limit framing** (operator §1.1 lock #1).
- **No retroactive audit-row rewriting** (operator §1.1 lock #5; OQ-G recommended-disposition leave-as-is).
- **No Schwab API V2 features beyond mapper widening** — token encryption-at-rest, Option B HTTPS callback, per-env namespacing, multi-account picker, surface='web' CHECK enum widening, etc. — all banked in Sub-bundle B V2 list; not in scope.

### §1.5 Sub-bundle decomposition expectation

This is a STANDALONE bundle (NOT a phase sub-bundle). Brainstorm proposes a tentative decomposition for writing-plans to refine; writing-plans locks. Likely shape (3 sub-bundles):

- **Sub-bundle 1 — V2 mapper widening + classifier consumer + comparator + back-compat fall-through.** Headline architectural work (5 items in §3 of the operator-locked scope). New mapper fields; new classifier branch; new comparator path; discriminating tests for fall-back vs unsupported. Ships first.
- **Sub-bundle 2 — T-B.7 `/schwab/status` web counterpart.** GET route + view-model + template; HTMX form-driven; mirrors `/schwab/setup` pattern. Ships second (independent of Sub-bundle 1; can be parallelized if dispatched separately).
- **Sub-bundle 3 — Housekeeping micro-fixes.** Status-line CVGI date typo correction + CLAUDE.md `Pass-2-tier-1-FORBIDDEN` gotcha amendment marking V2-RESOLVED + historical audit-row leave-as-is documentation. Smallest; can be folded into Sub-bundle 1 ship or run as a single docs-only commit if writing-plans prefers. Ships last (or folded).

Brainstorm refines this decomposition — output goes into writing-plans as input.

### §1.6 Out-of-scope candidates (DO NOT design)

- **Future fill auto-population at trade-entry time** — per Sub-bundle C §1.6, separate sub-bundle worth scoping at brainstorm. NOT this dispatch's scope.
- **Tier-2 `multi_partial_vs_consolidated` auto-redirect to tier-1** — flagged at OQ-F as V2 candidate; brainstorm DECIDES whether to ship in this bundle OR defer. Recommendation: defer to a follow-up dispatch (the auto-redirect requires further analysis on confidence thresholds + may cascade to require new classifier dispatch states).
- **Web Tier-2 discrepancy-resolution surface** — Sub-bundle C spec §6.1 LOCK V1 CLI-only; web is V2 banked at Sub-bundle C plan §I.3. NOT this dispatch's scope.
- **schwabdev SDK version bump or token encryption-at-rest** — banked Sub-bundle B V2 candidates; NOT this dispatch's scope.

---

## §2 Brainstorm scope (in scope)

Produce a design spec at `docs/superpowers/specs/2026-05-17-schwab-mapper-execution-grain-widening-design.md` covering §2.1-§2.10.

### §2.1 — `SchwabOrderResponse` + mapper widening

For each addition proposed:

- **New dataclass(es) OR existing-dataclass extension** + fields (type + nullability + post-init validation) + relationship to `SchwabOrderResponse`.
- **Mapper changes** (`map_orders_to_fill_candidates`) extracting `orderActivityCollection[].executionLegs[]` per Schwab API spec at lines 1791-1792. Defensive parsing required (missing/empty/malformed array handling).
- **Backward-compat** — existing `SchwabOrderResponse.price` field stays (still load-bearing for stop_mismatch trigger comparison + audit + sandbox-environment fixtures); new field adds sibling execution-grain data.

Likely shape (brainstorm refines):

- NEW dataclass `SchwabExecutionLeg` (frozen) with fields `leg_id: int`, `price: float`, `quantity: float`, `mismarked_quantity: float | None`, `instrument_id: int | None`, `time: str` (ISO 8601). `__post_init__` validates `price > 0` AND `quantity > 0` AND `math.isfinite(price)` AND `math.isfinite(quantity)`.
- EXTEND `SchwabOrderResponse` with optional field `executions: list[SchwabExecutionLeg] | None = None` (None = legacy/unavailable; empty list = "Schwab returned no executions"; non-empty list = execution-grain data available).
- EXTEND `map_orders_to_fill_candidates` body to extract `orderActivityCollection[i]["executionLegs"]` for each order; build `SchwabExecutionLeg` instances; assign to `SchwabOrderResponse.executions`. Tolerate missing `orderActivityCollection` (LMT-only orders pre-fill / WORKING orders / etc.) by returning `executions=None`.

### §2.2 — Classifier consumer (lift Pass-2-tier-1-FORBIDDEN for execution-grain)

For `_classify_unmatched_fill_shared` (currently tier-2-always per V1 Pass-2-tier-1-FORBIDDEN LOCK):

- **Input contract:** classifier receives V1 inputs PLUS now-available `SchwabOrderResponse.executions` (when populated).
- **Output contract:** unchanged dataclass `ClassificationResult` — but tier-1 emission is now LEGAL when execution-grain data resolves the journal-fill match deterministically.
- **Discriminating examples (BINDING):** worked end-to-end for both CVGI + LION historical chains (§1.2):
  - CVGI execution-grain $5.2244 vs journal $5.23 → no discrepancy emit (within `price_tolerance`).
  - LION execution-grain $12.6999 vs journal $12.70 → no discrepancy emit (within `price_tolerance`).
- **Determinism principle preservation (spec §4.4):** when execution-grain data shape is uncertain (missing fields / multi-leg with `mismarkedQuantity` discrepancies / extreme outlier prices), classifier STAYS tier-2 with explanatory `ambiguity_kind`.
- **Pass-2-tier-1-FORBIDDEN amendment LOCK** (CLAUDE.md gotcha): mark V1 LIMIT-vs-EXECUTION defect family as V2-RESOLVED; retain historical context for the V1 limit-vs-fill lessons.

### §2.3 — Reconciliation comparator (execution-grain at `schwab_reconciliation.py:693`)

Switch comparator from `so.price` (order-grain) to execution-leg VWAP:

- **Single-leg:** `execution_price = so.executions[0].price` (if `so.executions` non-empty AND `len == 1`).
- **Multi-leg:** `execution_price = sum(leg.price * leg.quantity for leg in so.executions) / sum(leg.quantity for leg in so.executions)` (volume-weighted average price).
- **Fall-back path (OQ-A):** if `so.executions` is None/empty → branch to OQ-A disposition (order-level fall-back vs tier-2 `unsupported` emit).
- **Tolerance (OQ-C):** retains `price_tolerance=0.01` OR tightens to `0.001` per brainstorm decision.

### §2.4 — Backward-compat fall-through

When `orderActivityCollection` is missing/empty (older orders, exotic order types, sandbox responses, edge cases): brainstorm picks ONE of two paths:

- **Path A — Order-level fall-back (preserves V1 behavior):** comparator uses `so.price` (order-grain) when `so.executions is None`; classifier still emits tier-2 `unsupported` for `unmatched_open_fill`/`unmatched_close_fill` per Pass-2-tier-1-FORBIDDEN preserved partially (V1 LOCK preserved for non-execution-grain data). Discriminating test: plant a Schwab fixture with `orderActivityCollection=None`; assert comparator falls back; assert classifier emits per V1 rules.
- **Path B — Tier-2 `unsupported` emit (defer to operator):** comparator + classifier both treat absence of execution-grain data as "cannot deterministically resolve" → tier-2 with `ambiguity_kind='unsupported'` + explanatory `correction_reason`. Operator dispositions per real broker-statement consultation. Discriminating test: plant same fixture; assert emit shape.

Brainstorm picks + provides recommendation rationale.

### §2.5 — T-B.7 `/schwab/status` web counterpart (Sub-bundle B deferred follow-up)

Mirror `swing schwab status` CLI as web route:

- **`GET /schwab/status`** route in `swing/web/routes/schwab.py`. Path query-param `?environment=production` (default) or `?environment=sandbox`.
- **View-model** `SchwabStatusVM` in `swing/web/view_models/schwab.py` (NEW file OR extension of existing). Surfaces 3-state CONFIGURED/PROVISIONAL/NOT_CONFIGURED + refresh-token TTL with severity escalation (≤24hr WARN; ≤2hr ERROR per Sub-bundle D gotcha) + recent-call audit summary (last 5 `schwab_api_calls` rows).
- **Template** `swing/web/templates/schwab_status.html.j2` extending `base.html.j2` (will inherit Phase 10 Sub-bundle E T-E.3 base-layout VM banner — must populate `unresolved_material_discrepancies_count`).
- **HTMX discipline preserved:** no form POST in V1 (read-only surface); `/config?schwab_setup=ok` query-param consumer pattern from Sub-bundle B retargets to `/schwab/status` when this lands (Sub-bundle B `HX-Redirect: /config?schwab_setup=ok` becomes `HX-Redirect: /schwab/status`).
- **Nav-bar discoverability:** add link to `/schwab/status` from `/config` page's "External integrations" section (Sub-bundle B orchestrator-inline gate-fix `7b75d4a` precedent).
- **OQ-D applicability:** does the web status surface need to be aware of FIRED-stop handling differently from the CLI? Brainstorm picks (recommended: V1 read-only surface inherits CLI semantics 1:1).

### §2.6 — Housekeeping micro-fix 1: CLAUDE.md status-line CVGI date attribution

Fix typo: `2026-04-27` → `2026-05-08` per operator's TOS-confirmed actual CVGI entry date (the 2026-04-27 was DHC's entry date; CVGI was 2026-05-08). Brainstorm enumerates EXACT location(s) in the status line + proposed replacement text. Spec deliverable is the diff intent; writing-plans + executing-plans produces the actual edit.

### §2.7 — Housekeeping micro-fix 2: CLAUDE.md `Pass-2-tier-1-FORBIDDEN` gotcha amendment

Amend gotcha (currently AMENDED at `4bab6ee` to cover both Pass-1 + Pass-2 families) to mark V2-RESOLVED: brainstorm proposes the exact wording. Retain V1 historical context (CVGI + LION 2026-05-17 falsification evidence); add new top section "V2 RESOLVED:" referencing the V2 mapper widening dispatch + this spec for the architectural fix.

### §2.8 — Housekeeping micro-fix 3 (OQ-G): Historical audit-row leave-as-is documentation

The 3 historical correction chains (correction_ids 3+4 for CVGI + 5+6 for LION; plus correction_id=1+2 emitted during C.C T-C.11 testing) recorded V1's WRONG `schwab_said_value` (the limit, not the execution). Operator-recommendation: **leave-as-is + document**. Brainstorm produces:

- A docs/phase3e-todo.md entry explicitly noting the historical correction-chain forensic-honesty disposition.
- A short note in the spec's "V1 limitations historical record" section so future readers understand why correction_ids 3+4+5+6 have `schwab_said_value_json` containing limit-prices rather than execution-prices.
- NO retroactive UPDATE/DELETE proposed (operator §1.1 lock #5).

Alternative considered + rejected: backfill rewriting. Brainstorm enumerates rejection rationale.

### §2.9 — Open questions for orchestrator triage (6 OQs locked at handoff)

Per Phase 9/10/12 brainstorm pattern. Each OQ gets a recommended-with-rationale answer + binding-vs-deferrable disposition.

**OQ-A — Backward-compat fall-through path** (§2.4): order-level fall-back (preserves V1 behavior) vs tier-2 `unsupported` emit (defer to operator). **Brainstorm tentative recommendation: Path B (tier-2 `unsupported`)** — preserves determinism principle from spec §4.4 verbatim; falling back to order-level data introduces the SAME defect family the V2 widening exists to close. Discriminating tests required for both paths regardless. Binding.

**OQ-B — Multi-leg journal-fill mapping** (§2.3): VWAP comparator (single tier-1 with weighted-average price) vs leg-by-leg audit surfacing (emit one discrepancy per leg). **Brainstorm tentative recommendation: VWAP comparator for V1** — simpler; matches how operator's TOS Net Price column already aggregates multi-leg fills; leg-by-leg audit is V2 candidate that may auto-redirect tier-2 `multi_partial_vs_consolidated` → tier-1 `split_into_partials` (banked V2). Binding.

**OQ-C — Tolerance window for execution-grain** (§2.3): current `price_tolerance=0.01` (cent precision) vs tightened `0.001` (mil precision). **Brainstorm tentative recommendation: retain `0.01`** — execution-leg prices at 4dp are typical for Schwab; sub-cent broker-side rounding is 99%+ of historical TOS observed deltas (CVGI $0.0056 + LION $0.0001); tightening to `0.001` would surface false-positives from rounding noise. Binding.

**OQ-D — FIRED-stop handling** (§2.3, §2.5): when a stop order FILLS (status changes from WORKING → FILLED), the comparator currently consumes `stopPrice` via the V1 `order.price` fall-back at `mappers.py:225-227`. V2 widening preserves `stop_mismatch` trigger-vs-trigger comparison — but does the FIRED-stop's fill record need separate execution-grain extraction for `close_price_mismatch` evaluation? **Brainstorm tentative recommendation: yes, mirror entry-fill discipline** — when a FIRED stop fills, the fill record uses `executionLegs[].price` for actual execution price (not the stop trigger). Spec walks this through end-to-end. Binding.

**OQ-E — Schwab API field-shape verification** (§2.1): confirm `orderActivityCollection[].executionLegs[].price` exists + is reliably populated across LMT / MKT / STOP / STOP_LIMIT order types. **Brainstorm tentative recommendation: REQUIRE cassette-recording in operator-paired session before executing-plans dispatch** — Schwab API spec at `reference/schwab-api/account-specification.md:1791-1792` documents the field, but operator's actual order types in production are predominantly LIMIT BUY/SELL; coverage across MKT + STOP + STOP_LIMIT is unverified empirically. **Spec MUST enumerate which order types need cassette coverage at writing-plans time + flag the operator-paired cassette-recording session as a prerequisite to executing-plans dispatch.** Deferrable to writing-plans-phase (writing-plans triggers the cassette session).

**OQ-F — Tier-1 confidence threshold for tier-2 `multi_partial_vs_consolidated` auto-redirect** (§2.2): with execution-grain data, when N Schwab orders cumulatively sum to journal qty + individual VWAPs align with journal price within tolerance, can classifier auto-emit tier-1 instead of tier-2 `multi_partial_vs_consolidated`? **Brainstorm tentative recommendation: DEFER to V2 follow-up dispatch** — auto-redirect requires further analysis on confidence thresholds + may cascade to require new classifier dispatch states + the operator's current workflow handles tier-2 multi-partial-vs-consolidated via CLI menu (`split_into_partials` choice with operator-supplied `--custom-value`). V1 mapper widening LIFTS Pass-2-tier-1-FORBIDDEN for SINGLE-leg execution-grain data + matched-tuple cases only. Deferrable.

**OQ-G — Historical audit-row leave-as-is vs backfill** (§2.8): the 6 correction-chain rows (correction_ids 1-6) recorded V1's WRONG `schwab_said_value` (limit-price). **Brainstorm tentative recommendation: leave-as-is + document** — forensic-honesty preserved; tier-3 `operator_overridden` chain heads (correction_ids 4+6) already record correct operator-truth values; the wrong intermediate "Schwab said" rows are honest about what V1 emitted. Alternative considered: UPDATE the `schwab_said_value_json` to retroactively reflect execution-grain data — rejected because (a) violates operator §1.1 lock #5; (b) requires re-fetching historical Schwab orders within refresh-token-TTL constraints; (c) executing-plans Codex would catch as a deferred-truth-rewrite violation. Binding (operator-decided).

### §2.10 — Sub-bundle decomposition recommendation

Brainstorm proposes a tentative decomposition (per §1.5) for writing-plans to refine. Likely shape: 3 sub-bundles (mapper-comparator-classifier + T-B.7 web + housekeeping). Brainstorm specifies dispatch ordering + cross-sub-bundle dependencies + projected test deltas + projected line counts.

---

## §3 OUT OF SCOPE (do not do)

- **Migration SQL drafting** — that's writing-plans territory. Schema MUST stay at v19 (§1.1 lock #4); no schema sketches required because no schema changes.
- **Code drafting** — service modules, view-models, mapper bodies, classifier branches, route handlers, repo functions, CLI command bodies, template Jinja.
- **Sub-bundle task-decomposition into per-task acceptance criteria** — writing-plans output. Sub-bundle high-level scope is in §2.10 brainstorm-output; per-task decomposition is downstream.
- **Re-litigating §1 binding constraints** — accepted as given. Operator-locked. If a Codex round produces a finding that contradicts §1.1, flag as open question, do NOT relax §1.1.
- **Fill auto-population at trade-entry time** (§1.6) — separate sub-bundle. NOT this dispatch's scope.
- **Web Tier-2 discrepancy-resolution surface** — Sub-bundle C plan §I.3 V2 candidate; NOT this dispatch's scope.
- **schwabdev SDK upgrade or token encryption-at-rest** — Sub-bundle B V2 candidates; NOT this dispatch's scope.
- **Retroactive `reconciliation_corrections` rewriting** — OQ-G recommended-disposition leave-as-is; NOT this dispatch's scope.
- **Sub-bundle C deferred V2 candidates (D1-D7)** — pivot helper relocation; sentinel rule wording; SAVEPOINT-uniqueness test mechanic; inline SQL vs repo helpers; T-C.11 scope; view_models.py touch — all banked at C.C return report §5; NOT this dispatch's scope.
- **Multi-leg tier-1 auto-redirect to `split_into_partials`** (OQ-F deferred) — V2 follow-up dispatch candidate; NOT this dispatch's scope.
- **Re-deriving Phase 9 + Phase 10 + Phase 11 + Phase 12 A/B/C arc forward-binding lessons** — accept as given (~46 cumulative lessons; binding inheritance).

---

## §4 Binding conventions

- **Branch:** `main`. Single commit OR landing+fixes split per Phase 9/10/12 brainstorm precedent if Codex finds substantive issues.
- **Commit message:** `docs(post-phase12): Schwab mapper execution-grain widening + T-B.7 + housekeeping brainstorm spec`. **No Claude co-author footer** (per CLAUDE.md binding convention + NEW C.B forward-binding lesson #7 — explicit suppression citation; passive CLAUDE.md inheritance is insufficient because subagents have isolated context). No `--no-verify`. No amending.
- **Spec format:** mirror `docs/superpowers/specs/2026-05-15-phase12-bundle-C-auto-correct-reconciliation-design.md`. Section-numbered; locked decisions called out explicitly with rationale; open questions enumerated for orchestrator triage with tentative recommendations.
- **Spec line target:** ~600-1000 lines (smaller than Phase 12 Sub-bundle C's 1444 because the architectural surface is more bounded: 1 mapper extension + 1 classifier consumer + 1 comparator + 1 web route + 2-3 docs touches vs Sub-bundle C's full architectural pivot with 4 sub-sub-bundles).
- **Adversarial review:** mandatory; iterate to `NO_NEW_CRITICAL_MAJOR`. Budget 4-6 rounds (convergent chain expected per Phase 9/10/12 brainstorm lesson family).
- **Schema sketches:** zero — no schema changes proposed.

---

## §5 Adversarial review watch items

For Codex rounds — pass these as targeted prompts to `copowers:adversarial-critic`:

1. **§1.1 operator-locked constraints integrity.** Spec respects all 6 operator locks (execution price is truth; stop_mismatch sound; back-compat is binding question; schema stays v19; audit-trail preserved; multi-leg VWAP is OQ-B). If any spec recommendation appears to weaken these, flag for orchestrator — do NOT relax in spec.
2. **§1.2 discriminating examples worked end-to-end.** CVGI fill_id=9 + LION fill_id=15 each walked through proposed V2 mapper + classifier + comparator with input payload + expected output + assertion. Coverage check: does V2 design avoid emitting false-positive discrepancies for these historical chains?
3. **Determinism principle preservation** (Sub-bundle C spec §4.4). When in doubt, classify as tier-2 (NOT tier-1). Audit §2.2 classifier branches for false-positive-tier-1 risk under multi-leg + sandbox + missing-orderActivityCollection edge cases.
4. **OQ-A backward-compat fall-through coverage.** Both paths (order-level fall-back + tier-2 `unsupported`) have discriminating tests enumerated regardless of brainstorm's recommended-path pick. Spec MUST cover both — the deferred decision should still ship test coverage so writing-plans can lock the path with binding tests.
5. **OQ-B multi-leg VWAP correctness.** Worked example: 2-leg fill with `leg[0].price=$10.00`, `leg[0].quantity=50`, `leg[1].price=$10.20`, `leg[1].quantity=50` → VWAP = $10.10. Discriminating test: assert classifier compares journal `price=$10.10` vs VWAP `$10.10` → no discrepancy emit; journal `price=$10.00` (operator-typed as first-leg price ignoring split) → tier-1 discrepancy with `correction_target.price=$10.10`.
6. **OQ-C tolerance window sensitivity audit.** With `price_tolerance=0.01`, what's the smallest deltable execution-vs-journal divergence that triggers? Audit historical TOS observed deltas (CVGI $0.0056 + LION $0.0001 sub-cent rounding; legitimate broker-side divergences = ??? from operator's archived broker statements if available). Spec MUST anchor the tolerance pick to empirical evidence.
7. **OQ-D FIRED-stop discipline** (§2.3, §2.5). Stop orders that FILL transition WORKING → FILLED with `orderActivityCollection` populated. Comparator MUST use execution-grain for `close_price_mismatch` on FIRED stops; trigger-price for WORKING-stop `stop_mismatch` (unchanged). Discriminating test plants Schwab FIRED-stop fixture + asserts close_price_mismatch comparator uses execution-leg path.
8. **OQ-E cassette-recording prerequisite** (§2.1). Spec enumerates which order types need cassette coverage at writing-plans time + flags operator-paired session as prereq to executing-plans dispatch. Coverage check: LMT BUY/SELL (operator's predominant); MKT BUY/SELL (rare but exists); STOP (FIRED case); STOP_LIMIT (rare; verify field shape). At minimum 4 cassettes; brainstorm may recommend more.
9. **OQ-F deferral rationale soundness.** Auto-redirect tier-2 `multi_partial_vs_consolidated` → tier-1 `split_into_partials` is V2 follow-up dispatch candidate. Brainstorm enumerates the cascade analysis required + the confidence-threshold design space + why V1 mapper widening LIFTS the LOCK only for single-leg matched-tuple cases.
10. **OQ-G leave-as-is rationale soundness.** 6 historical correction-chain rows record V1's wrong `schwab_said_value`. Spec enumerates the 3 alternatives (leave-as-is + document; UPDATE retroactive; DELETE-and-resimulate) + rejection rationales for the latter two + the audit-trail-integrity LOCK preserving option.
11. **T-B.7 HTMX discipline preservation** (§2.5). `/schwab/status` is read-only V1 — but base-layout VM banner inheritance + `/config` "External integrations" nav-link discoverability + Sub-bundle B `/config?schwab_setup=ok` query-param consumer retargeting all need spec coverage. Watch for missing items.
12. **NO new schema** integrity check. Spec proposes NO `CREATE TABLE` / `ALTER TABLE` / `0020_*.sql` migration. If V2 mapper widening surfaces a need for schema change, STOP + flag for orchestrator escalation (C.A return report lesson #7 + 2026-05-15 `657b8a0` lesson).
13. **Sub-bundle decomposition cleanliness** (§2.10). Dispatch ordering + cross-bundle dependencies enumerated; no circular deps; T-B.7 web counterpart can be independent of mapper widening (parallelizable) OR sequential (operator preference). Brainstorm picks.
14. **Brief-premise empirical-verification** (Phase 10 + 2026-05-04 lesson family). Spec assertions about shipped-code state (e.g., "mapper at lines 175-242 takes order-grain inputs" / "classifier at `reconciliation_classifier.py:155-215` is tier-2-always per V1") verified against actual code/migration files before encoding as binding §1. **Particularly important here**: the Schwab API field-shape claim at OQ-E is uncertain without cassette evidence.
15. **~46 cumulative forward-binding lessons inheritance integrity.** Brief §0 lists them; spec audits compliance — especially:
    - **Sub-bundle C.B forward-binding lesson #7** (Co-Authored-By footer EXPLICIT suppression in dispatch prompts).
    - **Sub-bundle C.D 4 NEW lessons** (operator-pushback STOP-and-recover; production-write classifier soft-block per-invocation; orchestrator-inline gate-fix durable pattern; Pass-1 limit-vs-fill defect family extension).
    - **Sub-bundle C.B forward-binding lesson #5** (shape predicate tightening discipline applied to V2 mapper field-shape validation at `SchwabExecutionLeg.__post_init__`).
    - **Sub-bundle B forward-binding lesson #6** (`apply_overrides(cfg)` discipline at Schwab entry points — `/schwab/status` web counterpart inherits).
    - **HTMX gotcha trinity** (HX-Request propagation; HX-Redirect-vs-303-swap; HX-Redirect-target-unrouted) — T-B.7 inherits.
16. **Pass-2-tier-1-FORBIDDEN gotcha amendment text** (§2.7) reviewed for completeness — preserves V1 historical context + clearly marks V2-RESOLVED + references this spec + the V2 mapper widening dispatch.
17. **Convergent-chain expectation.** Codex round count likely 4-6; chain shape matters more than count. Implementer's return report documents fix-introduced regression vs adversarial-thrash distinction.
18. **§1.6 fill-auto-population-at-entry scope clarity.** Spec acknowledges scope; identifies clean layering interfaces; flags any V2-mapper-widening decisions that would foreclose. DOES NOT design fill auto-population.

---

## §6 Done criteria

1. Spec at `docs/superpowers/specs/2026-05-17-schwab-mapper-execution-grain-widening-design.md` covering §2.1-§2.10.
2. Brainstorm went through ≥3 Codex rounds reaching `NO_NEW_CRITICAL_MAJOR`.
3. Spec section structure mirrors prior brainstorm spec format (Phase 12 Sub-bundle C design canonical).
4. CVGI fill_id=9 + LION fill_id=15 each walked through end-to-end as discriminating examples in §2.2 classifier + §2.3 comparator.
5. 6 OQs (A-F) each addressed with recommendation-with-rationale + binding-vs-deferrable disposition; OQ-G additionally requires operator's leave-as-is rationale + the 2 rejected alternatives enumerated.
6. Sub-bundle decomposition recommendation in §2.10.
7. Single commit OR landing+fixes split: `docs(post-phase12): Schwab mapper execution-grain widening + T-B.7 + housekeeping brainstorm spec` (and follow-up commit `docs(post-phase12): brainstorm spec — Codex R1-R<N> fixes` if applicable).
8. Return report covers items in §7.

---

## §7 Return report format

```
## Return report — Post-Phase-12 Schwab mapper execution-grain widening brainstorm

### Spec location
`docs/superpowers/specs/2026-05-17-schwab-mapper-execution-grain-widening-design.md` ({line count} lines)
Commits on main:
- {sha} `docs(post-phase12): Schwab mapper execution-grain widening + T-B.7 + housekeeping brainstorm spec` (initial)
- (optional) {sha} `docs(post-phase12): brainstorm spec — Codex R1-R<N> fixes` (post-review)

### Codex review history
- R1: {C/M/m findings; verdict; FIXED/ACCEPTED counts}
- R2: ...
- ...
- Final verdict: NO_NEW_CRITICAL_MAJOR

### Three highest-leverage design decisions
1. ...
2. ...
3. ...

### V2 mapper widening architecture decision (§2.1)
Locked: SchwabExecutionLeg dataclass shape + SchwabOrderResponse.executions field + mapper extraction.
Rationale: ...

### Classifier consumer decision (§2.2)
Locked: Pass-2-tier-1-FORBIDDEN LIFT scope (single-leg matched-tuple only V1; multi-leg auto-redirect deferred V2).
Rationale: ...

### Comparator path decision (§2.3)
Locked: single-leg vs VWAP multi-leg routing.
Rationale: ...

### Backward-compat fall-through decision (OQ-A)
Locked: Path A (order-level fall-back) OR Path B (tier-2 unsupported).
Rationale: ...

### Tolerance window decision (OQ-C)
Locked: price_tolerance pick.
Rationale: ...

### FIRED-stop handling decision (OQ-D)
Locked: mirror entry-fill discipline OR defer.
Rationale: ...

### Schwab API cassette prerequisite (OQ-E)
Locked: which order types need cassette coverage + writing-plans-phase cassette-recording session prereq.

### Tier-1 auto-redirect deferral (OQ-F)
Confirmed: V2 follow-up dispatch candidate banked.

### Historical audit-row leave-as-is (OQ-G)
Confirmed: leave-as-is + document; 2 rejected alternatives enumerated.

### T-B.7 web counterpart scope (§2.5)
Locked: GET /schwab/status read-only V1; base-layout VM banner inheritance + nav-link from /config; HTMX trinity preserved.

### Sub-bundle decomposition + dispatch ordering (§2.10)
Locked: 3 sub-bundles with dispatch order + cross-bundle dependencies.

### Open questions for orchestrator triage
1. ...
2. ...

### Capture-needs feedback FOR WRITING-PLANS
- ...

### Outstanding capture-needs that DEFER to future dispatches
- ...
```

---

## §8 If you get stuck

- If §1 operator-locked constraints conflict with Codex finding, §1 wins; flag as open question.
- If a Codex round produces a finding you can't disposition without orchestrator input, ACCEPT-with-rationale + flag explicitly in spec's "open questions" section + return report.
- If the spec exceeds ~1000 lines, re-scope (smaller than Sub-bundle C's 1444 by design — bounded surface).
- DO NOT propose migration SQL or schema changes. DO NOT write code. If you start drafting `CREATE TABLE ...` / `class SchwabExecutionLeg:` (other than as illustrative sketch) / route handler bodies, stop.
- If you encounter a Phase 7/8/9/10/11/12-A/12-B/12-C lesson that conflicts with a V2 mapper widening design proposal, the prior-phase lesson wins (validated by ship-experience). Surface the conflict as a design constraint.
- If "fill auto-population at trade-entry" (§1.6) tempts you to design schema for it, STOP — separate sub-bundle (the same trap as Sub-bundle C brainstorm faced; banked).
- If you find yourself proposing schema changes for the V2 mapper widening, STOP — §1.1 lock #4 violated (schema MUST stay at v19); escalate to orchestrator.
- If you find yourself proposing retroactive `reconciliation_corrections` rewriting, STOP — §1.1 lock #5 violated (operator-recommended leave-as-is); flag as design constraint.
- If you find yourself proposing magnitude-based threshold gating on the mapper widening (e.g., "only apply execution-grain when delta > $0.10"), STOP — Sub-bundle C §1.1 lock #3 inheritance preserved (magnitude is the WRONG axis; determinism is the axis).
- If OQ-E cassette-recording feels under-specified, that's by design — it's a deferred prerequisite triggered at writing-plans phase (operator-paired session). Don't try to solve it in the brainstorm; just enumerate the order types that need coverage.
- If OQ-F auto-redirect tier-2 → tier-1 design tempts you toward V1 inclusion, STOP — operator's tentative recommendation is DEFER; cascade analysis required.

---

*End of brief. Standalone post-Phase-12 dispatch; bundles 8 operator-approved items (5 architectural + 1 web follow-up + 2 housekeeping micro-fixes + OQ-G operator-decision). Spec output target: `docs/superpowers/specs/2026-05-17-schwab-mapper-execution-grain-widening-design.md`. Expected duration 150-300 minutes including 4-6 Codex rounds. Schema unchanged (v19); architectural surface bounded.*
