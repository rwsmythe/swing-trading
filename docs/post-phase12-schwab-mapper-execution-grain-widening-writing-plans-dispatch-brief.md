# Post-Phase-12 Schwab Mapper Execution-Grain Widening + T-B.7 + Housekeeping — Writing-Plans Dispatch Brief

**Audience:** Fresh Claude Code instance with no prior conversation context.

**Mission:** Convert the post-Phase-12 Schwab mapper execution-grain widening brainstorm spec into an executable implementation plan via `copowers:writing-plans`. The skill wraps `superpowers:writing-plans` + adversarial Codex MCP review. Output is a single plan file the orchestrator subsequently dispatches via `copowers:executing-plans` as **2 sequential sub-bundle dispatches** (Sub-bundle 1 → Sub-bundle 2). Sub-bundle 3 housekeeping micro-fixes are FOLDED into Sub-bundle 1 per operator decision 2026-05-17.

**Expected duration:** ~3-6 hr planning + ~2-4 hr Codex convergence. Total ~5-10 hr. Smaller than Phase 12 Sub-bundle C writing-plans (8-14hr; 4 sub-sub-bundles + schema work) because (a) schema is LOCKED at v19 with NO new schema needed; (b) 2 sub-bundles not 4; (c) architectural surface bounded to mapper widening + classifier consumer + comparator + web counterpart; (d) operator already pre-decided OQ-E + parallelization + fold ahead of dispatch. Plan line target: **~1100–1700 lines**.

---

## §0 Inputs

### §0.1 Spec

- **SPEC_PATH:** `docs/superpowers/specs/2026-05-17-schwab-mapper-execution-grain-widening-design.md`
- **Spec status:** Codex R1-R4 substantive + R5 advisory → NO_NEW_CRITICAL_MAJOR at HEAD `dda8730` on main. **1086 lines** (8.6% over 600-1000 target; acceptable overshoot per brief expectation of 4-6 rounds). 6 commits in spec chain (`8c1e5cb` initial + 5 Codex-fix rounds through `dda8730`).
- **Spec produces** (per §1.5 + §3 + §4-§8 LOCKs): a locked V2 mapper widening shape (§4 — NEW `SchwabExecutionLeg` dataclass + `SchwabOrderResponse.executions: list[SchwabExecutionLeg] | None = None` tri-valued field + mapper extension at `map_orders_to_fill_candidates`); locked comparator path (§5.1 — `_compute_execution_price(so)` helper + §5.3 `_resolve_match_quantity(so)` helper for quantity-grain switch + comparator at `swing_reconciliation.py:693` switching to execution-grain VWAP); locked classifier consumer scope (§3.2 + §5.2 — V1 LIFT scope = **Pass-1 only**; NEW Shape C predicate `source_keys == {"price"} | _EXECUTION_AUDIT_KEYS` at `_classify_entry_price_mismatch` + `_classify_close_price_mismatch`; `_classify_unmatched_fill_shared` gains ONLY the Path B `execution_unavailable=true` sentinel recognition; Pass-2 STAYS tier-2-always V1); locked backward-compat fall-through (§6.1 OQ-A — Path B tier-2 `unsupported` when `orderActivityCollection` missing/empty); locked tolerance window (§6.3 OQ-C — `price_tolerance=0.01` retained); locked FIRED-stop discipline (§6.4 OQ-D — Path A mirror entry-fill); locked Schwab API cassette-recording prerequisite (§6.5 OQ-E — **operator-decided 2026-05-17: cassette-required default**); locked T-B.7 web counterpart scope (§7 — GET `/schwab/status` read-only V1 + `SchwabStatusVM` 1:1 with CLI + base.html.j2 inheritance + nav-link from `/config` "External integrations" + `/schwab/setup` HX-Redirect retargeting + `/config?schwab_setup=ok` consumer RETAINED one release window); locked housekeeping micro-fixes (§8 — CVGI date typo verify; Pass-2-tier-1-FORBIDDEN gotcha amendment; historical audit-row leave-as-is generic ID-free CLI help-text addendum); 2 discriminating-example walkthroughs (§10 — CVGI fill_id=9 + LION fill_id=15); 3 sub-bundle decomposition (§9.1 — Sub-bundle 1/2/3 with cross-bundle dependencies + parallelization options); 7 V2 follow-up candidates banked (§9.2); 25 LOCKED Codex round outcomes (§13).
- **Spec deliberately does NOT produce** (per §3 + §13): migration SQL drafts (no schema work; v19 unchanged), code drafts, sub-bundle task-decomposition into per-task acceptance criteria, re-litigation of §1 operator-locked constraints. **THAT IS WRITING-PLANS' JOB.**

### §0.2 Project state at dispatch time

- **HEAD on `main`:** `dda8730` (post-brainstorm-spec-Codex-R5-fix). Brief commit will land at HEAD+1 pre-dispatch.
- **Test count:** **~4363 fast passing on main** + 3 pre-existing failures (3 phase8 walkthrough; unchanged since Phase 8 ship) + 5 skipped. Verified at brief drafting time post-brainstorm-merge.
- **Ruff baseline:** **18** (E501 only; unchanged across Phase 11 + Phase 12 + post-Phase-12 brainstorm).
- **Schema version:** **v19.** LOCKED since Phase 12 Sub-sub-bundle C.A at 2026-05-15. **Sub-bundle 1 + 2 are consumer-side only — DO NOT propose v20 migration** (spec §1.3 lock).
- **Phase 12 CLOSED.** Sub-bundle A `123d27a` (operational-pain) + Sub-bundle B `b09eb06`/`7b75d4a` (web-UI-friendliness) + Sub-bundle C closed via 4 sub-sub-bundles A+B+C+D (final merge `bd1a62b` 2026-05-17; status-line + 2 NEW gotchas + Pass-2-tier-1-FORBIDDEN gotcha AMENDED at `4bab6ee`).
- **Production discrepancy state:** ZERO unresolved-material (all 7 from C.D gate dispositioned in terminal states: 3 CVGI/LION tier-1-then-override-back per limit-vs-fill finding + 4 DHC/VSAT mark_unmatched/acknowledge). Phase 10 dashboard banner count=0. **Sub-bundle 1 ship is the architectural fix that prevents these CVGI/LION-family false-positive emissions going forward** (the historical correction chains at correction_ids 1-6 remain leave-as-is per OQ-G).
- **Production refresh-token clock:** expires ~2026-05-22T17:05:00+00:00. Operator may need to re-auth via `/schwab/setup` web form OR `swing schwab setup` CLI before Sub-bundle 1 gate session if it lands after that date. T-A.2 self-healing means recovery is one CLI/web invocation now.
- **Worktree husks:** ALL CLEAN as of brief drafting time — operator's `cleanup-locked-scratch-dirs.ps1 -DeregisterFirst` pass cleared all 4 phase12-bundle-c-* husks.

### §0.3 Operator-resolved decisions (BINDING for plan; 2026-05-17 post-brainstorm triage)

Brainstorm spec §6 + §9 produced 6 OQs (A-F) all reaching binding-or-deferrable LOCKs in spec; OQ-G operator-decided. Post-brainstorm operator triage 2026-05-17 settled the 3 writing-plans-phase decisions:

| Question | Operator-resolved disposition (2026-05-17) | Spec section |
|---|---|---|
| **OQ-E cassette-recording prerequisite** | **Cassette-required default.** Operator-paired cassette-recording session BEFORE Sub-bundle 1 executing-plans dispatch covering 4 order types minimum (LIMIT BUY, LIMIT SELL, STOP FIRED, MARKET BUY); stretch STOP_LIMIT FIRED. Writing-plans phase routes this into the Sub-bundle 1 executing-plans dispatch brief §0 LOCK as a HARD PREREQUISITE. Mocked-only fallback NOT elected. | §6.5 |
| **Sub-bundle 1 + 2 ordering** | **Sequential 1 then 2.** Sub-bundle 1 (mapper widening) dispatches FIRST; Sub-bundle 2 (T-B.7 `/schwab/status`) dispatches AFTER Sub-bundle 1 ships. No concurrent worktrees. Per spec §9.1 default. | §9.1 |
| **Sub-bundle 3 housekeeping fold** | **Fold into Sub-bundle 1.** Sub-bundle 1's CLAUDE.md gotcha amendment + status-line refresh + phase3e-todo leave-as-is entry land in the SAME integration merge as the code. Atomic correctness preserved. NO standalone Sub-bundle 3. Brainstorm noted CVGI date typo (housekeeping #1) returned ZERO matches in CLAUDE.md at brainstorm time — orchestrator confirms same at brief-drafting time. Housekeeping #1 ships as a no-op-with-note in plan §A. | §9.1 |

**LOCKED-in-spec (no plan-author action needed; track only):**

| Topic | Disposition | Locked at |
|---|---|---|
| OQ-A backward-compat path | Path B (tier-2 `unsupported` via `unmatched_*_fill` + `execution_unavailable=true` sentinel) when `orderActivityCollection` missing/empty | spec §6.1 |
| OQ-B multi-leg journal-fill | VWAP comparator V1; leg-by-leg audit deferred to OQ-F V2 | spec §6.2 |
| OQ-C tolerance | `price_tolerance=0.01` retained | spec §6.3 |
| OQ-D FIRED-stop | Path A — `executionLegs[].price` consumed uniformly for FILLED orders regardless of `order_type` | spec §6.4 |
| OQ-F tier-1 auto-redirect | V2 follow-up dispatch deferred; V1 Pass-2 stays tier-2-always except Path B sentinel recognition | spec §6.6 |
| OQ-G historical audit-row | Leave-as-is + document; §8.3 generic ID-free CLI help-text addendum on `show-correction` subcommand | spec §6.7 + §8.3 |
| Shape C predicate | NEW `source_keys == {"price"} | _EXECUTION_AUDIT_KEYS` predicate at `_classify_entry_price_mismatch` + `_classify_close_price_mismatch`; Sub-bundle C.B's Shape A + Shape B predicates preserved unchanged | spec §3 + §5.2 |
| V1 LIFT scope = Pass-1 only | Pass-2 `unmatched_*_fill` LIFT entirely deferred V2; V1 ONLY adds Path B sentinel recognition | spec §1.5 + §3.2 + §6.6 |
| Quantity-grain switch | `_resolve_match_quantity(so)` helper preferring `sum(legs.quantity)` over `so.quantity` when executions populated; mapper coherence-check distinguishes legitimate partial fills from malformed leg totals | spec §5.3 |

**Writing-plans decides (defer to plan author):**

| Topic | Spec recommendation | Plan posture |
|---|---|---|
| Sub-bundle 1 task grain (mapper + classifier + comparator split across N tasks vs unified) | Spec §9.1 enumerates atomic-grain phases (mapper extension; classifier branches; comparator switch; backward-compat; housekeeping); writing-plans decides per-task vs per-phase granularity. | Plan author chooses; aim for 10-14 tasks total in Sub-bundle 1. |
| Cassette runbook + sanitization filter spec | Spec §6.5 + §11 enumerate the cassette session prereq + minimum 4 order types; writing-plans drafts the cassette runbook including filter spec (auth header redaction; `authorization_code` redaction; `accountHash` redaction; token-shape regex). | Writing-plans verifies pattern against `tests/integrations/test_finviz_api_live.py` cassette precedent + Phase 11 D V2-PLANNED Schwab cassette runbook gap (CLAUDE.md gotcha). |
| `SchwabExecutionLeg.__post_init__` validation strictness | Spec §4.1 enumerates `price > 0` AND `quantity > 0` AND `math.isfinite()` guards; writing-plans may add `mismarked_quantity` sanity check or relax based on real-world Schwab fixture observations. | Writing-plans verifies against Sub-bundle C.B forward-binding lesson #5 (shape predicate tightening discipline) + locks at task grain. |
| `surface=` value for new entry points | Spec §3.2 implies CLI surface (`'cli'`) for any new manual invocation; web counterpart at T-B.7 uses `'cli'` per Sub-bundle B precedent (V2 `surface='web'` enum widening banked). | Writing-plans locks. |

**V2-banked / informational (no action this dispatch; per spec §9.2):**

- OQ-F V2 follow-up dispatch (multi-leg tier-1 auto-redirect from tier-2 `multi_partial_vs_consolidated` → tier-1 `split_into_partials`).
- Per-row `engine_version` metadata column on `reconciliation_corrections` (requires schema v20; out of scope here).
- `/config?schwab_setup=ok` hard removal (passive no-op landing retained one release window per Codex R1 m#2).
- Per-leg audit surfacing for tier-2 outside-tolerance VWAP (`actual_value_json.execution_legs` audit-only V1).
- Schwab cassette runbook elevation (currently V2-PLANNED; V2 mapper widening MAY ship the runbook as part of Sub-bundle 1 cassette session per OQ-E LOCK).
- Fill auto-population at trade-entry time (broader sub-bundle; spec §1.6 OUT-OF-SCOPE).
- Web Tier-2 discrepancy-resolution surface (Sub-bundle C plan §I.3 V2).
- schwabdev SDK upgrade or token encryption-at-rest (Sub-bundle B V2).

### §0.4 Forward-binding lessons inherited (BINDING for plan)

**~60 cumulative lessons** inheritance through Sub-bundle 1 writing-plans:
- Phase 11 Schwab arc: 17 lessons (A 5 + B 7 + C 5 + D 0)
- Phase 12 Sub-bundle A: 5 lessons
- Phase 12 Sub-bundle B: 12 lessons (return report §10)
- Phase 12 Sub-bundle C brainstorm: 5 lessons (orchestrator-context.md `effb995`)
- Phase 12 Sub-sub-bundle C.A: 3 lessons (return report §11)
- Phase 12 Sub-sub-bundle C.B: 7 lessons (return report §11)
- Phase 12 Sub-sub-bundle C.C: 7 lessons (return report §10)
- Phase 12 Sub-sub-bundle C.D: ~7 lessons (return report §10) + 4 NEW C.D-arc lessons (orchestrator-context.md `4b392fc`)
- Post-Phase-12 brainstorm: ~5 NEW lessons (will bank in orchestrator-context.md post-merge; preliminary from return report)

The **4 NEW C.D-arc lessons** banked at orchestrator-context.md `4b392fc` are particularly load-bearing for Sub-bundle 1 writing-plans:

1. **Operator-architectural-pushback mid-gate triggers STOP-and-recover, not push-through.** The CVGI + LION limit-vs-fill defect surfaced because operator pushed back mid-gate. Plan §A locks Sub-bundle 1 operator-witnessed gate surfaces enumerated for the production-write `--apply` path (mirror C.D 10-surface gate precedent where production-write surfaces against operator's REAL DB).
2. **Production-write classifier soft-block fires PER-INVOCATION even after AskUserQuestion authorization.** Plan §A acknowledges this for any Sub-bundle 1 gate surface that invokes reconciliation against production DB — operator pre-authorizes via plain-chat "yes" per invocation; gate-driver does NOT batch authorizations.
3. **Orchestrator-inline gate-fix is a durable Phase-12-arc pattern (3 cumulative instances).** Plan §A's discriminating-test enumeration includes the C.D gate-fix #1-#3 family pre-emptions: Windows cp1252 stdout encoder (avoid non-ASCII glyphs in any new CLI output OR rely on `swing/cli.py` entry's UTF-8 stdout reconfigure as defense-in-depth); synthetic-fixture-vs-production-emitter shape drift (per Sub-bundle 1 mapper widening — test fixtures plant Schwab response shapes that match production emitter byte-for-byte).
4. **Pass-1 tier-1 entry_price_mismatch inherits limit-vs-fill defect from Pass-2-tier-1-FORBIDDEN family.** **THIS IS THE RAISON D'ÊTRE FOR SUB-BUNDLE 1.** Plan §A Sub-bundle 1 scope LOCKS the architectural fix: V2 mapper widening surfaces `orderActivityCollection[].executionLegs[]`; classifier Shape C predicate consumes execution-grain data; comparator switches to execution-leg VWAP. After Sub-bundle 1 ships, the Pass-2-tier-1-FORBIDDEN gotcha gets the V2-RESOLVED amendment per spec §8.2.

**5 Sub-bundle C brainstorm lessons** (orchestrator-context.md `effb995`) — particularly load-bearing for Sub-bundle 1 writing-plans:

1. **9-substantive-round chain new project high-water mark for architectural-pivot brainstorms.** This brainstorm needed 5 rounds (lower bound; bounded scope). Writing-plans budget: 4-5 rounds (smaller plan than Phase 12 Sub-bundle C; ~1100-1700 lines).
2. **Brainstorm-time composition-source claims need empirical verification BEFORE spec encoding.** Plan §A pre-verification list MUST include: `swing/integrations/schwab/mappers.py:175-242` mapper body (verified at brief-drafting time; greenfield extension to extract `orderActivityCollection`); `swing/trades/schwab_reconciliation.py:660-720` comparator (verified line 693 `abs(so.price - float(f.price)) > price_tolerance`); `swing/trades/reconciliation_classifier.py:155-215` `_classify_unmatched_fill_shared` (verified tier-2-always per V1 LOCK); `swing/integrations/schwab/models.py:133-180` `SchwabOrderResponse` (verified 8 fields; greenfield extension to add `executions` field); `swing/web/routes/schwab.py` mounted route group (verified Sub-bundle B `/schwab/setup` shipped); `swing/cli.py` `swing schwab status` Click command (verified Phase 11 Sub-bundle D shipped); `swing/web/templates/base.html.j2` extension pattern (verified Phase 10 Sub-bundle E T-E.3 banner pin).
3. **Persisted-JSON-tier-1 vs re-fetched-tier-1 asymmetry.** Sub-bundle 1 LIFTS the V1 mapper limitation for Pass-1 only (persisted-JSON-grain classification); Pass-2 (re-fetched Schwab) stays tier-2-always per spec §1.5 LOCK. Plan §A.1 reaffirms.
4. **Synthetic-fixture-only acceptance test for production-write-contract surfaces.** Sub-bundle 1's gate `--apply` surface against production data MUST run with isolated tmp DB for any acceptance-test pathway that exercises `--custom-value` shape coverage (mirrors C.D T-D.11 precedent). Per spec §10.5 walkthrough.
5. **Brief enumeration of shipped CHECK enums needs empirical verification against migration files.** N/A for Sub-bundle 1 + 2 (no schema work; no CHECK enum widening).

**5 NEW post-Phase-12 brainstorm lessons** (preliminary from return report; will bank in orchestrator-context.md post-merge):

1. **Operator-decided architectural binding question (OQ-E refinement).** When brainstorm-time the operator's intent ranges across "required" vs "optional", brainstorm CAN lock a default + open the decision authority to operator at writing-plans phase via routing-into-dispatch-brief mechanic — better than guessing wrong at brainstorm time + paying for re-litigation rounds.
2. **Audit-bearing classifier predicate (Shape C) emergence at Codex R1.** A V2 architectural addition that extends a closed predicate family (Sub-bundle C.B Shape A + Shape B) needs Codex R1 to surface — implementer's first-cut spec proposal would have routed audit-bearing payloads to tier-2 `unsupported` under the strict-set Shape A predicate. Writing-plans phase tasks MUST enumerate the Shape C predicate AS A TASK with its own discriminating test (Shape A preserved; Shape B preserved; Shape C newly recognized; mixed/partial Shape C → tier-2).
3. **Quantity-grain vs order-grain switch is a separate concern from price-grain.** Codex R1 M#2+M#3 caught that the matching step's quantity comparison (`abs(so.quantity - float(f.quantity)) > price_tolerance`) ALSO needs execution-grain switch (preferring `sum(legs.quantity)` over `so.quantity`). Plan §A locks `_resolve_match_quantity(so)` as a separate task from `_compute_execution_price(so)`.
4. **Mapper coherence-check distinguishes legitimate partial fills from malformed leg totals.** When `sum(legs.quantity) == order.filledQuantity` → legitimate partial fills (preserve `executions`); when `sum(legs.quantity) != order.filledQuantity` → malformed leg totals (collapse to `executions=None`; comparator Path B fall-through). Plan §A locks this at mapper level with discriminating tests for both branches.
5. **Generic ID-free CLI help-text addendum vs per-row engine_version metadata.** OQ-G operator-decided leave-as-is + GENERIC help text mechanic (vs per-row metadata requiring schema v20) preserves §1.3 schema LOCK. Plan §A locks the generic CLI help-text mechanic at task grain.

### §0.5 Brief-vs-shipped-code empirical verification (pre-drafting checklist)

Per Lesson #2 above + spec §6.5 OQ-E cassette session prereq. Writing-plans implementer MUST verify the following shipped surface shapes BEFORE drafting per-task acceptance criteria. **Each verification produces a verbatim grep result + confirmation in plan §A.0 pre-verification list.**

1. **`swing/integrations/schwab/mappers.py:175-242`** — `map_orders_to_fill_candidates(...)` body extracts `order_type` + `price` (with `stopPrice` fallback) + `quantity` from order-grain `leg0`. **Confirm:** lines 223-230 read `price_raw = _opt(raw, "price")` + fall-back to `stopPrice`; this is what V2 widening extends to ALSO extract `orderActivityCollection[].executionLegs[]`.
2. **`swing/integrations/schwab/models.py:133-180`** — `SchwabOrderResponse` dataclass with 8 fields + `__post_init__` validators rejecting unknown statuses + unknown instructions + unknown order_types. **Confirm:** dataclass shape + validator pattern; this is what V2 widening extends with `executions: list[SchwabExecutionLeg] | None = None` optional field.
3. **`swing/trades/schwab_reconciliation.py:660-720`** — reconciliation comparator emits `entry_price_mismatch`/`close_price_mismatch` (line 693) + `unmatched_open_fill`/`unmatched_close_fill` (line 672 with synthetic `field_name='fill_match'`). **Confirm:** line 693 `abs(so.price - float(f.price)) > price_tolerance`; this is what V2 widening switches to `_compute_execution_price(so)`.
4. **`swing/trades/reconciliation_classifier.py:155-215`** — `_classify_unmatched_fill_shared` is tier-2-always per V1 Pass-2-tier-1-FORBIDDEN LOCK. **Confirm:** V2 Sub-bundle 1 widening adds ONLY the Path B `execution_unavailable=true` sentinel recognition; Pass-2 LIFT entirely deferred per spec §6.6 LOCK.
5. **`swing/trades/reconciliation_classifier.py:_classify_entry_price_mismatch` + `_classify_close_price_mismatch`** — current Shape A + Shape B predicates. **Confirm:** Shape A persisted-JSON-only `source_keys == {"price"}`; Shape B full match-tuple `source_keys >= {"price", "ticker", "date", "quantity"}`; this is what V2 widening extends with NEW Shape C `source_keys == {"price"} | _EXECUTION_AUDIT_KEYS` predicate.
6. **`swing/web/routes/schwab.py`** — `GET /schwab/setup` + `POST /schwab/setup` route definitions from Phase 12 Sub-bundle B (`b09eb06`). **Confirm:** route mounting pattern; this is the format Sub-bundle 2 `GET /schwab/status` mirrors.
7. **`swing/cli.py`** — `swing schwab status` Click command from Phase 11 Sub-bundle D + per-environment 3-state output. **Confirm:** CLI shape + status text; this is what `SchwabStatusVM` mirrors 1:1.
8. **`swing/web/templates/base.html.j2`** — Phase 10 Sub-bundle E T-E.3 base-layout VM banner pin populating `unresolved_material_discrepancies_count`. **Confirm:** template inheritance pattern; Sub-bundle 2 `SchwabStatusVM` MUST populate the banner field.
9. **`swing/web/routes/schwab.py:POST /schwab/setup`** — `HX-Redirect: /config?schwab_setup=ok` success-path response. **Confirm:** Sub-bundle 2 plan retargets this to `/schwab/status` while RETAINING `/config?schwab_setup=ok` as passive no-op consumer per spec §7.3 + R1 m#2 LOCK (one release window).
10. **`swing/web/routes/config.py`** — `/config` page "External integrations" section + `/schwab/setup` nav-link (`7b75d4a` orchestrator-inline gate-fix). **Confirm:** nav-link addition pattern; Sub-bundle 2 plan adds `/schwab/status` nav-link in same section.
11. **Schwab API spec at `reference/schwab-api/account-specification.md:1791-1800`** — `orderActivityCollection[].executionLegs[]` field shape: `legId` / `price` / `quantity` / `mismarkedQuantity` / `instrumentId` / `time`. **Confirm:** field names + types match `SchwabExecutionLeg` dataclass spec §4.1.
12. **`tests/integrations/test_finviz_api_live.py` cassette pattern** — existing cassette infrastructure precedent. **Confirm:** cassette filter list pattern (auth header redaction; token-shape regex) for Sub-bundle 1 cassette session runbook draft.

### §0.6 Cassette-recording session prerequisite (OQ-E LOCK)

Per operator decision 2026-05-17 (post-brainstorm triage): **cassette-required default; Sub-bundle 1 executing-plans dispatch BLOCKED on operator-paired cassette-recording session.**

**Writing-plans phase MUST:**

1. **Draft the cassette runbook** as a plan §F dedicated section: (a) which order types need coverage (LIMIT BUY + LIMIT SELL + STOP FIRED + MARKET BUY minimum; STOP_LIMIT FIRED stretch); (b) how to record (operator-paired session driver via `swing schwab fetch --verify-marketdata` or equivalent + `vcrpy` cassette write); (c) sanitization filter spec (auth header redaction; `client_id` + `client_secret` masking; `accountHash` masking; token-shape regex 32+ hex-char + 24+ base64-char per Phase 11 Sub-bundle A T-A.10 D1 redaction pattern); (d) cassette storage path (`tests/integrations/cassettes/schwab_*.yaml`); (e) staleness recovery runbook.
2. **Specify cassette acceptance criteria** as plan §G dedicated section: per cassette, the `SchwabOrderResponse` mapping output is byte-for-byte verified (snapshot test); the `SchwabExecutionLeg` dataclass shape validates without exception; the test exercises the comparator + classifier paths (not just the mapper).
3. **Surface the operator-paired cassette session as a dispatched-dependency** in the Sub-bundle 1 executing-plans dispatch brief §0 LOCK: "Sub-bundle 1 executing-plans dispatch BLOCKED until operator-paired cassette session ships cassettes at `tests/integrations/cassettes/schwab_*.yaml` covering 4 order types minimum."

**Writing-plans phase MUST NOT:**

- Propose mocked-only fallback as the default path (operator NOT-elected per OQ-E LOCK).
- Skip the cassette session in the dispatch ordering (cassette session is a HARD PREREQ; sequenced BEFORE Sub-bundle 1 executing-plans dispatch).
- Specify the cassette session as concurrent with Sub-bundle 1 implementation work (the implementation depends on the cassettes existing).

---

## §1 Strategic context (brief-author-distilled)

### §1.1 Six operator-locked architectural constraints (BINDING)

Per spec §1 (operator-locked; do NOT re-litigate; writing-plans inherits):

1. **Execution price IS truth for fill-grain reconciliation.** Schwab API exposes execution-grain data via `orderActivityCollection[].executionLegs[].price`; V1 mapper reads only order-grain. CVGI + LION 2026-05-17 falsified V1 limit-vs-fill assumption. V2 mapper widening is the architectural fix.
2. **`stop_mismatch` architecture is SOUND** — do NOT propose changes there. The `_find_working_stop_for_ticker` path compares journal `current_stop` vs Schwab `stopPrice` (operator-set trigger via WORKING-only orders); both sides are trigger thresholds, apples-to-apples. Defect is fill-grain ONLY.
3. **Schema MUST stay at v19.** V2 mapper widening fits in existing `actual_value_json` envelope + new dataclass field on `SchwabOrderResponse` — should NOT need new tables, column ALTERs, or migration v19→v20. If plan author surfaces a need for schema change, STOP + escalate.
4. **Audit-trail integrity preserved.** Historical `reconciliation_corrections` rows (correction_ids 1-6) recorded V1's WRONG `schwab_said_value` — do NOT propose retroactive rewriting (OQ-G).
5. **Multi-leg VWAP V1; leg-by-leg audit deferred V2.** V1 mapper widening surfaces execution-grain data; comparator uses VWAP for multi-leg; auto-redirect tier-2 `multi_partial_vs_consolidated` → tier-1 `split_into_partials` deferred OQ-F V2.
6. **Magnitude is NOT the axis (Sub-bundle C inheritance).** Determinism is the axis. NO magnitude-based auto-vs-surface threshold gates.

### §1.2 Sub-bundle decomposition (per spec §9.1; operator-confirmed 2026-05-17)

| Sub-bundle | Scope | Dependencies | Ships before |
|---|---|---|---|
| **Sub-bundle 1 — V2 mapper widening + classifier consumer + comparator + housekeeping (FOLDED)** | NEW `SchwabExecutionLeg` dataclass + `SchwabOrderResponse.executions` field + `map_orders_to_fill_candidates` body extension; NEW `_compute_execution_price(so)` helper + `_resolve_match_quantity(so)` helper at `swing/trades/schwab_reconciliation.py`; NEW Shape C predicate at `_classify_entry_price_mismatch` + `_classify_close_price_mismatch`; Path B sentinel recognition at `_classify_unmatched_fill_shared`; backward-compat fall-through (Path B tier-2 `unsupported` when `orderActivityCollection` missing/empty); CLAUDE.md `Pass-2-tier-1-FORBIDDEN` gotcha amendment marking V2-RESOLVED; status-line CVGI date no-op-with-note (housekeeping #1; already-verified zero matches); historical `reconciliation_corrections` leave-as-is generic ID-free `show-correction` CLI help-text addendum; cassette-recording session prereq + cassette runbook; +discriminating tests against CVGI fill_id=9 + LION fill_id=15 + 4 cassette-recorded order types (minimum). | Cassette session (operator-paired) | Sub-bundle 2 |
| **Sub-bundle 2 — T-B.7 `/schwab/status` web counterpart** | NEW `GET /schwab/status` route at `swing/web/routes/schwab.py`; NEW `SchwabStatusVM` view-model mirroring CLI `swing schwab status` 1:1; NEW `swing/web/templates/schwab_status.html.j2` extending `base.html.j2` (inherits Phase 10 T-E.3 banner pin); `/config` "External integrations" nav-link to `/schwab/status` (mirrors B `7b75d4a` precedent); `/schwab/setup` POST `HX-Redirect` retargets to `/schwab/status` while RETAINING `/config?schwab_setup=ok` as passive no-op consumer (one release window per Codex R1 m#2). | Sub-bundle 1 (SHIPS AFTER) | (CLOSES this dispatch arc) |

**~~Sub-bundle 3 — Housekeeping micro-fixes~~ FOLDED INTO Sub-bundle 1 per operator decision 2026-05-17.**

### §1.3 Plan-output shape expectations

Per spec §13 hand-off + brief §0.3 operator decisions:

- §13 enumerates 25 Codex-LOCKED items the plan inherits as locked from spec (re-enumerated in plan §A with task-level acceptance criteria).
- 6 OQs A-F all LOCKED in spec (no orchestrator-triage escalation needed); OQ-E operator-decided + OQ-G operator-decided per brief §0.3.
- Plan §A pre-verification list completes 12 verifications against shipped code BEFORE drafting per-task acceptance criteria (per brief §0.5 list).
- Plan §F + §G cassette runbook + acceptance-criteria sections.
- Plan §H per-sub-bundle operator-witnessed gate plan (Sub-bundle 1: 7-9 surfaces; Sub-bundle 2: 4-5 surfaces).

Plan should be **single-file output** at `docs/superpowers/plans/2026-05-17-schwab-mapper-execution-grain-widening-plan.md`, ~1100-1700 lines. Per-sub-bundle task grain locked; per-task acceptance criteria locked; per-task projected test deltas locked; cross-sub-bundle dependencies enumerated.

---

## §2 Plan scope (what writing-plans produces)

### §2.1 Per-sub-bundle task decomposition

For each of Sub-bundle 1 + Sub-bundle 2, plan §A enumerates:

- Task list with task IDs (T-1.0 ... T-1.N for Sub-bundle 1; T-2.0 ... T-2.N for Sub-bundle 2).
- Per-task scope (1-2 paragraphs).
- Per-task acceptance criteria (numbered list).
- Per-task discriminating-test patterns (mirror spec §10 walkthroughs where applicable — CVGI fill_id=9 + LION fill_id=15 + 4 cassette order types).
- Per-task files-touched list.
- Per-task tests-added projection.
- Per-task commit message stem.
- Per-task ordering within sub-bundle (when tasks have intra-bundle dependencies).

**Tentative Sub-bundle 1 task shape** (writing-plans refines; ~10-14 tasks total):

- T-1.0 Cassette runbook + sanitization filter spec authored (DOCS ONLY; ships ahead of cassette session).
- T-1.1 `SchwabExecutionLeg` dataclass NEW + `__post_init__` validators + tests.
- T-1.2 `SchwabOrderResponse.executions` field extension + tri-valued semantics tests.
- T-1.3 `map_orders_to_fill_candidates` body extension (extract `orderActivityCollection[].executionLegs[]`; defensive parsing; mapper coherence-check; legitimate-partial-fills vs malformed-leg-totals distinction) + tests.
- T-1.4 `_compute_execution_price(so)` helper at `swing/trades/schwab_reconciliation.py` (single-leg + multi-leg VWAP + None-fall-through) + tests.
- T-1.5 `_resolve_match_quantity(so)` helper for quantity-grain switch + tests.
- T-1.6 Comparator path switch at `schwab_reconciliation.py:693` to execution-grain VWAP (price comparator) + tests + backward-compat fall-through (Path B tier-2 `unsupported` via `unmatched_*_fill` + `execution_unavailable=true` sentinel).
- T-1.7 Comparator quantity-match switch (Codex R1 M#2 fix) + tests.
- T-1.8 NEW Shape C predicate at `_classify_entry_price_mismatch` + `_classify_close_price_mismatch` (Sub-bundle C.B Shape A + Shape B preserved unchanged) + discriminating tests (Shape A preserved; Shape B preserved; Shape C newly recognized; mixed/partial Shape C → tier-2).
- T-1.9 `_classify_unmatched_fill_shared` Path B sentinel recognition (Pass-2 stays tier-2-always V1 except adds Path B execution_unavailable=true sentinel) + tests.
- T-1.10 CLAUDE.md `Pass-2-tier-1-FORBIDDEN` gotcha amendment marking V2-RESOLVED (housekeeping FOLDED).
- T-1.11 Status-line CVGI date verification + no-op-with-note (housekeeping #1; already-verified zero matches).
- T-1.12 `show-correction` CLI generic ID-free help-text addendum (OQ-G operator-decided) + tests.
- T-1.13 End-to-end integration test against cassette-recorded order types (4 minimum: LIMIT BUY + LIMIT SELL + STOP FIRED + MARKET BUY; stretch STOP_LIMIT FIRED).

**Tentative Sub-bundle 2 task shape** (writing-plans refines; ~5-7 tasks total):

- T-2.0 `SchwabStatusVM` view-model NEW + base-layout VM banner pin + tests.
- T-2.1 `GET /schwab/status` route handler + `apply_overrides(cfg)` discipline at entry point + query-param `?environment=production|sandbox` override + tests.
- T-2.2 `swing/web/templates/schwab_status.html.j2` template extending `base.html.j2` + 3-state CONFIGURED/PROVISIONAL/NOT_CONFIGURED rendering + refresh-token TTL severity escalation + recent-call audit summary.
- T-2.3 `/config` "External integrations" nav-link to `/schwab/status` (mirrors `7b75d4a` orchestrator-inline gate-fix precedent) + regression test (per Phase 6 I3 target-route-registered check).
- T-2.4 `/schwab/setup` POST `HX-Redirect` retargets to `/schwab/status` + `/config?schwab_setup=ok` passive no-op consumer retention test.
- T-2.5 HTMX gotcha trinity preservation test (HX-Request propagation; HX-Redirect-vs-303-swap; HX-Redirect-target-unrouted — Phase 6 I3 lesson family).
- T-2.6 OQ-D applicability test for `/schwab/status` (V1 inherits CLI semantics 1:1; no FIRED-stop awareness specific to web).

### §2.2 Cross-sub-bundle dependencies

Plan §B enumerates cross-bundle pins:
- Sub-bundle 1 → Sub-bundle 2: Sub-bundle 2's `SchwabStatusVM` base-layout VM banner population pattern follows Sub-bundle 1's discipline; no direct module dependency (parallelizable in theory; sequential per operator decision).
- Cassette session → Sub-bundle 1: cassette session ships cassettes at `tests/integrations/cassettes/schwab_*.yaml`; Sub-bundle 1 implementation tests CONSUME them.
- Sub-bundle 1 housekeeping → CLAUDE.md gotcha section: T-1.10 amendment text reviewed for completeness + V2-RESOLVED top-section + V1 historical context preserved (CVGI + LION 2026-05-17 falsification evidence).

### §2.3 Per-sub-bundle operator-witnessed gate plan

Plan §H enumerates per-sub-bundle gate surfaces:

**Sub-bundle 1 gate (7-9 surfaces; +cassette-session-driven; production-write at S3+S4):**

- S1 Inline `pytest -m "not slow" -q -n auto` GREEN at ~4413-4493 fast tests (worktree-side; +50-130 net from 4363 baseline).
- S2 Cassette-driven mapper test PASS (4 order types minimum).
- S3 PRODUCTION DRY-RUN: `swing journal reconcile-tos --dry-run --schwab` (or equivalent) against operator's production DB. Expected: NO false-positive `entry_price_mismatch`/`close_price_mismatch` for CVGI + LION (V2 mapper correctly compares execution-grain).
- S4 PRODUCTION APPLY: optional — operator's preference. If applied, verify no false-positive discrepancies emitted; reconciliation_run completes cleanly.
- S5 Phase 10 dashboard banner count=0 (unchanged; production state remains clean).
- S6 CLAUDE.md gotcha amendment text reviewed by operator (T-1.10).
- S7 `show-correction` CLI generic help-text addendum manually invoked + operator-acceptance.
- S8 Ruff `swing/` reports 18 E501 unchanged.
- S9 (optional) Spot-check production `schwab_api_calls` audit log + cassette consumption pattern.

**Sub-bundle 2 gate (4-5 surfaces; web-driven via Chrome MCP):**

- S1 Inline `pytest -m "not slow" -q -n auto` GREEN at ~4428-4523 fast tests (worktree-side).
- S2 Chrome MCP walkthrough: `/schwab/status` renders production state + 3-state badge + refresh-token TTL + audit summary + ZERO console errors.
- S3 Chrome MCP walkthrough: `/config` "External integrations" section shows `/schwab/status` nav-link + click navigates correctly.
- S4 `/schwab/setup` POST + HX-Redirect to `/schwab/status` (operator may need to re-auth Schwab refresh-token before gate; T-A.2 self-healing path).
- S5 Ruff `swing/` reports 18 E501 unchanged.

### §2.4 Test projection

Plan §E projects total test delta. Spec §9 projects:
- Sub-bundle 1: +30-60 fast tests (per spec §9.1)
- Sub-bundle 2: +15-30 fast tests (per spec §9.1)
- **Cumulative: +45-90 fast tests** (smaller than Phase 12 Sub-bundle C's +494 cumulative because (a) no schema work; (b) 2 sub-bundles not 4; (c) bounded architectural surface).

Per the Phase 9/10/12 overshoot precedent (actual typically lands in upper half of projection), **plan §E should explicitly note: actual test delta likely +50-130** based on overshoot pattern across 2 sub-bundles.

Final main HEAD post-this-dispatch-arc-merge: **~4413-4493 fast tests** (was ~4363 + +50-130).

### §2.5 V2 candidates explicitly carried forward

Plan §Z (or housekeeping section) enumerates V2 candidates banked from brainstorm + writing-plans:

1. **V2 multi-leg tier-1 auto-redirect from tier-2 `multi_partial_vs_consolidated` → tier-1 `split_into_partials`** (spec §6.6 OQ-F V2 follow-up dispatch candidate).
2. **Per-row `engine_version` metadata column on `reconciliation_corrections`** (requires schema v20; spec §8.3 V2 candidate; would enable per-row context-rendering in `show-correction` help text instead of generic addendum).
3. **`/config?schwab_setup=ok` hard removal** (passive no-op retained one release window per Codex R1 m#2; banked V2 after one release demonstrates zero stale-tab traffic).
4. **Per-leg audit surfacing for tier-2 outside-tolerance VWAP** (currently V1 ships one tier-1 emit per outside-tolerance VWAP comparison; per-leg detail lives in `actual_value_json.execution_legs` audit-only; spec §9.2 V2 candidate).
5. **Schwab cassette runbook elevation** (V2-PLANNED per Phase 11 D CLAUDE.md gotcha; this dispatch ships the runbook as part of Sub-bundle 1 cassette-recording session — V2 candidate is to elevate the runbook to a first-class doc + scale to more order types beyond 4).
6. **`surface='web'` enum widening** (Sub-bundle B V2 candidate; Sub-bundle 2 uses `surface='cli'` for `/schwab/status` audit attributions per Sub-bundle B precedent).
7. **schwabdev SDK version pin + extended compat test** (Sub-bundle B V2 candidate; banked).
8. **Schwab token encryption-at-rest** (Sub-bundle B V2 candidate; banked).

---

## §3 OUT OF SCOPE (do not do)

- **Schema changes / migration v19→v20** — spec §1.3 lock. If plan author surfaces a need, STOP + escalate to orchestrator.
- **Code drafting.** Plan provides per-task acceptance criteria; does NOT write code (other than illustrative sketches at task acceptance criteria level).
- **Re-litigating spec §1 binding constraints** — accepted as given. Operator-locked.
- **V2 multi-leg tier-1 auto-redirect** (spec §6.6 OQ-F V2 follow-up dispatch).
- **Web Tier-2 discrepancy-resolution surface** (Sub-bundle C plan §I.3 V2 candidate).
- **schwabdev SDK upgrade or token encryption-at-rest** (Sub-bundle B V2 candidates).
- **Fill auto-population at trade-entry time** (Sub-bundle C §1.6 separate sub-bundle).
- **Re-deriving ~60 cumulative forward-binding lessons** — accept as given; plan §0.4 inheritance.
- **Mocked-only fallback path drafting** — OQ-E operator-decided cassette-required default; mocked-only NOT-elected.
- **Standalone Sub-bundle 3** — operator-decided FOLD INTO Sub-bundle 1.
- **Pass-2 LIFT** — spec §1.5 V1 LIFT scope = Pass-1 only; Pass-2 LIFT entirely deferred V2.
- **Magnitude-based threshold gating** — spec §1.1 lock #6 inheritance.

---

## §4 Binding conventions

- **Branch:** `main`. Single commit OR landing+fixes split per Phase 9/10/12 writing-plans precedent.
- **Commit message:** `docs(post-phase12): Schwab mapper execution-grain widening + T-B.7 writing-plans plan`. **No Claude co-author footer** (per CLAUDE.md binding convention + Phase 12 C.B forward-binding lesson #7 explicit suppression citation; brainstorm chain held the line for 3rd time across 6 commits — pattern is durable). No `--no-verify`. No amending.
- **Plan format:** mirror `docs/superpowers/plans/2026-05-15-phase12-bundle-C-auto-correct-reconciliation-plan.md` (Phase 12 Sub-bundle C plan canonical; 3621 lines for arc-scale dispatch) OR `docs/superpowers/plans/2026-05-13-phase10-metrics-dashboard-plan.md` (Phase 10; 2008 lines). Section-numbered; locked decisions called out explicitly with rationale; per-task acceptance criteria explicit; per-sub-bundle gate plan explicit. Plan should be SMALLER than both precedents because bounded scope + no schema work.
- **Plan line target:** ~1100–1700 lines.
- **Adversarial review:** mandatory; iterate to `NO_NEW_CRITICAL_MAJOR`. **Budget 4-5 rounds** (smaller plan than Phase 12 Sub-bundle C 3621-line plan / Phase 9 2257-line plan; convergent chain expected per brainstorm lesson #1 above).

---

## §5 Adversarial review watch items (writing-plans-phase specific)

For Codex rounds — pass these as targeted prompts to `copowers:adversarial-critic`:

1. **Spec §13 25-item LOCKED inheritance integrity.** Plan §A enumerates each item + maps to per-task acceptance criteria. No item silently dropped or relaxed.
2. **OQ-E cassette-required LOCK honored.** Plan §F drafts the cassette runbook + sanitization filter spec; plan §G specifies cassette acceptance criteria; plan §H Sub-bundle 1 gate enumerates cassette session as a HARD PREREQ.
3. **OQ resolutions honored.** OQ-A Path B; OQ-B VWAP V1; OQ-C `price_tolerance=0.01`; OQ-D Path A; OQ-F V2; OQ-G leave-as-is + generic CLI addendum. Spec recommendation preserved per OQ.
4. **§0.5 12 pre-verifications completed BEFORE plan drafting.** Plan §A.0 enumerates each pre-verification + verbatim grep results. Especially: `swing/integrations/schwab/mappers.py:175-242` mapper body confirms order-grain extraction (lines 223-230); `swing/trades/schwab_reconciliation.py:693` comparator confirms `abs(so.price - float(f.price)) > price_tolerance`; `swing/trades/reconciliation_classifier.py:155-215` confirms Shape A + Shape B predicates; Schwab API spec at lines 1791-1800 confirms `executionLegs[]` field shape.
5. **No schema work.** Plan proposes NO `CREATE TABLE`/`ALTER TABLE`/`0020_*.sql` migration. Confirm: `EXPECTED_SCHEMA_VERSION` stays at 19; no migration file added; no schema dataclass changes (other than greenfield `SchwabExecutionLeg` package-level dataclass).
6. **Shape C predicate as a SEPARATE task with discriminating tests.** Plan §A.1.8 task includes 4-case parametrize: Shape A preserved (Sub-bundle C.B tests still pass); Shape B preserved (Sub-bundle C.B tests still pass); Shape C newly recognized (V2-specific test); mixed/partial Shape C → tier-2 (defense-in-depth determinism principle).
7. **V1 LIFT scope = Pass-1 only LOCK preserved.** Plan §A.1.9 task locks `_classify_unmatched_fill_shared` widening to ONLY add Path B `execution_unavailable=true` sentinel recognition. Pass-2 full LIFT entirely deferred per spec §6.6 LOCK. Discriminating test: re-run Sub-bundle C.B's Pass-2-tier-1-FORBIDDEN parametrized test (6 distinct input shapes) + assert it still PASSES post-Sub-bundle-1 — Pass-2 LIFT not enabled.
8. **Quantity-grain switch separate task from price-grain switch.** Plan §A.1.5 (`_resolve_match_quantity`) and §A.1.7 (comparator quantity-match switch) are separate tasks from §A.1.4 (`_compute_execution_price`) and §A.1.6 (comparator price-match switch). Codex R1 M#2+M#3 caught this; plan reaffirms separation.
9. **Mapper coherence-check distinguishes legitimate partial fills from malformed leg totals.** Plan §A.1.3 task includes 2-case discriminating test: `sum(legs.quantity) == order.filledQuantity` → `executions` preserved; `sum(legs.quantity) != order.filledQuantity` → `executions=None` collapse + comparator Path B fall-through. Per Codex R1 M#2 LOCK.
10. **Backward-compat fall-through = Path B (tier-2 unsupported) per spec §6.1 OQ-A LOCK.** Plan §A.1.6 task includes discriminating test for both branches: `orderActivityCollection` present → comparator uses execution-grain; missing/empty → comparator emits `unmatched_open_fill`/`unmatched_close_fill` with `execution_unavailable=true` sentinel → classifier tier-2 `unsupported`. Per spec §6.1 + §5.2 LOCK.
11. **HTMX trinity preservation for Sub-bundle 2** (HX-Request propagation; HX-Redirect-vs-303-swap; HX-Redirect-target-unrouted). Plan §A.2.5 task pins all 3 with regression tests.
12. **`apply_overrides(cfg)` discipline at Sub-bundle 2 entry point.** Plan §A.2.1 task includes integration test asserting `/schwab/status` route handler invokes `apply_overrides(cfg)` BEFORE consuming `cfg.integrations.schwab.environment` (per Phase 12 Sub-bundle B forward-binding lesson #6 + Codex R1 Critical #1 fix at `e418d56`).
13. **Phase 10 base-layout VM banner pin** (Phase 10 Sub-bundle E T-E.3). Plan §A.2.0 task includes test asserting `SchwabStatusVM.unresolved_material_discrepancies_count` field populated; banner predicate widening from Phase 12 Sub-sub-bundle C.D (`'pending_ambiguity_resolution'` widening) inherited via `BaseLayoutVM` mixin.
14. **CLAUDE.md gotcha amendment text completeness** (T-1.10). Plan §A.1.10 task includes acceptance criterion: amendment preserves V1 historical context (CVGI + LION 2026-05-17 falsification evidence + 3 orchestrator-inline gate-fix instances + Pass-2-FORBIDDEN family); adds NEW V2-RESOLVED top-section; references the V2 mapper widening dispatch + this spec + commit chain (initial `8c1e5cb` through Codex-R5 `dda8730`).
15. **CVGI date typo verification no-op-with-note** (T-1.11). Plan §A.1.11 task acceptance criterion: grep CLAUDE.md at task time; if zero matches (confirmed at brainstorm + brief drafting), task is a no-op with note in commit message; if matches found (regression since brief), fix-on-the-fly.
16. **Generic ID-free `show-correction` CLI help-text addendum mechanic** (T-1.12; OQ-G operator-decided). Plan §A.1.12 task includes acceptance criterion: addendum works on ANY DB (no per-row IDs); cites spec path + V1 limit-vs-fill historical context; renders via `--help` flag.
17. **Cassette session prereq routing into Sub-bundle 1 executing-plans dispatch brief §0 LOCK.** Plan §F + §G + §H confirm the cassette session as a HARD PREREQ; plan provides the runbook + acceptance criteria; orchestrator routes the cassette ship into the executing-plans dispatch brief.
18. **Sub-bundle 2 `/schwab/setup` HX-Redirect retargeting + `/config?schwab_setup=ok` consumer retention** (Codex R1 m#2 LOCK). Plan §A.2.4 task: Sub-bundle 1's `/schwab/setup` POST handler retargeted to `HX-Redirect: /schwab/status`; `/config?schwab_setup=ok` consumer retained as passive no-op for one release window; V2 banked for hard removal.
19. **NO behavioral changes to NON-touched existing surfaces.** Plan modifies the touch list in §1.2 above + NO other production files should change. Codex SHOULD verify the touch surface is bounded; especially: `stop_mismatch` path at `swing/trades/schwab_reconciliation.py:_find_working_stop_for_ticker` UNCHANGED (spec §1.1 lock #2).
20. **Plan-author schema additions during writing-plans cycle (Sub-bundle C.A return report lesson #7 inheritance).** If plan author surfaces a need for a schema element NOT in spec §3 + §1.3 (e.g., new audit column; new CHECK enum value; new FK relationship), STOP + escalate to orchestrator BEFORE encoding inline. Cost of bank-after-write: 2-3 cascade-cleanup rounds.
21. **Operator-actionability test.** Each operator-facing surface (Sub-bundle 1 cassette runbook section; T-1.12 `show-correction` CLI help-text; T-1.10 CLAUDE.md amendment; Sub-bundle 2 `/schwab/status` page) answers: "what action does the operator take?" Each surface's help text + error messages + usage examples are operator-actionable.
22. **Brief-premise empirical-verification (lesson #2 inheritance).** Plan §A.0 pre-verification list greps shipped surfaces BEFORE locking per-task acceptance criteria. Any divergence between spec §3 + §4 + §5 + §7 and shipped code is FLAGGED in plan §A.0 as a brief-vs-shipped-code deviation.
23. **Per-row policy stamping (Phase 8 R1 M5 inheritance)** — N/A V1 (no new `reconciliation_corrections` rows emitted by Sub-bundle 1; the comparator/classifier shift emits FEWER false-positive discrepancies than V1, not more — V1's `risk_policy_id_at_correction` stamping discipline at C.A T-A.4 preserved unchanged).
24. **Datetime impedance + lexicographic ordering** — N/A V1 (no new TEXT timestamp fields added; `SchwabExecutionLeg.time` field reuses Schwab API's ISO 8601 string format without writes to journal).
25. **Convergent-chain expectation.** Codex round count likely 4-5; chain shape matters more than count. Implementer's return report documents fix-introduced regression vs adversarial-thrash distinction.

---

## §6 Done criteria

1. Plan at `docs/superpowers/plans/2026-05-17-schwab-mapper-execution-grain-widening-plan.md` covering §2.1–§2.5.
2. Per-sub-bundle task decomposition (Sub-bundle 1: ~10-14 tasks; Sub-bundle 2: ~5-7 tasks; total ~15-21 tasks).
3. Each task has: scope + acceptance criteria + discriminating-test patterns + files-touched + tests-added projection + commit message stem.
4. §H per-sub-bundle gate plan (Sub-bundle 1: 7-9 surfaces; Sub-bundle 2: 4-5 surfaces; total 11-14 gate surfaces).
5. §A.0 pre-verifications all completed against shipped code with verbatim grep results.
6. §F + §G cassette runbook + acceptance-criteria sections drafted.
7. Writing-plans went through ≥3 Codex rounds reaching `NO_NEW_CRITICAL_MAJOR` (target 4-5 rounds per smaller-plan-than-arc-scale lesson).
8. Single commit OR landing+fixes split: `docs(post-phase12): Schwab mapper execution-grain widening + T-B.7 writing-plans plan` (+ optional `docs(post-phase12): plan — Codex R1-R<N> fixes`).
9. Return report covers items in §7.

---

## §7 Return report format

```
## Return report — Post-Phase-12 Schwab mapper execution-grain widening writing-plans

### Plan location
`docs/superpowers/plans/2026-05-17-schwab-mapper-execution-grain-widening-plan.md` ({line count} lines)
Commits on main:
- {sha} `docs(post-phase12): Schwab mapper execution-grain widening + T-B.7 writing-plans plan` (initial)
- (optional) {sha} `docs(post-phase12): plan — Codex R1-R<N> fixes` (post-review)

### Codex review history
- R1: {C/M/m findings; verdict; FIXED/ACCEPTED counts}
- R2: ...
- ...
- Final verdict: NO_NEW_CRITICAL_MAJOR

### Three highest-leverage planning decisions
1. ...
2. ...
3. ...

### Per-sub-bundle task count + projected test deltas
- Sub-bundle 1: {N} tasks; +{X}..+{Y} fast tests
- Sub-bundle 2: {N} tasks; +{X}..+{Y} fast tests
- Cumulative: +{X}..+{Y} fast tests; matches §0.4 lesson #1 + spec §9.1 projection

### §13 25-item LOCKED inheritance triage outcomes
[Per-item plan-author posture; default-recommendation-accepted vs orchestrator-escalated]

### §0.5 12 pre-verification outcomes (all completed)
[Per-pre-verification: grep result + verbatim shipped surface confirmed OR divergence flagged]

### Brief-vs-shipped-code deviations flagged (per lesson #2 inheritance)
- ...

### Sub-bundle dispatch order locked
Cassette session → Sub-bundle 1 → Sub-bundle 2
With per-bundle cross-bundle pins enumerated

### Operator-witnessed gate plan summary (per §H)
- Sub-bundle 1: 7-9 surfaces
- Sub-bundle 2: 4-5 surfaces

### Cassette runbook + acceptance criteria summary (per §F + §G)
- 4 order types minimum (LIMIT BUY + LIMIT SELL + STOP FIRED + MARKET BUY); stretch STOP_LIMIT FIRED
- Sanitization filter spec
- Storage path
- Staleness recovery runbook

### V2 candidates banked (per §2.5)
- ...

### Open questions for orchestrator triage (if any escalated past spec §13 + brief §0.3)
- ...

### Forward-binding lessons for executing-plans dispatches
- ...
```

---

## §8 If you get stuck

- If spec §1 binding constraints conflict with a planning approach, §1 wins; flag as open question.
- If a Codex round produces a finding you can't disposition without orchestrator input, ACCEPT-with-rationale + flag explicitly in plan's "open questions" section + return report.
- If the plan exceeds ~1700 lines, re-scope (smaller than Phase 12 Sub-bundle C's 3621-line plan / Phase 9's 2257-line plan by design — bounded scope + no schema work).
- DO NOT propose schema changes within this dispatch's scope (§1.1 lock #3 + §3).
- DO NOT propose Pass-2 LIFT within this dispatch's scope (spec §1.5 lock).
- DO NOT propose mocked-only fallback as default path (OQ-E operator-decided cassette-required).
- DO NOT propose web Tier-2 surface within this dispatch's scope (Sub-bundle C plan §I.3 V2 candidate).
- DO NOT propose magnitude-based threshold gating (spec §1.1 lock #6 inheritance).
- If you encounter a Phase 7/8/9/10/11/12-A/12-B/12-C lesson that conflicts with a planning proposal, the prior-phase lesson wins (validated by ship-experience). Surface the conflict as a planning constraint.
- If you find yourself proposing retroactive `reconciliation_corrections` rewriting, STOP — spec §1.1 lock #4 violated.
- If you find yourself proposing OQ-F V2 auto-redirect inline within Sub-bundle 1, STOP — spec §6.6 V2 LOCK.
- If the cassette runbook surfaces a need for schwabdev SDK upgrade, STOP — Sub-bundle B V2 candidate; out of scope.

---

*End of brief. Writing-plans phase for post-Phase-12 Schwab mapper execution-grain widening + T-B.7 + housekeeping (FOLDED INTO Sub-bundle 1). Plan output target: `docs/superpowers/plans/2026-05-17-schwab-mapper-execution-grain-widening-plan.md`. Expected duration ~5-10hr including 4-5 Codex rounds. Schema unchanged (v19); 2 sub-bundles sequential (1 then 2); cassette session HARD PREREQ for Sub-bundle 1; operator decisions locked 2026-05-17 (OQ-E cassette-required default; sequential ordering; Sub-bundle 3 fold).*
