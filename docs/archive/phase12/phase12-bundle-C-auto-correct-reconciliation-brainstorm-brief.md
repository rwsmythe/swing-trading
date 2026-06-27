# Phase 12 Sub-bundle C — Auto-Correct Journal-from-Schwab Reconciliation Brainstorm — Implementer Brief

**Audience:** Fresh Claude Code instance dispatched as the Phase 12 Sub-bundle C brainstorm implementer. No prior conversation context.

**Mission:** Produce a design spec for Phase 12 Sub-bundle C — the architectural pivot that replaces the current Phase 9 + Phase 11 "emit reconciliation discrepancies for operator-triage" loop with a three-tier resolution model: (tier 1) **unambiguous auto-correct** of journal-from-Schwab; (tier 2) **ambiguity surfaced for operator decision** with type-specific resolution choices; (tier 3) **rare operator override** of an applied tier-1 correction. Schwab data IS truth when available. Brainstorm IS schema-locking + service-architecture-locking (writing-plans depends on locked classifier + auto-correction module + audit-history table + Tier-2 surface contracts).

**Brief:** `docs/phase12-bundle-C-auto-correct-reconciliation-brainstorm-brief.md` (this file).

**Sequencing:** Phase 12 Sub-bundle A SHIPPED 2026-05-15 at `123d27a` (operational-pain mini-bundle: env vars + setup self-healing + pipeline env-var wiring + cleanup-script regex). Phase 12 Sub-bundle B SHIPPED 2026-05-15 at `b09eb06` (web-UI-friendliness: credentials-in-file cfg-cascade + web OAuth paste-back form Outcome B; 12 forward-binding lessons banked for THIS dispatch). Sub-bundle C scope is the architectural pivot banked at `28a7d01` + `75b876c` after operator pushback on the operator-action triage loop during 12A's gate.

**Expected duration:** 150–300 minutes including 4–6 adversarial Codex rounds. Sub-bundle C has the largest design surface of Phase 12 (new audit table + ambiguity classifier + auto-correction service + Tier-2 surface + reconciliation flow pivot + backfill path). Convergent chain shape per Phase 7 Sub-B + Phase 8 R2-R5 + Phase 9 brainstorm lesson family — budget 5–6 rounds.

---

## §0 Read first

In this order:

1. **`CLAUDE.md`** at repo root — project conventions + gotchas. Especially the 12 Schwab gotchas added at Sub-bundle D T-D.4 (token redaction, sandbox short-circuit gating, source-artifact reference shape, schwabdev camelCase kwarg discipline, etc.) + the 2 new gotchas from Sub-bundle B (Schwab OAuth web setup flow; CLIENT_ID + CLIENT_SECRET storage) + the architectural-pushback / operator-action-loop framing notes embedded in the status line.
2. **`docs/orchestrator-context.md`** sections "Currently in-flight work" + "Recent decisions and framings" + "Lessons captured" — the LAST section has the THREE most-load-bearing-for-this-dispatch lessons: (a) **operator architectural pushback supersedes orchestrator scope assumptions; reframe before bandaging** (the lesson that produced this dispatch); (b) **once operator-witnessed gate passes, integration merge is orchestrator action**; (c) **operator-paired-gate-caught implementation gap → orchestrator-inline gate-fix (3 instances)**. Plus all 22+12 cumulative Schwab-arc forward-binding lessons (Phase 11 A 5 + B 7 + C 5 + D 0; Phase 12 A 5 + B 12 = **34 total**).
3. **`docs/phase3e-todo.md`** top entries 2026-05-15 in TOP-DOWN order:
   - **Phase 12 Sub-bundle B SHIPPED entry** (just-shipped; 10 V2 candidates + 12 forward-binding lessons for THIS dispatch).
   - **ARCHITECTURAL: reconciliation must auto-correct journal-from-Schwab** entry at `28a7d01` + `75b876c` (Sub-bundle C HEADLINE — read end-to-end; spec §1 binding constraints inherit verbatim).
   - **Phase 12 Sub-bundle A SHIPPED entry** (just-shipped predecessor).
   - **Phase 11 CLOSED entry**.
4. **`docs/superpowers/specs/2026-05-06-phase9-risk-policy-reconciliation-design.md`** — Phase 9 spec; the reconciliation_runs + reconciliation_discrepancies tables this dispatch consumes + pivots. Read §3 (reconciliation framework) + §10 (lifecycle integration) end-to-end.
5. **`swing/trades/reconciliation.py`** + **`swing/data/repos/reconciliation.py`** — current `run_tos_reconciliation` + `run_schwab_reconciliation` service helpers + repo. The "emit + wait" loop lives here; this dispatch designs the "classify + dispatch + apply" pivot at the same call site.
6. **`swing/integrations/schwab/marketdata_ladder.py`** + **`swing/integrations/schwab/trader.py`** — Phase 11 Sub-bundle C + B Schwab API surfaces. Sub-bundle C's auto-correction service consumes these for tier-1 "Schwab is truth" data fetches.
7. **`swing/data/repos/fills.py`** + **`swing/data/repos/trades.py`** + **`swing/trades/entry.py`** + **`swing/trades/exit.py`** + **`swing/trades/stop_adjust.py`** — the WRITE surfaces the auto-correction service uses to correct journal-from-Schwab. Phase 7 fills validators + Phase 6 review_log freezing rules apply.
8. **`swing/data/migrations/0018_schwab_api_calls.sql`** + **`0017_phase9_risk_policy_reconciliation.sql`** + **`0014_phase7_state_machine_and_fills.sql`** — already-shipped schemas. Don't propose anything that conflicts.
9. **Production state evidence** — **discrepancies 39 (DHC unmatched_open_fill), 40 (VSAT unmatched_open_fill), 41 (CVGI entry_price_mismatch)** are the 3 unresolved-material live cases. CVGI 41 is the canonical tier-1 example; DHC 39 is the canonical tier-2 `multi_partial_vs_consolidated` example. **Spec MUST work through each of these three cases end-to-end** as discriminating examples for the classifier + auto-correction service.
10. **One prior brainstorm spec for format reference** — `docs/superpowers/specs/2026-05-06-phase9-risk-policy-reconciliation-design.md` (mirror its section-numbered + locked-decisions-vs-open-questions structure; its §3 reconciliation framework + §10 lifecycle integration patterns are reusable; Phase 9 used 1090 lines for 5 new tables — Sub-bundle C target is ~800-1300 lines for 1 new table + classifier + service + Tier-2 surface + flow pivot + backfill path).

---

## §0 Skill posture

- Invoke **`copowers:brainstorming`** (which wraps `superpowers:brainstorming` with adversarial Codex review). Iterate to `NO_NEW_CRITICAL_MAJOR`.
- DO NOT invoke `superpowers:writing-plans` — schema sketches + service-architecture sketches are NOT plan tasks.
- DO NOT invoke `superpowers:executing-plans` — design-only.
- DO NOT invoke `superpowers:test-driven-development` — no code changes.
- DO NOT invoke `superpowers:using-git-worktrees` — no code changes; spec doc commit only.

---

## §1 Strategic context (ORCHESTRATOR-DISTILLED + OPERATOR-LOCKED — do NOT re-litigate)

The following are accepted as **BINDING design constraints**. Operator-locked during 2026-05-15 architectural-pushback conversation. If a Codex round produces a finding that contradicts §1, do NOT relax §1 — instead enumerate it as an open question for orchestrator triage and continue.

### §1.1 Operator-locked architectural framing (DO NOT re-litigate)

1. **Schwab data IS truth.** When Schwab API responses are available + the call succeeded, the journal must converge TO Schwab, not the other way around. The current `acknowledged_immaterial` operator-triage loop bypasses validators + treats journal as authoritative — this is the architectural anti-pattern.
2. **Three-tier resolution model.**
   - **Tier 1 — unambiguous auto-correct (most common):** classifier identifies single journal fill + single Schwab record + single field differs + clear target value. System auto-corrects journal to match Schwab + writes audit row. ZERO operator involvement.
   - **Tier 2 — ambiguity surfaced for operator decision (operationally important):** classifier identifies mismatch but cannot deterministically resolve (e.g., Schwab shows multiple partial fills + journal has single consolidated entry; multiple Schwab transactions could match same journal fill within window; Schwab data shape doesn't fit existing journal schema). Surfaced with **structured `ambiguity_kind` enum** + **type-specific resolution choices** for operator. Operator picks → service auto-applies + audits.
   - **Tier 3 — rare operator override (edge case):** operator has ground-truth knowledge that Schwab itself is wrong (broker error; reporting glitch). Operator marks an applied tier-1 correction as `operator_overridden` + provides ground-truth value + reason. Audit chain preserves all three values: pre-correction journal / Schwab-said / operator-override.
3. **Magnitude is the WRONG axis.** Determinism is the axis. `$0.07` is not "small"; the question is whether the correction is deterministic, not whether the delta is big. NO magnitude-based auto-vs-surface threshold gates.
4. **`acknowledged_immaterial` enum value stays as back-compat** for the SPECIFIC narrow case where operator has tier-3 ground-truth-Schwab-is-wrong knowledge. New discrepancies use new resolution enum values: `auto_corrected_from_schwab` / `pending_ambiguity_resolution` / `operator_resolved_ambiguity` / `operator_overridden`. Existing `acknowledged_immaterial` resolutions in production (30 of them as of 2026-05-15) do NOT need backfill rewriting — they predate Sub-bundle C semantics.

### §1.2 Concrete current-state evidence (3 unresolved discrepancies; classifier discriminating examples)

Production state at dispatch time (per `swing schwab status --environment production` 2026-05-15):

- **disc 41 CVGI entry_price_mismatch:** journal `fills.fill_id=9` price=$5.23 × N shares on entry date D, Schwab=$5.30, delta `+$0.07`. **Likely `auto_correctable` (tier 1):** single journal fill matches single Schwab transaction by (ticker, date, qty); only `price` field differs; clear target = $5.30. System sets journal price to $5.30 + writes audit row + done. NO operator involvement.
- **disc 39 DHC unmatched_open_fill:** journal `fills.fill_id=2` entry @$7.58 × 39 on 2026-04-27, Schwab `actual={"matched": null}`. **Likely `ambiguous` (tier 2) with `ambiguity_kind=multi_partial_vs_consolidated`:** Schwab almost certainly has partial fills (e.g., 20 + 19 at slightly different prices); journal has single consolidated row. Operator picks split-into-partials / keep-consolidated-use-Schwab-VWAP / keep-journal-as-is-mark-aggregation-acknowledged / operator-custom.
- **disc 40 VSAT unmatched_open_fill:** journal `fills.fill_id=6` entry @$65.69 × 2 on 2026-05-06, `manual_entry_confidence='low'` (operator flagged uncertain at entry), Schwab `actual={"matched": null}`. **Classification per-row:** either `ambiguous` (`multi_partial_vs_consolidated` if Schwab split entry) OR `auto_correctable` (if Schwab has single fill at slightly different price/qty). The classifier must distinguish on actual Schwab payload.

**All three fills** carry `reconciliation_status='unreconciled'` + `tos_match_id=NULL` — they were operator-typed-from-memory + never linked to a Schwab/TOS source record at entry time. These cases drive §2.2 classifier design + §2.7 backfill path; spec MUST work each example through the proposed classifier end-to-end as a discriminating walkthrough.

### §1.3 Binding integrations

Sub-bundle C consumes shipped Phase 6 + Phase 7 + Phase 9 + Phase 11 + Phase 12 Sub-bundle A/B surfaces:

- **`reconciliation_runs` (Phase 9):** current state machine `(created → running → completed/failed)`. Sub-bundle C extends to support post-completion classification + tier-1 application (does the run gain new states `classified` / `auto_applied` / etc.? OR is classification a sibling table linked via FK? Brainstorm decides.)
- **`reconciliation_discrepancies` (Phase 9):** current `resolution_action` enum is `('unresolved', 'acknowledged_immaterial', 'journal_corrected', 'mistake_corrected')`. Sub-bundle C adds: `('auto_corrected_from_schwab', 'pending_ambiguity_resolution', 'operator_resolved_ambiguity', 'operator_overridden')`. Schema v19 migration to widen the CHECK enum.
- **`fills.reconciliation_status` (Phase 7):** current enum `('unreconciled', 'reconciled')`. Sub-bundle C MAY widen (`auto_matched`, `auto_corrected_from_schwab`, etc.) — brainstorm decides if widening adds value over per-discrepancy resolution_action.
- **`schwab_api_calls` (Phase 11):** audit table for Schwab API invocations. Sub-bundle C's auto-correction service may emit new audit rows when it fetches Schwab data to verify the tier-1 correction. Source-artifact reference shape locked at `schwab_api:call/{call_id}`.
- **Phase 7 fills validators (`swing/data/repos/fills.py`):** auto-correction MUST preserve invariants. If the tier-1 correction would violate a validator (e.g., negative quantity, missing FK), classifier MUST downgrade to tier-2 with an explanatory `ambiguity_kind`.
- **Phase 6 review_log freezing (`swing/data/repos/review_log.py`):** if a closed trade's fill is auto-corrected post-review, does the review_log row's frozen aggregates UN-freeze? OR retain frozen-then-mark-superseded pattern (per Phase 8 `is_superseded` flag lesson)? Brainstorm decides.
- **Phase 8 daily_management_records (`swing/data/repos/daily_management.py`):** snapshot rows that recorded position state at a session may diverge from auto-corrected journal post-Sub-bundle-C. Brainstorm decides whether snapshots need post-correction adjustment OR retain as historical record.
- **Phase 11 Sub-bundle C marketdata + Sub-bundle B trader endpoints:** Schwab API surfaces the auto-correction service consumes for tier-1 truth-fetching. Sandbox short-circuit gating MUST be preserved (CLAUDE.md gotcha).
- **Phase 12 Sub-bundle B cfg-cascade:** credentials resolved via `apply_overrides` at all 5 Schwab entry points. Sub-bundle C auto-correction service is a 6th entry point if it constructs `schwabdev.Client(...)` directly — single-Client-instance discipline + `apply_overrides` discipline both apply.

### §1.4 Apply existing DROP rules

Inherits from prior phases — no new DROP rules unique to Sub-bundle C. Specifically:

- **No magnitude-based threshold** (operator §1.1 lock).
- **No re-litigating Schwab-truth premise** (operator §1.1 lock).
- **No Phase 7 state-machine extension beyond enum widening** (Phase 9 lesson: query-side JOIN over schema flag where grain mismatches). If auto-correction surfaces require new trade states, surface as open question — don't pre-decide.

### §1.5 Sub-sub-bundle decomposition expectation

Sub-bundle C is expected to decompose into 3-4 sub-sub-bundles for executing-plans. Brainstorm should propose a tentative decomposition for writing-plans to refine; writing-plans locks. Likely shape:

- **Sub-sub-bundle C.A — Foundation:** new audit-history table (OR `event_log` extension; brainstorm decides) + `resolution_action` enum widening + `reconciliation_runs` state extension if needed + schema migration v18 → v19. Ships first.
- **Sub-sub-bundle C.B — Ambiguity classifier:** the `auto_correctable` / `ambiguous` / `unsupported` classifier with structured `ambiguity_kind` enum. Pure logic; consumes Phase 11 Schwab API responses. Ships second.
- **Sub-sub-bundle C.C — Auto-correction service (tier 1 only) + reconciliation flow pivot:** the transactional service-layer module that consumes classifier output + applies tier-1 corrections + emits audit rows. Refactors `run_schwab_reconciliation` from "emit + wait" to "classify + dispatch + apply". Ships third.
- **Sub-sub-bundle C.D — Tier-2 ambiguity-resolution UI/CLI + backfill path:** operator-facing surface for tier-2 resolution choices + one-time classifier sweep over existing unresolved discrepancies (39/40/41 + any future). Tier-2 surface scope (CLI-only V1 vs web-from-start) is brainstorm open question. Ships fourth.

Brainstorm refines this decomposition — output goes into writing-plans as input.

### §1.6 Fill auto-population at trade-entry time — OUT OF SCOPE for Sub-bundle C (separate sub-bundle)

Per `docs/phase3e-todo.md` ARCHITECTURAL entry §"Fill auto-population at trade-entry time": creating fills directly from Schwab Trader API responses at trade-entry handler time (instead of operator-typing-from-memory) closes the entire discrepancy stream as a CATEGORY (not one-at-a-time). **Operator-locked decision (handoff brief Step 8 #6):** this is a SEPARATE sub-bundle worth scoping at brainstorm. Brainstorm should:

1. Acknowledge this scope as separate from Sub-bundle C.
2. Identify the schema + service interfaces Sub-bundle C ships that make the future "fill auto-population at entry" sub-bundle clean to layer on top.
3. Flag any Sub-bundle C decisions that would foreclose or complicate the future "fill auto-population" sub-bundle.

DO NOT design fill auto-population in this brainstorm. DO NOT propose schema changes for it. The Tier-2 ambiguity-resolution surface designed in §2.4 is the analog for retroactive cases; auto-population at entry is the prospective analog and lives in a separate sub-bundle.

---

## §2 Brainstorm scope (in scope)

Produce a design spec at `docs/superpowers/specs/<YYYY-MM-DD>-phase12-bundle-C-auto-correct-reconciliation-design.md` covering:

### §2.1 — Schema design (NOT migration SQL; that's writing-plans)

For each schema change proposed:

- **New table OR existing-table extension** + columns (type + nullability + CHECK constraints + FK relationships) + indexes (which queries each supports; expected cardinality) + retention policy.

Likely changes (brainstorm refines):

- **Audit-history table** (NEW; OR extension of existing `event_log`/`trade_events`) — preserves pre-correction journal values + Schwab-said values + correction action + timestamp. Forensic trail. Brainstorm decides table-vs-extension. Recommend: NEW table `reconciliation_corrections` linked to `reconciliation_discrepancies.discrepancy_id` + `fills.fill_id` (or `trades.trade_id` / `cash_movements.movement_id`) for the forensic trail.
- **`reconciliation_discrepancies.resolution_action`** enum widening: existing `('unresolved', 'acknowledged_immaterial', 'journal_corrected', 'mistake_corrected')` + new `('auto_corrected_from_schwab', 'pending_ambiguity_resolution', 'operator_resolved_ambiguity', 'operator_overridden')`. CHECK constraint widening.
- **`reconciliation_discrepancies.ambiguity_kind`** NEW column (TEXT NULL). CHECK enum populated by classifier when `resolution_action='pending_ambiguity_resolution'`. Suggested values: `('multi_partial_vs_consolidated', 'multi_match_within_window', 'unknown_schwab_subtype', 'field_shape_incompatible', 'schwab_returned_no_match', 'validator_rejected', 'unsupported')`.
- **`reconciliation_runs` state machine extension?** Current `('created', 'running', 'completed', 'failed')`. Does Sub-bundle C need `('classified', 'tier1_applied')` post-completion states? OR is classification a sibling table linked by FK without state-machine extension? Brainstorm picks.
- **`fills.reconciliation_status`** enum widening (optional; brainstorm decides if it adds value).

Schema version target: v18 → v19 (single migration in C.A foundation sub-sub-bundle).

### §2.2 — Ambiguity classifier design

For each detected discrepancy emitted by `run_tos_reconciliation` / `run_schwab_reconciliation`:

- **Input contract:** classifier receives a `reconciliation_discrepancies` row + the source-side Schwab payload (or TOS payload) + the journal-side row(s) referenced.
- **Output contract:** `(tier: int, ambiguity_kind: str | None, correction_target: dict | None)` where:
  - `tier=1` → `ambiguity_kind=None` + `correction_target={field: target_value, ...}` (deterministic).
  - `tier=2` → `ambiguity_kind` populated + `correction_target=None` (operator must pick).
  - `tier=3` → unreachable from classifier (operator-initiated post-tier-1).
- **Discriminating examples (BINDING):** work each of disc 39 / 40 / 41 through the classifier end-to-end:
  - CVGI 41 → tier 1, `correction_target={'price': 5.30}`.
  - DHC 39 → tier 2, `ambiguity_kind='multi_partial_vs_consolidated'`, `correction_target=None`.
  - VSAT 40 → classifier evaluates per-row based on Schwab payload (may be either tier).
- **`ambiguity_kind` enum scope:** brainstorm enumerates each value + describes when the classifier emits it + what type-specific resolution choices §2.4 surfaces. Coverage check: does the enum cover every observable case in the current 30 resolved + 3 unresolved discrepancies? If not, what does the classifier emit for an unrecognizable shape?
- **Determinism principle:** when in doubt, classify as tier-2 (ambiguous), NOT tier-1. False-positive tier-1 silently corrupts journal; false-positive tier-2 just defers to operator (no harm).
- **Validator-respecting:** if tier-1 correction would violate a Phase 7 fills validator, downgrade to tier-2 with `ambiguity_kind='validator_rejected'`.

### §2.3 — Auto-correction service architecture

New module `swing/trades/reconciliation_auto_correct.py` (or similar; brainstorm picks naming) with:

- **Transactional discipline (Phase 8 + Phase 9 lesson):** BEGIN IMMEDIATE / COMMIT / ROLLBACK; reject caller-held transactions. Single source of truth for the atomic boundary.
- **Validator chain:** Phase 7 fills validators (`swing/data/repos/fills.py`) + Phase 6 review_log invariants + Phase 9 risk_policy at-trade-time-locked references.
- **Audit emission:** writes one row to `reconciliation_corrections` (or chosen audit table) per applied tier-1 correction; updates `reconciliation_discrepancies.resolution_action='auto_corrected_from_schwab'` + sets resolved_at; updates the journal table (`fills` / `trades` / `cash_movements`) atomically.
- **Surface awareness:** consumed by pipeline (`surface='pipeline'`) + CLI (`surface='cli'`) per Phase 11 forward-binding lesson #4.
- **Idempotency:** if invoked twice on the same discrepancy_id, second call is a no-op (resolution_action already set). Audit table prevents double-write via discrepancy_id UNIQUE.

### §2.4 — Tier-2 ambiguity-resolution surface (operator-facing)

For each `ambiguity_kind` enum value, the surface MUST render:

1. **What the discrepancy is** (the field + values from journal-side + Schwab-side).
2. **What the ambiguity is** (why the classifier couldn't auto-resolve).
3. **What the resolution choices are** (type-specific).

Suggested per-kind choices (brainstorm refines):

- **`multi_partial_vs_consolidated`:** (a) Split journal into matching partials; (b) Keep consolidated + use Schwab volume-weighted avg price; (c) Keep journal as-is + mark schwab_partial_fill_aggregation_acknowledged; (d) Operator-custom value.
- **`multi_match_within_window`:** (a) Pick Schwab record #N (operator selects from listed candidates); (b) Mark journal unmatched (no Schwab record corresponds).
- **`unknown_schwab_subtype`:** (a) Acknowledge + log for code update; (b) Operator-custom value.
- **`field_shape_incompatible`:** (a) Acknowledge + log for code update; (b) Operator-custom transformation.
- **`schwab_returned_no_match`:** (a) Mark journal unmatched (Schwab has no record of this fill — possible manual entry mistake); (b) Operator-supplied source-of-truth.
- **`validator_rejected`:** (a) Acknowledge (correction would violate journal invariants; system cannot apply); (b) Operator-supplied alternative value.
- **`unsupported`:** Operator action only.

**Surface decision (open question):** CLI-only V1 (`swing journal discrepancy resolve <id> --choice <n>`) OR web-from-start (route at `/discrepancies/{id}/resolve`)? Brainstorm recommends + locks. Note Phase 12 Sub-bundle B established the web-discoverability pattern (`/config` "External integrations" section linking to `/schwab/setup`); analogous pattern would be a "Pending reconciliation ambiguities (N)" link from `/config` or dashboard if web-from-start chosen.

### §2.5 — Reconciliation flow pivot

The current `run_tos_reconciliation` + `run_schwab_reconciliation` services emit discrepancies + return — operator-triage loop. Sub-bundle C pivot:

```
run_reconciliation(source)
  → emit discrepancies (PHASE 9 BEHAVIOR PRESERVED — unchanged)
  → CLASSIFY each discrepancy via §2.2 classifier (NEW)
  → for tier-1 discrepancies: APPLY via §2.3 auto-correction service + audit (NEW)
  → for tier-2 discrepancies: SET resolution_action='pending_ambiguity_resolution' + ambiguity_kind (NEW)
  → for tier-3: unreachable at this point (operator-initiated post-tier-1)
  → return summary { matched, tier1_applied, tier2_pending, ... } (NEW shape)
```

Brainstorm specifies:

- Exactly what the pivot looks like at the call-site level.
- Failure-mode semantics: if classifier raises, what happens? If auto-correction service raises, what happens? Per Phase 11 forward-binding lesson #2 (broaden the catch at pipeline boundary), V1 graceful-degradation contract: pipeline never crashes; classifier/auto-correction failures fall through to "emit-only" Phase 9 behavior + log WARNING.
- Operator-visible CLI output: does `swing schwab fetch --all` change to surface tier-1 auto-applied count + tier-2 pending count?

### §2.6 — Backfill path

When Sub-sub-bundle C.D ships, a one-time backfill operation runs the classifier across all existing `reconciliation_discrepancies` rows where `resolution_action='unresolved'`. For each:

- **Tier-1:** auto-apply + write audit row + update resolution_action.
- **Tier-2:** set `resolution_action='pending_ambiguity_resolution'` + `ambiguity_kind` + leave for operator.
- **Tier-3:** unreachable at backfill (operator-initiated only).

**Worked examples (BINDING):**

- disc 41 CVGI → backfill auto-applies; journal `fills.fill_id=9` price field UPDATEs from $5.23 → $5.30; audit row in `reconciliation_corrections`; resolution_action='auto_corrected_from_schwab'.
- disc 39 DHC → backfill sets `resolution_action='pending_ambiguity_resolution'` + `ambiguity_kind='multi_partial_vs_consolidated'`; operator resolves via §2.4 surface.
- disc 40 VSAT → backfill classifies per-row based on Schwab payload available at backfill time.

Backfill surface (operator-initiated): CLI `swing journal reconcile-backfill --apply` (one-time). Brainstorm specifies exact CLI shape + idempotency (re-run is no-op for already-resolved discrepancies).

### §2.7 — Lifecycle integration with Phase 6 + Phase 7 + Phase 8 + Phase 9

- **Phase 6 `review_log` freezing under auto-correction:** if auto-correction modifies a fill on a closed-reviewed trade, do frozen aggregates UN-freeze? OR retain + mark via `is_superseded` (Phase 8 pattern)? Brainstorm decides.
- **Phase 7 `fills.reconciliation_status` enum:** widening adds value over per-discrepancy `resolution_action`? Brainstorm picks.
- **Phase 7 `trade_events`:** emit a new event type for tier-1 corrections? OR sufficient to log in `reconciliation_corrections` audit table? Brainstorm picks.
- **Phase 8 `daily_management_records`:** historical snapshots that disagree with auto-corrected post-correction state — retain as historical OR retroactively adjust? Brainstorm picks (recommend: retain as historical; snapshots are point-in-time observations).
- **Phase 9 `reconciliation_runs`:** state machine extension? OR sibling table tracking classification phase? (Per §2.1)

### §2.8 — Sub-sub-bundle decomposition recommendation

Brainstorm proposes a tentative decomposition (per §1.5) for writing-plans to refine. Likely shape: 4 sub-sub-bundles (foundation + classifier + service + UI/backfill). Brainstorm specifies dispatch ordering + cross-sub-sub-bundle dependencies + projected test deltas + projected line counts.

### §2.9 — Open questions for orchestrator triage

Per Phase 9 brainstorm pattern. Likely categories:

- Audit-history table-vs-`event_log`-extension decision.
- `reconciliation_runs` state machine extension vs sibling table.
- `fills.reconciliation_status` widening scope.
- Tier-2 surface CLI-only-V1 vs web-from-start.
- review_log freezing un-freeze semantics under auto-correction.
- `ambiguity_kind` enum coverage completeness.
- Backfill surface CLI shape + dry-run support.
- Failure-mode semantics on classifier/auto-correction service errors.
- Phase 11 Schwab API call audit-row attribution for backfill-time classifier fetches.

---

## §3 OUT OF SCOPE (do not do)

- **Migration SQL drafting** — that's writing-plans territory. Schema SKETCHES (column lists + CHECK semantics) are in scope; full `CREATE TABLE` SQL is not.
- **Code drafting** — service modules, view-models, query implementations, Jinja templates, route handlers, repo functions, CLI command bodies.
- **Sub-sub-bundle task-decomposition into per-task acceptance criteria** — writing-plans output. Sub-sub-bundle high-level scope is in §2.8 brainstorm-output; per-task decomposition is downstream.
- **Re-litigating §1 binding constraints** — accepted as given. Operator-locked. If a Codex round produces a finding that contradicts §1.1, flag as open question, do NOT relax §1.1.
- **Fill auto-population at trade-entry time** (§1.6) — separate sub-bundle. Sub-bundle C designs the retroactive-correction surface; prospective auto-population is the next sub-bundle.
- **Phase 11 Schwab API V2 features** — token encryption-at-rest; Option B HTTPS callback; per-env namespacing; multi-account picker; surface='web' CHECK enum widening; etc. All banked in Sub-bundle A + B V2 lists; not Sub-bundle C scope.
- **Phase 7 state-machine changes beyond enum widening** — trade.state transitions stay locked. Sub-bundle C can widen `fills.reconciliation_status` enum if §2.7 finds value, but cannot extend the trade-state state machine.
- **Re-deriving Phase 9 + Phase 11 + Phase 12 A + B forward-binding lessons** — accept as given (34 cumulative lessons; binding inheritance).

---

## §4 Binding conventions

- **Branch:** `main`. Single commit OR landing+fixes split per Phase 9/10 brainstorm precedent if Codex finds substantive issues.
- **Commit message:** `docs(phase12): Phase 12 Sub-bundle C auto-correct reconciliation brainstorm spec`. No Claude co-author footer. No `--no-verify`. No amending.
- **Spec format:** mirror `docs/superpowers/specs/2026-05-06-phase9-risk-policy-reconciliation-design.md`. Section-numbered; locked decisions called out explicitly with rationale; open questions enumerated for orchestrator triage.
- **Spec line target:** ~800–1300 lines (substantial; larger than Phase 8's 875 because Sub-bundle C has architectural-pivot scope; smaller than Phase 9's 1090 because fewer new tables but deeper classifier + service architecture).
- **Adversarial review:** mandatory; iterate to `NO_NEW_CRITICAL_MAJOR`. Budget 5–6 rounds (convergent chain expected per Phase 7/8/9 lesson family).
- **Schema sketches use simplified syntax** — column-name + type + CHECK descriptor + FK target, NOT full DDL.

---

## §5 Adversarial review watch items

For Codex rounds — pass these as targeted prompts to `copowers:adversarial-critic`:

1. **§1.1 operator-locked constraints integrity.** Spec respects all 4 operator locks (Schwab is truth; three-tier model; magnitude wrong axis; back-compat enum). If any spec recommendation appears to weaken these, flag for orchestrator — do NOT relax in spec.
2. **§1.2 discriminating examples worked end-to-end.** CVGI 41 + DHC 39 + VSAT 40 each walked through proposed classifier with input payload + classifier output + service action. Coverage check: does §2.2 enum cover all 3 cases without "miscellaneous" catch-all?
3. **Classifier determinism principle.** §2.2: when in doubt, classify tier-2 (NOT tier-1). False-positive tier-1 silently corrupts journal; false-positive tier-2 just defers. Audit §2.2 classifier examples for false-positive-tier-1 risk.
4. **Transactional discipline integrity (Phase 8 + Phase 9 lesson).** §2.3 auto-correction service rejects caller-held transactions; owns BEGIN IMMEDIATE/COMMIT/ROLLBACK; validator chain inside the lock. Audit for `in_transaction` auto-detect anti-pattern.
5. **SQLite REPLACE prohibition (Phase 8 CLAUDE.md gotcha).** §2.3 auto-correction service + §2.6 backfill MUST NOT use `INSERT OR REPLACE` against any FK-referenced or audit-trail table. SELECT-then-UPDATE-or-INSERT only.
6. **Validator chain integrity.** §2.3 enumerates ALL Phase 7 fills validators + Phase 9 risk_policy invariants the auto-correction MUST preserve. If tier-1 correction would violate any, classifier downgrades to tier-2 with `validator_rejected` ambiguity_kind.
7. **Audit-history table-vs-extension decision lockable.** §2.1 + §2.7: brainstorm picks new table OR `event_log` extension with rationale; both options have implications enumerated. Cross-bundle FK references locked.
8. **Tier-2 surface decision lockable.** §2.4: CLI-only V1 OR web-from-start with rationale. If web, HTMX failure-surface trinity preserved (HX-Request propagation + HX-Redirect + target-route-exists).
9. **Backfill path correctness for 39/40/41.** §2.6: each of the three current unresolved-material discrepancies walked through the backfill operation end-to-end with expected post-state.
10. **`acknowledged_immaterial` back-compat preserved.** §2.1 enum widening ADDS new values; existing values + existing 30 resolved discrepancies in production untouched. No backfill rewrite of historical resolutions.
11. **Phase 11 Schwab API audit-row attribution.** §2.3 + §2.6: when auto-correction or backfill fetches Schwab data, the `schwab_api_calls` audit row gets attributed with `surface='cli'` (or new value if surface='auto_correct' is justified; banked V2 candidate from Sub-bundle B is `surface='web'` enum widening — coordinate). FK reference shape `linked_reconciliation_correction_id` (NEW; if audit-history table is the chosen design) parallels Phase 11's `linked_snapshot_id` + `linked_reconciliation_run_id`.
12. **Per-row policy-versioned value stamping (Phase 8 R1 M5 lesson).** If auto-correction surface persists policy-versioned values (e.g., classifier thresholds, retention policies), per-row stamp at write time.
13. **Phase 9 reconciliation_runs lifecycle integration.** §2.1 + §2.5: state machine extension vs sibling table decision locked with rationale. If extension, ALL state transitions enumerated.
14. **Sub-sub-bundle decomposition cleanliness.** §1.5 + §2.8: dispatch ordering + cross-bundle dependencies enumerated; foundation (C.A) ships first; tier-1 service (C.C) blocked on classifier (C.B); UI + backfill (C.D) blocked on tier-1 service. No circular deps.
15. **Brief-premise empirical-verification (Phase 10 + 2026-05-04 lesson family).** Spec assertions about shipped-code state (e.g., "Phase 7 fills validators include X" / "Phase 9 reconciliation_runs state machine has Y") verified against actual code/migration files before encoding as binding §1.
16. **34 cumulative forward-binding lessons inheritance integrity.** Brief §0 lists them; spec audits compliance — especially Phase 9 D R3 form-render hidden anchors + Phase 12 B forward-binding lessons #6 (apply_overrides discipline) + #11 (HTMX gotcha trinity) + #12 (T-A.3 gap pre-emption pattern).
17. **`§1.6` fill auto-population scope clarity.** Spec acknowledges scope; identifies clean layering interfaces; flags any C decisions that would foreclose. DOES NOT design fill auto-population.
18. **Convergent-chain expectation.** Codex round count likely 5-6; chain shape matters more than count. Implementer's return report documents fix-introduced regression vs adversarial-thrash distinction.

---

## §6 Done criteria

1. Spec at `docs/superpowers/specs/<YYYY-MM-DD>-phase12-bundle-C-auto-correct-reconciliation-design.md` covering §2.1–§2.9.
2. Brainstorm went through ≥3 Codex rounds reaching `NO_NEW_CRITICAL_MAJOR`.
3. Spec section structure mirrors prior brainstorm spec format (Phase 9 design canonical).
4. CVGI 41 + DHC 39 + VSAT 40 each walked through end-to-end as discriminating examples in §2.2 classifier + §2.6 backfill.
5. Sub-sub-bundle decomposition recommendation in §2.8.
6. Single commit OR landing+fixes split: `docs(phase12): Phase 12 Sub-bundle C auto-correct reconciliation brainstorm spec` (and follow-up commit `docs(phase12): Phase 12 Sub-bundle C spec — Codex R1-R<N> fixes` if applicable).
7. Return report covers items in §7.

---

## §7 Return report format

```
## Return report — Phase 12 Sub-bundle C auto-correct reconciliation brainstorm

### Spec location
`docs/superpowers/specs/<YYYY-MM-DD>-phase12-bundle-C-auto-correct-reconciliation-design.md` ({line count} lines)
Commits on main:
- {sha} `docs(phase12): Phase 12 Sub-bundle C auto-correct reconciliation brainstorm spec` (initial)
- (optional) {sha} `docs(phase12): Phase 12 Sub-bundle C spec — Codex R1-R<N> fixes` (post-review)

### Codex review history
- R1: {C/M/m findings; verdict; FIXED/ACCEPTED counts}
- R2: ...
- ...
- Final verdict: NO_NEW_CRITICAL_MAJOR

### Three highest-leverage design decisions
1. ...
2. ...
3. ...

### Classifier architecture decision (§2.2)
Locked: classifier input/output contract + ambiguity_kind enum coverage + determinism principle.
Rationale: ...

### Audit-history schema decision (§2.1 + §2.7)
Locked: new table vs event_log extension.
Rationale: ...

### Tier-2 surface decision (§2.4)
Locked: CLI-only V1 OR web-from-start.
Rationale: ...

### Reconciliation flow pivot decision (§2.5)
Locked: classify-and-apply-inline OR async post-run.
Rationale: ...

### Sub-sub-bundle decomposition + dispatch ordering (§2.8)
Locked: 3-4 sub-sub-bundles with dispatch order + cross-bundle dependencies.

### Backfill path decision (§2.6)
Locked: CLI surface + dry-run support + idempotency contract.
Worked examples for 39/40/41 verified.

### review_log freezing semantics decision (§2.7)
Locked: un-freeze vs retain-and-mark-superseded.
Rationale: ...

### Open questions for orchestrator triage
1. ...
2. ...

### Capture-needs feedback FOR PHASE 12 SUB-BUNDLE C WRITING-PLANS
- ...

### Outstanding capture-needs that DEFER to "fill auto-population at entry" sub-bundle
- ...
```

---

## §8 If you get stuck

- If §1 operator-locked constraints conflict with Codex finding, §1 wins; flag as open question.
- If a Codex round produces a finding you can't disposition without orchestrator input, ACCEPT-with-rationale + flag explicitly in spec's "open questions" section + return report.
- If the spec exceeds ~1300 lines, re-scope.
- DO NOT propose migration SQL. DO NOT write code. If you start drafting `CREATE TABLE ...` or `class FooService`, stop.
- If you encounter a Phase 7/8/9/10/11/12-A/12-B lesson that conflicts with a Sub-bundle C design proposal, the prior-phase lesson wins (validated by ship-experience). Surface the conflict as a design constraint.
- If "fill auto-population at trade-entry" (§1.6) tempts you to design schema for it, STOP — separate sub-bundle.
- If you find yourself proposing a magnitude-based threshold, STOP — §1.1 lock #3 violated.
- If you find yourself proposing operator triage as the default for any new discrepancy type, STOP — §1.1 lock #1+#2 violated (Schwab is truth; tier 1 is default for unambiguous cases).
