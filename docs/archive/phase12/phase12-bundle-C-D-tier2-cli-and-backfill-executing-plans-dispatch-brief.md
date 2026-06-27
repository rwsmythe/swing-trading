# Phase 12 Sub-sub-bundle C.D (Tier-2 CLI + backfill + Phase 10 banner widening — CLOSES Sub-bundle C) — executing-plans dispatch brief

**Audience:** Fresh Claude Code instance with no prior conversation context.

**Mission:** Execute Sub-sub-bundle C.D (Tier-2 CLI surface + reconcile-backfill CLI + Pass 1 / Pass 2 backfill mechanic + Phase 10 dashboard banner predicate widening + cycle-checklist + CLAUDE.md gotcha additions) of the Phase 12 Sub-bundle C implementation plan via `copowers:executing-plans`. Plan is `docs/superpowers/plans/2026-05-15-phase12-bundle-C-auto-correct-reconciliation-plan.md` §E (C.D scope; 16 tasks T-D.1 … T-D.14 + T-D.6.1 + T-D.11). All per-task acceptance criteria + tests + commit shapes are in the plan; this dispatch brief is a worktree-config + scope wrapper, NOT a duplicate spec.

**Expected duration:** ~16-22 hr implementation + ~4-7 hr Codex convergence. Total ~20-29 hr. C.D is the **closer** sub-sub-bundle of the Sub-bundle C arc; introduces 5 new CLI surfaces + Pass 1/Pass 2 backfill orchestrator + Phase 10 banner predicate widening (transitive through 14 base-layout VM instances across 9 files) + cycle-checklist + CLAUDE.md gotcha additions. **The 10-surface operator-witnessed gate is the largest in project history** — production-write `reconcile-backfill --apply` against operator's REAL discrepancies 39 DHC + 40 VSAT + 41 CVGI.

**Skill posture:**
- Invoke `copowers:executing-plans` against the plan path scoped to Sub-sub-bundle C.D (`PLAN_PATH=docs/superpowers/plans/2026-05-15-phase12-bundle-C-auto-correct-reconciliation-plan.md`, `SCOPE=Sub-sub-bundle C.D (T-D.1..T-D.14 + T-D.6.1 + T-D.11 only)`).
- The skill wraps `superpowers:subagent-driven-development` + adversarial Codex review.
- Adversarial review runs after all 16 tasks land. Expected 4-6 Codex rounds (matches Phase 12 Sub-sub-bundle C.B 5 rounds for multi-CLI-surface scope; C.A 2 rounds + C.C 3 rounds are the lower bound; C.B 5 rounds is the realistic upper bound). Plan §E + spec §6/§8 LOCKs have already absorbed 8 Critical + 14+ Major across writing-plans + brainstorm chains; execution rounds should converge faster.

---

## §0 Inputs

### §0.1 Plan

- **PLAN_PATH:** `docs/superpowers/plans/2026-05-15-phase12-bundle-C-auto-correct-reconciliation-plan.md` (3621 lines; Codex R6 confirmation NO_NEW_CRITICAL_MAJOR; LOCKED at `008dfe4`).
- **Sub-sub-bundle C.D section** is plan §E (lines 2573-3254). Self-contained per-task spec with TDD checkboxes (`- [ ]`).
- **Plan §F cross-bundle pin matrix:**
  - F-7 (C.C T-C.3 handlers → C.D T-D.3 CLI + T-D.5 exhaustiveness) — 18 per-(ambiguity_kind, choice_code) handlers registered + matching `get_choice_menu(...)` registry. **18 = 17 exact-key + 1 parametric prefix** (Codex R1 Minor #4 clarified at writing-plans; brief §0.5 #10 below).
  - F-8 (C.D T-D.2 menu helper → C.D T-D.3 CLI) — `get_choice_menu(ambiguity_kind) -> list[ChoiceMenuItem]` with `requires_custom_value` field.
  - F-9 (C.D T-D.6/7/8/9 backfill → C.D gate S2/S3/S4) — `swing journal reconcile-backfill` CLI surface + flags.
  - F-10 (C.D T-D.10 banner widening → all 14 base-layout VMs) — `count_unresolved_material(conn)` now sums `'unresolved'` + `'pending_ambiguity_resolution'`.
- **Plan §G.4 C.D operator-witnessed gate (10 surfaces; see §3 below).** This is the LARGEST gate in project history; previous max was Phase 11 Sub-bundle D 7-surface + Phase 10 Sub-bundle E 7-surface.
- **Plan §A.5 brief-vs-spec discrepancy:** spec §A.5 wording says "retrofit 10 base-layout VM consumers"; actual count per grep is **14 VMs across 9 files** (banked at §I.10 as V2.1 §VII.F amendment candidate). Plan T-D.10 covers the full 14-VM surface; grep `unresolved_material_discrepancies_count` confirms (post-grep at orchestrator handoff time shows 18 files of which 9 hold the base-layout VMs; remainder are metric VMs that may also extend base.html.j2 — verify at T-D.10 implementation time via template-inheritance audit; defense-in-depth retrofit).

### §0.2 Spec

- **SPEC_PATH:** `docs/superpowers/specs/2026-05-15-phase12-bundle-C-auto-correct-reconciliation-design.md` (1444 lines; Codex R9 confirmation NO_NEW_CRITICAL_MAJOR; LOCKED at `d682c25`).
- **Read for §6 Tier-2 ambiguity-resolution surface (BINDING — §6.1 CLI-first V1 / web V2 LOCK; §6.2 CLI surface shape — `resolve-ambiguity` + `list-pending-ambiguities` + `show-ambiguity` LOCKED; §6.2.1 per-(ambiguity_kind, choice_code) menu LOCKED post-Codex R5+R7 — 11 payload-required + 7 no-payload choices across 7 ambiguity_kinds; §6.3 operator workflow; §6.4 tier-3 override CLI + confirmation prompt + `--force` flag LOCKED).**
- **Read §8 Backfill path (BINDING — §8.1 purpose; §8.2 CLI surface LOCKED with `--apply` + `--dry-run` + `--ticker` + `--limit` + `--no-pass-2-on-dry-run` + `--retry-pass-2-failures`; §8.3 idempotency LOCKED post-Codex R2 Major #2; §8.4 classifier source-payload sourcing — Pass 1 / Pass 2 two-pass contract LOCKED; §8.4 #4 per-discrepancy-type Pass-1-sufficient table LOCKED; §8.4 Pass-2-tier-1-FORBIDDEN LOCK post-Codex R3 Critical #1 + Major #1; §8.5 backfill flow; §8.6 backfill applied to existing 3 discrepancies — §10 walkthroughs binding).**
- **Read §15.5 LOCKED revised C.D gate mechanic** (S6a synthetic-fixture-only payload-contract acceptance test + S6b operator-real-disposition per actual data without contortion — banked through R6 M#3 + R7 M#3 + R8 M#1+M#2 cascade).
- **Read §1.3 four operator-locked architectural constraints** + **§3.5 trade_events enum +1 LOCK** + **§9.1 review_log freezing RETAIN + mark superseded LOCK** + **§9.2 NO V1 fills.reconciliation_status enum widening LOCK** + **§9.5 NO reconciliation_runs.state extension LOCK** + **§10 three discriminating-example walkthroughs (CVGI 41 tier-1; DHC 39 tier-2 pending; VSAT 40 classifier-data-dependent path).**

### §0.3 Project state at dispatch time

- **HEAD on `main`:** `e53cb59` (or later if operator landed follow-on commits; post-Phase-12-Sub-sub-bundle-C-C-merge handoff brief commit). Brief commit lands at HEAD+1 pre-dispatch.
- **Test count:** **4204 fast passing on main** + 3 pre-existing failures (`tests/integration/test_phase8_pipeline_walkthrough.py`; banked since Phase 8) + 1 skipped (Task 7.3 flag-classifier operator-only fixture).
- **Ruff baseline:** **18** (E501 only; unchanged across Phase 11 + Phase 12 A+B+C.A+C.B+C.C).
- **Schema version:** **v19** (C.A T-A.1 shipped 2026-05-15; production-migrated 2026-05-15T18:52:43; C.B + C.C consumer-side only). **C.D MAY NOT widen schema** (§4 lock; C.A return report lesson #7 family).
- **Production discrepancy state:** **3 unresolved-material (39 DHC + 40 VSAT + 41 CVGI)** + 30+ resolved historical. **LEFT UNRESOLVED BY DESIGN pending C.D backfill operation.** C.D gate S3+S4 dispositions them via `reconcile-backfill --apply`. CVGI 41 → tier-1 auto-correct per §10.1 (Pass 1 sufficient); DHC 39 + VSAT 40 → tier-2 stamps per §10.2/§10.3 (Pass 2 required; actual `ambiguity_kind` set per real Pass-2 outcome).
- **Production refresh-token clock:** expires **2026-05-22T17:05:00+00:00** (~5-6 days remaining from handoff date 2026-05-16). **C.D dispatch + gate likely consumes 4-7 days. Operator may need to re-auth via `/schwab/setup` web form OR `swing schwab setup` CLI BEFORE C.D gate session.** T-A.2 self-healing means recovery is one CLI/web invocation now (no longer needs `logout → setup` two-step). **Verify Schwab refresh-token TTL > 1hr at gate S2 pre-check** (per §G.4 S2 pre-gate operator check + spec §G.4 line 3351).
- **Production-write classifier soft-block awareness:** `reconcile-backfill --apply` at S3+S4 is production-write against operator's REAL DB. Operator pre-authorizes via gate-path AskUserQuestion or plain-chat "yes" if Claude Code's production-write classifier soft-blocks. **DO NOT proceed without explicit operator authorization.**
- **Worktree husks:** **3 pending at handoff** (`.worktrees/phase12-bundle-C-A-foundation/` + `.worktrees/phase12-bundle-C-B-classifier-and-validator-shim/` + `.worktrees/phase12-bundle-C-C-auto-correction-service-and-flow-pivot/`); all ACL-locked; operator's `cleanup-locked-scratch-dirs.ps1 -DeregisterFirst` regex `(phase\d+[-_]|schwab(?:-\w+)?-bundle-)` matches all 3 + the new C.D husk cleanly. Operator-driven cleanup pass.

### §0.4 Sub-sub-bundle C.D scope (16 tasks per plan §E)

| Task | Title | Files (illustrative; plan §E locks) |
|---|---|---|
| **T-D.1** | `swing journal discrepancy list-pending-ambiguities` CLI subcommand (`--ambiguity-kind` + `--ticker` + `--limit` flags) | MODIFY `swing/cli.py` + NEW `tests/cli/test_discrepancy_list_pending_ambiguities_cli.py` |
| **T-D.2** | `swing journal discrepancy show-ambiguity <id>` CLI + NEW helper module `swing/trades/reconciliation_ambiguity_choices.py` (per-`ambiguity_kind` choice-menu builder; mirrors §6.2.1 verbatim; `ChoiceMenuItem` dataclass with `code` + `description` + `requires_custom_value: bool` + `recommended: bool`; `keep_journal_as_is` is `recommended=True` for `multi_partial_vs_consolidated` per OQ-4) | MODIFY `swing/cli.py` + NEW `swing/trades/reconciliation_ambiguity_choices.py` + NEW `tests/cli/test_discrepancy_show_ambiguity_cli.py` + NEW `tests/trades/test_reconciliation_ambiguity_choices.py` |
| **T-D.3** | `swing journal discrepancy resolve-ambiguity` CLI + per-choice `--custom-value` enforcement (Codex R5 Major #2 LOCK per-choice not suffix-based) + REQUIRED `--reason` + OPTIONAL `--schwab-api-call-id` flag (Codex R3 Major #1 revision; R4 Major #2 deterministic-output) | MODIFY `swing/cli.py` + NEW `tests/cli/test_discrepancy_resolve_ambiguity_cli.py` |
| **T-D.4** | `swing journal discrepancy override-correction` CLI + confirmation prompt by default + `--force` flag + `AlreadySupersededError` chain-head guidance | MODIFY `swing/cli.py` + NEW `tests/cli/test_discrepancy_override_correction_cli.py` |
| **T-D.5** | Exhaustive handler-registry vs menu vs spec §6.2.1 binding-contract regression test (17 exact-key + 1 parametric-prefix = 18 binding entries; Codex R1 Minor #4 clarified parametric handling) | NEW `tests/cli/test_resolve_ambiguity_handler_exhaustiveness.py` |
| **T-D.6** | `swing journal reconcile-backfill` CLI scaffold + `BackfillSummary` dataclass + `BackfillOutcome` per-row dataclass + `BackfillPipelineActiveError` exclusion guard (Codex R2 Major #1 LOCK — autocommit; NO outer BEGIN IMMEDIATE; service helpers own their own txs) | MODIFY `swing/cli.py` + NEW `swing/trades/reconciliation_backfill.py` + NEW `tests/cli/test_reconcile_backfill_cli.py` |
| **T-D.6.1** | `_audited_get_account_orders` wrapper at `swing/integrations/schwab/trader.py` (Codex R2 Major #2 fix; returns `(call_id, list[SchwabOrderResponse])` tuple; opt-in `return_call_id: bool = False` kwarg on shared helper; backward-compat regression test asserts existing `get_account_orders(...)` signature unchanged) | MODIFY `swing/integrations/schwab/trader.py` + NEW `tests/integrations/test_schwab_trader_audited_wrapper.py` |
| **T-D.7** | Backfill Pass 1 (persisted-JSON-only classification) + dry-run projection matrix + apply-path dispatches via PUBLIC `apply_tier1_correction` (own-tx) + PUBLIC `stamp_pending_ambiguity` (own-tx) — NO direct UPDATE from backfill code; NO per-discrepancy BEGIN IMMEDIATE in backfill code; `environment` keyword propagates through CLI cfg into every public-service call | MODIFY `swing/trades/reconciliation_backfill.py` + NEW `tests/trades/test_reconciliation_backfill_pass1.py` |
| **T-D.8** | Backfill Pass 2 (Schwab re-fetch + Pass-2-tier-1-FORBIDDEN LOCK + per-discrepancy `call_id` printout for `--schwab-api-call-id` workflow + sandbox short-circuit + Pass 2 failure-mode persisted state) | MODIFY `swing/trades/reconciliation_backfill.py` + NEW `tests/trades/test_reconciliation_backfill_pass2.py` |
| **T-D.9** | Backfill idempotency (`resolution != 'unresolved'` → SKIP) + `--retry-pass-2-failures` flag (Codex R5 Major #1 fix; `stamp_pending_ambiguity(..., allow_pending_update=True)` overwrites prior failure-state stamp) + summary counters | MODIFY `swing/trades/reconciliation_backfill.py` + NEW `tests/trades/test_reconciliation_backfill_idempotency.py` |
| **T-D.10** | Phase 10 dashboard banner predicate widening to include `'pending_ambiguity_resolution'` (3 SQL predicates widened; **14-VM regression suite across 9 files**; OQ-7 acceptance evidence) | MODIFY `swing/metrics/discrepancies.py` + MODIFY `swing/data/repos/reconciliation.py` + NEW `tests/metrics/test_discrepancies_predicate_widening.py` + NEW `tests/web/test_base_layout_vm_banner_with_pending_ambiguity.py` |
| **T-D.11** | **Synthetic-fixture payload-contract acceptance test (C.D gate S6a prerequisite per spec §15.5 LOCKED revised mechanic + Codex R1 Major #7 fix — table-driven across ALL 11 payload-required choices + 7 no-payload choices)** | NEW `tests/integration/test_phase12_bundle_c_payload_contract_acceptance.py` |
| **T-D.12** | Cycle-checklist updates (weekly Tier-2 cadence + one-time backfill + tier-3 override) | MODIFY `docs/cycle-checklist.md` |
| **T-D.13** | CLAUDE.md gotcha additions (6 new entries per writing-plans assessment) | MODIFY `CLAUDE.md` |
| **T-D.14** | `briefing.md` "Reconciliation status" section integration test (E2E + empty-section case) | NEW `tests/integration/test_briefing_md_reconciliation_status_e2e.py` |

**Cross-bundle dependencies:** C.D CONSUMES C.A schema (`reconciliation_corrections` table + `ambiguity_kind` column + CHECK enum widenings) + C.B `classify_discrepancy` + C.B `default_validator_chain` + **C.C `apply_tier1_correction` (public/own-tx)** + **C.C `apply_tier2_resolution` (public/own-tx)** + **C.C `apply_tier3_override` (public/own-tx)** + **C.C `stamp_pending_ambiguity` (public/own-tx)** + **C.C `_MANUAL_RESOLVE_ALLOWED_RESOLUTIONS` allowlist invariant** (C.D `resolve-ambiguity` CLI must NOT regress to `RESOLUTION_TYPES`; routes through C.C service entries).

**Module boundaries (BINDING — preserve discipline):**
- `swing/trades/reconciliation_backfill.py`: BACKFILL ORCHESTRATOR LAYER. Does NOT own transactions (autocommit; per Codex R2 Major #1 LOCK). Composes over C.C public service functions (each owns its own tx) + C.B classifier (pure function) + T-D.6.1 audited Schwab wrapper.
- `swing/trades/reconciliation_ambiguity_choices.py`: HELPER MODULE. `ChoiceMenuItem` dataclass + `get_choice_menu(ambiguity_kind)` function. Pure data; no DB writes; no I/O.
- `swing/cli.py`: CLI ENTRY POINTS. Click subcommands invoke C.C service functions + C.D backfill orchestrator + helper module. CLI MUST validate `--choice` against `get_choice_menu(ambiguity_kind)` member list BEFORE invoking service.

### §0.5 BINDING contracts from plan §E + spec §6 + §8 + §15.5 (DO NOT re-litigate)

Per writing-plans return report + plan §E + spec §6/§8/§15.5:

1. **Spec §6.1 CLI-first V1 LOCK** — web Tier-2 surface is V2 candidate (banked at plan §I.3). C.D scope is CLI-only.
2. **Spec §6.2 CLI surface shape LOCKED** — 3 NEW subcommands under existing `swing journal discrepancy` group: `list-pending-ambiguities`, `show-ambiguity`, `resolve-ambiguity`. 1 NEW subcommand `override-correction` for Tier-3. 1 NEW subcommand under `swing journal` group: `reconcile-backfill`.
3. **Spec §6.2.1 per-(ambiguity_kind, choice_code) menu LOCKED post-Codex R5 + R7** — 7 ambiguity_kinds × variable choices = **11 payload-required choices + 7 no-payload choices = 18 binding contract entries** (17 exact-key + 1 parametric prefix `pick_schwab_record_<N>`). `--custom-value` requirement is PER-CHOICE not suffix-based (Codex R5 Major #2 LOCK).
4. **Spec §6.3 operator workflow LOCKED** — `--reason` REQUIRED on every `resolve-ambiguity` + `override-correction` invocation.
5. **Spec §6.4 tier-3 override CLI LOCKED** — `--truth-value` + `--reason` REQUIRED; confirmation prompt by default (OQ-8 ACCEPT); `--force` flag bypasses (mirrors `cleanup-locked-scratch-dirs.ps1 -DeregisterFirst` precedent). `AlreadySupersededError` (OQ-15 disposition) maps to friendly CLI error naming the chain-head correction_id + exit 2.
6. **Spec §8.2 backfill CLI surface LOCKED** — default mode `--dry-run`; `--apply` + `--dry-run` mutually exclusive; `--ticker` + `--limit` scope/throttle flags; `--no-pass-2-on-dry-run` + `--retry-pass-2-failures` per Codex R5 Major #1 fix. **Dry-run does NOT mutate journal tables, does NOT mutate `reconciliation_discrepancies.resolution`/`ambiguity_kind`, does NOT INSERT `reconciliation_corrections`/`trade_events`, does NOT UPDATE `review_log.superseded_by_correction_id`. Dry-run DOES write `schwab_api_calls` audit rows when Pass-2 re-fetches occur** (per Codex R2 Major #1 LOCK; the audit row is the read's audit-trail contract, not a journal mutation). CLI prints explicit advisory before any Pass-2 re-fetches.
7. **Spec §8.3 idempotency LOCKED** — re-running `--apply` is safe; discrepancies with `resolution != 'unresolved'` SKIPPED; Pass-2-failed discrepancies persisted as `resolution='pending_ambiguity_resolution'` (per §8.4 #3) ALSO SKIPPED by default; operator opts-in via `--retry-pass-2-failures` to retry.
8. **Spec §8.4 two-pass contract LOCKED** — Pass 1 = persisted-JSON-only classification (zero Schwab API calls; sufficient for 8 of 10 discrepancy_types per §8.4 #4 table); Pass 2 = re-fetch Schwab via `get_account_orders_audited(...)` (T-D.6.1) ONLY when Pass 1 emits `ambiguity_kind='unsupported'` with `_pass_2_required=True` (only `unmatched_open_fill` + `unmatched_close_fill` types per §8.4 #4 table).
9. **Spec §8.4 Pass-2-tier-1-FORBIDDEN LOCK (Codex R3 Critical #1 + Major #1)** — Pass 2 source data is `list[SchwabOrderResponse]` (order-grain); classifier-output from Pass 2 MUST NEVER be tier-1. C.B T-B.4 sub-classifier already enforces this; T-D.8 inherits. Discriminating test: invoke backfill against a planted DHC fixture where Pass 2 returns N orders summing to journal qty; assert classifier emits tier-2 (NEVER tier-1) regardless of price-similarity to journal.
10. **Spec §8.4 sandbox short-circuit LOCK** — under `environment='sandbox'`, Pass 2 returns `None` (no Schwab API call fired); classifier emits tier-2 `unsupported` with rationale `"sandbox: cannot re-fetch source-canonical payload"`.
11. **Spec §10 three discriminating-example walkthroughs BINDING** — CVGI 41 tier-1 entry_price_mismatch from persisted JSON (Pass 1 sufficient); DHC 39 + VSAT 40 tier-2 pending ambiguity per actual Pass-2 outcome (Pass 2 required).
12. **Codex R1 Critical #1 fix LOCKED at spec §6.2.1** — EVERY tier-2 resolution lands as `resolution='operator_resolved_ambiguity'` + a `reconciliation_corrections` audit row, EVEN WHEN the operator's choice is "no journal mutation" (e.g., `keep_journal_as_is`, `mark_unmatched`, `acknowledge`). The audit row records the operator's explicit no-mutation choice with `applied_value_json == pre_correction_value_json` + `correction_action='operator_resolved_ambiguity'` + `correction_choice='<choice_code>'`. `acknowledged_immaterial` is RESERVED for the narrow Tier-3 case where operator declares Schwab itself wrong (§6.4).
13. **Spec §15.5 C.D gate LOCKED revised mechanic (post-R6+R7+R8)** — S6a synthetic-fixture-only payload-contract acceptance test (table-driven across ALL 11 payload-required + 7 no-payload choices; fresh isolated tmp DB per case discarded at gate end) + S6b operator-real-disposition of production DHC 39 per actual data (NO contortion). S7 operator-real-disposition of VSAT 40 per actual data (payload-contract surface already satisfied at S6a; S7 does NOT need contortion).
14. **Plan §A.5 14-VM-instance retrofit LOCK** — banner predicate widening lands at **3 helper functions** (`count_unresolved_material`, `list_unresolved_material_for_active_trades`, `list_unresolved_material_for_trade`); transitive through **14 VM instances across 9 files** (per grep verification). Spec §A.5 says "10 base-layout VMs" — banked as V2.1 §VII.F amendment candidate.

### §0.6 Forward-binding lessons inherited (BINDING for C.D)

**58 cumulative lessons** through C.C (Phase 11 17 + Phase 12 A 5 + B 12 + C brainstorm 5 + C writing-plans 2 + C.A 3 + C.B 7 + C.C 7 = 58).

**Particularly load-bearing for C.D — the 7 NEW C.C-binding lessons banked at C.C return report §10 (`docs/phase12-bundle-C-C-return-report.md`):**

1. **C.C lesson #1 — Schema-coverage constant ≠ manual-resolver allowlist.** After widening a Python enum to mirror schema CHECK (the standard CLAUDE.md gotcha pattern), audit every existing **manual** callsite that validates against the constant. If the new values are service-owned (require routing through specific service entries), introduce a separate tighter allowlist for the manual path. **C.D inheritance:** the per-(ambiguity_kind, choice_code) menu validation at T-D.3 `resolve-ambiguity` CLI MUST use the tight `get_choice_menu(ambiguity_kind)` member list (a NEW C.D-introduced allowlist), NOT regress to `RESOLUTION_TYPES` (the 9-value schema-coverage constant). Per-choice rejection test asserting the routing hint substring in the error message for any service-owned-state attempt + parametrized positive test for the menu allowlist. **C.D specific application:** `resolve-ambiguity` MUST NOT accept the 4 service-owned states (`auto_corrected_from_schwab` / `pending_ambiguity_resolution` / `operator_resolved_ambiguity` / `operator_overridden`) as `--choice` values — those route through C.C canonical service entries (`apply_tier1_correction` / `stamp_pending_ambiguity` / `apply_tier2_resolution` / `apply_tier3_override`).
2. **C.C lesson #2 — Outer transaction discipline UNIFORM regardless of sandbox.** Sandbox short-circuit MUST live in the inner (caller-tx) function, NOT the outer (own-tx) function. **C.D inheritance:** `reconcile-backfill --apply --environment sandbox` is a deferred test path — the backfill orchestrator does NOT open BEGIN IMMEDIATE (per §0.5 #6 Codex R2 Major #1 LOCK — autocommit); the public-service `apply_tier1_correction(conn, environment='sandbox')` short-circuits inside; the audit row is still written via the PUBLIC service function (which owns its own BEGIN IMMEDIATE + commits the audit-row-only side per spec §5.9). Discriminating test pattern: invoke `run_backfill(..., environment='sandbox')` against a planted CVGI-shape tier-1-eligible discrepancy + assert `fills.price` unchanged + assert no `reconciliation_corrections` row written + assert `BackfillSummary.tier1_applied == 0`.
3. **C.C lesson #3 — SELECT-first idempotency must precede payload validation.** For services with idempotency contracts (terminal-state → return existing audit row WITHOUT new write), the SELECT + terminal-check MUST happen BEFORE input-payload validation. **C.D inheritance:** T-D.9 backfill idempotency directly consumes this — re-running `--apply` on a terminal-state discrepancy returns cleanly without exception even with stale/malformed/None `classification` payload (the discrepancy is SKIPPED at the backfill level before any service-layer payload validation fires). Discriminating test: re-run `--apply` against fully-resolved DB; assert summary counter `skipped_already_resolved` increments correctly.
4. **C.C lesson #4 — Counter staleness after inline state mutation.** When a flow emits rows AND later mutates those rows' states, run-summary counters MUST be recomputed or decremented post-mutation. **C.D inheritance:** `BackfillSummary` counters (`tier1_applied`, `tier2_stamped`, `tier_errored`, `pass_2_failed`, `skipped_already_resolved`, `skipped_pass_2_failed`) MUST reflect the actual post-backfill state. Discriminating test: plant N discrepancies (mix of tier-1 + tier-2 + Pass-2-failed + already-resolved) → run backfill → assert each counter equals actual post-backfill count, NOT N.
5. **C.C lesson #5 — DRY helper extraction across pivot mirror sites.** When the plan says "mirrors T-X verbatim" + the mirror is non-trivial, extract a private helper rather than duplicating. **C.D inheritance:** `show-ambiguity` + `resolve-ambiguity` + `override-correction` all consume similar pre-step validation (`discrepancy_id` lookup + ambiguity_kind retrieval + menu lookup); extract a shared helper rather than duplicating across 3 CLI subcommands. The CLI display-output formatting for `show-ambiguity` table-output may also be shared with `list-pending-ambiguities`.
6. **C.C lesson #6 — Pre-Codex orchestrator-side review catches obvious LOCK divergences cheaply.** Orchestrator-side spec-compliance + code-quality review BEFORE invoking adversarial-critic catches plan-text deviations Codex would otherwise spend a round flagging. **C.D inheritance:** the IMPLEMENTER's `copowers:executing-plans` skill triggers pre-Codex review automatically — but the implementer's chain MUST do an explicit dispatched-reviewer-subagent pass BEFORE invoking `copowers:adversarial-critic`. Saved 1-2 Codex rounds on C.C. **Pattern reusable for C.D's 10-surface gate stakes:** dispatch focused reviewer subagent with plan §E acceptance criteria + brief §0.5 BINDING contracts as anchors; ask for deviation list ≤600 words.
7. **C.C lesson #7 — Implementer self-report accuracy gate.** Implementer chain's final report claims MUST cite specific file:line evidence for each fix claim. **C.D inheritance:** at C.D return-report time, every claim should cite `<file>:<line>` evidence (e.g., "T-D.7 Pass 1 implementation at `swing/trades/reconciliation_backfill.py:142-180`"); orchestrator-side review verifies the cited lines actually match the claim.

**The 7 C.B-binding lessons (still load-bearing for C.D):**

8. **C.B lesson #1 (classifier → service boundary).** Pinned at §0.5 #11 above. C.D backfill consumes the classifier; the lifecycle invariants on `reconciliation_corrections` rows are enforced at C.C service-layer apply-time (NOT at classifier-output time + NOT at backfill orchestrator time).
9. **C.B lesson #2 (validator chain re-invoke at apply time).** Pinned via C.C `_apply_tier1_correction_inner` Step 4 (Codex R1 M#2 SELECT-first idempotency LOCK preserves this). C.D backfill invokes C.C public service functions; service-layer validator re-runs end-to-end.
10. **C.B lesson #5 (shape predicate tightening).** **CRITICAL FOR C.D** — `--custom-value` JSON payloads at T-D.3 `resolve-ambiguity` + T-D.4 `override-correction --truth-value`. **The brief MANDATES explicit shape predicate checks at handler entry for EACH per-(ambiguity_kind, choice_code) handler that consumes a payload-required choice:**
    - Reject unrecognized keys (e.g., `consolidate_using_operator_vwap` accepts `{"price": X}` ONLY; reject any other keys)
    - Reject contradictory evidence within payload (e.g., `split_into_partials` payload list MUST have `len(payload) >= 2` for split to be meaningful; reject `len <= 1`)
    - Reject missing-required-fields (e.g., `split_into_partials` per-entry MUST have all 3 keys `qty` + `price` + `fill_datetime`)
    - Reject NaN/inf on numeric fields (per C.B Codex R1 M#2 `math.isfinite()` family)
    **Per-handler discriminating-test pattern: per service-owned-choice, 4-case parametrize (correct-shape happy / unrecognized-key reject / contradictory-field reject / missing-required-field reject).** This pre-empts the Codex round-2-round-3 cascade that C.B's `entry_price_mismatch` Shape A/B predicate took (R1 C#1 → R2 M#1 → R3 M#1 → R4 M#1) by designing defensively up-front. Where this validation lives: C.C `apply_tier2_resolution` inner-function's per-handler dispatch already validates the payload as part of the §5.6 LOCK. C.D `resolve-ambiguity` CLI does PARSE-time validation (Click usage errors for missing flag) + SHAPE validation BEFORE invoking the service (so the error mode is `click.UsageError` exit 2, NOT a `ValueError` from service exit 1).
11. **C.B lesson #6 (same-source-keys evidence convergence).** Relevant to T-D.3 + T-D.4 multi-field payloads (e.g., `pick_schwab_record_<N>` payload mirrors source-side keys `qty` + `price` + `fill_datetime`).
12. **C.B lesson #7 (Co-Authored-By footer drift — EXPLICIT suppression).** Carry-forward to C.D: this dispatch's inline prompt MUST explicitly cite the "No Claude co-author footer" CLAUDE.md binding convention. C.C's explicit citation produced ZERO footer drift across 23 commits — pattern works. See §1.3 below for binding language. **DO NOT skip this — passive CLAUDE.md inheritance is insufficient because subagents have isolated context.**

**5 V2 candidates from C.C return report §7 + 6 V2.1 §VII.F amendments banked** — see CLAUDE.md gotchas + `docs/phase3e-todo.md` 2026-05-16 entries.

### §0.7 Sub-sub-bundle C.D test projection

Per plan §H.1: **+55-80 fast tests projected** (plan-author tightening from spec §12.D's +80-150 because the banner-widening retrofit is mechanically smaller than the spec's 10-VM phrasing suggested). Per Phase 9/10/12 overshoot precedent (A overshoot +35→actual +104; B +85-130→actual +139; C +65-115→actual +95), **actual likely +60-120 fast tests** for C.D upper bound.

Final main HEAD post-C.D-merge: **~4259-4324 fast tests** (was ~4204 + +55-120).

---

## §1 Worktree + binding conventions

### §1.1 Worktree

- **Branch:** `phase12-bundle-C-D-tier2-cli-and-backfill`
- **Worktree directory:** `.worktrees/phase12-bundle-C-D-tier2-cli-and-backfill/`
- **BASELINE_SHA:** `e53cb59` (current main HEAD pre-brief-commit; resolve via `git rev-parse main` at worktree-creation time after this brief lands).
- **Branch naming intent:** `phase12-bundle-C-D-*` matches the cleanup-script `phase\d+[-_]` regex; operator's `-DeregisterFirst` pass cleans cleanly post-merge.

### §1.2 Marker-file workflow

- After worktree creation: `New-Item -ItemType File c:\Users\rwsmy\swing-trading\.copowers-subagent-active`
- After all 16 tasks land + tests GREEN + before invoking adversarial-critic: `Remove-Item c:\Users\rwsmy\swing-trading\.copowers-subagent-active`

### §1.3 Commits

- Conventional prefixes:
  - `feat(phase12-bundle-c-T-D.1..4): <description>` for CLI subcommands
  - `test(phase12-bundle-c-T-D.5): <description>` for exhaustiveness regression test
  - `feat(phase12-bundle-c-T-D.6..9): <description>` for backfill orchestrator + Pass 1 + Pass 2 + idempotency
  - `feat(phase12-bundle-c-T-D.6.1): <description>` for `_audited_get_account_orders` wrapper
  - `feat(phase12-bundle-c-T-D.10): <description>` for banner predicate widening + 14-VM regression suite
  - `test(phase12-bundle-c-T-D.11): <description>` for synthetic-fixture payload-contract acceptance test
  - `docs(phase12-bundle-c-T-D.12..13): <description>` for cycle-checklist + CLAUDE.md gotcha additions
  - `test(phase12-bundle-c-T-D.14): <description>` for briefing.md E2E
  - `fix(phase12-bundle-c-D): Codex RN <severity> #N — <description>` for Codex-driven fixes
- **NO Claude co-author footer.** This is a CLAUDE.md binding convention. Per fresh forward-binding lesson #7 (Phase 12 Sub-sub-bundle C.B 2026-05-15) — do NOT add `Co-Authored-By: Claude Opus 4.7 (1M context) <noreply@anthropic.com>` (or any other Co-Authored-By footer attributing the AI assistant) to ANY commit message. Subagent context starts isolated; the Bash tool's default footer template is NOT authoritative for this project — CLAUDE.md is. C.B R1 fix-bundle 4 commits carried the footer accidentally + required orchestrator-side rebase-strip pre-merge; C.C ship's explicit citation of this convention produced ZERO footer drift across 23 commits — pattern works. **This dispatch MUST NOT repeat the C.B drift pattern.**
- **NO `--no-verify`**, **NO `--amend`** (per CLAUDE.md binding conventions: prefer `git add <specific-files>` over `git add -A`).
- **TDD:** failing test first, minimal implementation, pass, commit. Per-task `- [ ]` checkboxes in plan §E mark per-step boundaries.

### §1.4 Branch isolation + ownership

- Commits on branch only; no push to origin from worktree until C.D integration commit (T-D.14 worktree push).
- **Implementer (you) owns:** task-family TDD commits → marker-file removal → pre-Codex review (NEW C.C lesson #6) → adversarial-critic → return report.
- **Operator owns:** witnessed verification gate (§3 surfaces below — 10 surfaces).
- **Orchestrator owns:** integration merge to main + post-merge housekeeping + Sub-bundle C arc-closer aggregate banking + V2 mapper widening dispatch commissioning.

### §1.5 Verify command

PowerShell from inside worktree:

```powershell
git log --oneline HEAD~20..HEAD
python -m pytest -m "not slow" -q
python -m pytest -m slow tests/integration/test_phase12_bundle_c_payload_contract_acceptance.py -v   # T-D.11
ruff check swing/ --statistics
python -c "from swing.trades.reconciliation_ambiguity_choices import get_choice_menu, ChoiceMenuItem; print(len(get_choice_menu('multi_partial_vs_consolidated')))"
python -c "from swing.trades.reconciliation_backfill import run_backfill, BackfillSummary, BackfillPipelineActiveError; print('backfill OK')"
python -c "from swing.integrations.schwab.trader import get_account_orders_audited; import inspect; print(inspect.signature(get_account_orders_audited))"
```

---

## §2 Adversarial review (Codex)

Invoked automatically by `copowers:executing-plans` after all 16 tasks land + tests GREEN + after the pre-Codex orchestrator-side review (NEW C.C lesson #6 — implementer MUST do an explicit dispatched-reviewer-subagent pass BEFORE invoking adversarial-critic).

**Expected chain shape:** 4-6 substantive Codex rounds (matches Phase 12 Sub-sub-bundle C.B 5 rounds for multi-CLI-surface scope; convergent tapering per Phase 8 R2-R5 + Phase 9/10/11/12 lesson family). Plan §E + spec §6 + §8 absorbed 8+ Critical + 14+ Major across writing-plans + brainstorm chains; execution rounds should converge faster.

**Adversarial review watch items (C.D-specific; pass as targeted prompts to `copowers:adversarial-critic`):**

1. **Manual-resolver allowlist tightness LOCK at T-D.3** (NEW C.C lesson #1). `resolve-ambiguity` CLI's `--choice` validation MUST use `get_choice_menu(ambiguity_kind)` member list, NOT regress to `RESOLUTION_TYPES`. Discriminating test: invoke CLI with `--choice auto_corrected_from_schwab` (service-owned state) → assert exit 2 + clear routing-hint error message.
2. **Per-choice `--custom-value` enforcement LOCK at T-D.3** (Codex R5 Major #2 LOCK; per-choice not suffix-based). CLI rejects `requires_custom_value=True` choice without `--custom-value` flag. Discriminating test: per ChoiceMenuItem with `requires_custom_value=True`, invoke without `--custom-value` → assert clear error message naming the missing flag + exit 2.
3. **Shape predicate tightening at handler entry** (NEW C.B lesson #5). Per service-owned choice with payload-required: per-handler 4-case parametrize (correct-shape happy / unrecognized-key reject / contradictory-field reject / missing-required-field reject + NaN/inf reject). T-D.3 CLI + T-D.11 synthetic-fixture acceptance test BOTH cover this; CLI-side parses with `json.loads(...)` + does shape validation before service invocation; service-side (C.C) validates again at apply time (defense-in-depth).
4. **Pass-2-tier-1-FORBIDDEN LOCK at T-D.8** (spec §8.4; Codex R3 Critical #1 + Major #1). Pass 2 source data is order-grain; classifier MUST emit tier-2 ALWAYS. Discriminating test: plant DHC fixture where Pass 2 returns N orders summing to journal qty + matching journal price; assert classifier emits tier-2 (NEVER tier-1) regardless.
5. **Backfill autocommit + service-tx-ownership LOCK at T-D.6** (Codex R2 Major #1 LOCK). Backfill orchestrator does NOT open BEGIN IMMEDIATE; service helpers (C.C public functions) own their own txs. Discriminating test: invoke `run_backfill(...)` with `_ExecuteSpyConn` wrapper; assert backfill code itself never issues `BEGIN IMMEDIATE` (the service entry points do via their inner BEGIN IMMEDIATE).
6. **Pipeline-exclusion guard at T-D.6** (Codex R2 Major #2 fix). `BackfillPipelineActiveError` raised at backfill entry if `pipeline_runs.state='running'` is non-empty. Discriminating test: plant a `pipeline_runs.state='running'` row; invoke `run_backfill(...)` → assert raises `BackfillPipelineActiveError` cleanly.
7. **`_audited_get_account_orders` backward-compat regression at T-D.6.1** (Codex R4 Major #3 implementation-seam explicit). Refactor `_call_endpoint(...)` opt-in `return_call_id: bool = False` kwarg. Backward-compat test asserts existing `get_account_orders(...)` signature + return shape unchanged; existing pipeline + flow-pivot callsites compile + tests pass.
8. **14-VM banner regression at T-D.10** (plan §A.5 14-VM-instance retrofit LOCK). All 14 base-layout VM instances across 9 files surface the widened count. Discriminating regression test plants a `resolution='pending_ambiguity_resolution' AND material_to_review=1` discrepancy → renders each base-layout-extending page → asserts banner count includes it.
9. **Sandbox short-circuit propagation at T-D.7 + T-D.8** (NEW C.C lesson #2). `environment` keyword propagates from CLI cfg into every public-service call. Discriminating test: invoke `run_backfill(..., environment='sandbox')` against tier-1-eligible discrepancy + assert `fills.price` unchanged + assert no `reconciliation_corrections` row + `BackfillSummary.tier1_applied == 0`.
10. **`--retry-pass-2-failures` flag scoped iteration LOCK at T-D.9** (Codex R5 Major #1 fix). Flag scopes iteration to rows WHERE `resolution = 'pending_ambiguity_resolution' AND ambiguity_kind = 'unsupported' AND resolution_reason LIKE '%Pass 2 re-fetch failed%'`. Discriminating test: plant mixed-state DB (some unresolved + some Pass-2-failed); without flag, default skips Pass-2-failed; with flag, re-attempts Pass 2 only on Pass-2-failed.
11. **Tier-3 override CLI confirmation prompt + `--force` flag at T-D.4** (spec §6.4 + OQ-8 ACCEPT). Without `--force`, prompts `"Override this correction? [y/N]"`; non-y answer → exits 0 with `"(aborted)"`. Discriminating tests: 3 cases — `--force` (skips prompt) / `"n"` stdin (aborted) / `"y"` stdin (applied).
12. **`AlreadySupersededError` chain-head guidance at T-D.4** (spec §6.4 + OQ-15 disposition). CLI catches exception + maps to friendly `"correction {id} is already superseded by correction {N}; override the chain head ({N}) instead"` + exit 2. Discriminating test: plant a superseded chain → invoke `override-correction <superseded_id>` → assert clear error naming the chain-head correction_id.
13. **`apply_overrides` discipline at any Schwab entry point** (Sub-bundle B lesson #6). T-D.6.1 `get_account_orders_audited(...)` wraps `get_account_orders(...)`; the construction of `schwab_client` in `run_backfill` MUST `apply_overrides(cfg)` at the entry point. Verify via integration test that cascade-resolved credentials thread through.
14. **NO behavioral changes to NON-touched existing surfaces.** C.D modifies the touch list in §0.4 above + NO other production files should change. Codex SHOULD verify the touch surface is bounded.
15. **Plan-author schema additions during executing-plans cycle (C.A return report lesson #7).** If Codex surfaces a need for a schema element NOT in plan §E + spec §3 (e.g., new audit column; new CHECK enum value; new FK relationship), the implementer MUST STOP + escalate to orchestrator BEFORE adding inline. Cost of bank-after-write: 2-3 cascade-cleanup rounds.
16. **Synthetic-fixture-only acceptance test (S6a) discipline at T-D.11** (spec §15.5 LOCKED revised mechanic per R6+R7+R8 cascade). T-D.11 test runs against isolated tmp `swing.db` (NOT operator's production `~/swing-data/swing.db`); table-driven across ALL 11 payload-required + 7 no-payload choices; per-class assertions split by mutation-class / split-class / audit-only-class / no-payload-class. **DO NOT** weaken to a single representative case — Codex R1 Major #7 fix LOCKS table-driven coverage.

---

## §3 Operator-witnessed verification gate (Sub-sub-bundle C.D integration — 10 surfaces — THE BIG ONE)

Per plan §G.4 + spec §15.5 LOCKED revised mechanic (Codex R6 + R7 + R8 cascade):

| Surface | Type | Acceptance |
|---|---|---|
| **S1** | Inline `pytest -m "not slow" -q -n auto` | GREEN at ~4259-4324 fast tests (worktree-side; +55-120 net from 4204 baseline; upper-half overshoot precedent); 3 pre-existing phase8 walkthrough failures unchanged; 5 skipped. **ALL forward-binding pins (F-1 through F-10) pass.** T-D.11 slow-marked synthetic-fixture acceptance test PASSES under `-m slow`. |
| **S2** | `swing journal reconcile-backfill --dry-run` against operator's production DB | Operator-driven walkthrough. Expected output: classification matrix with disc 41 CVGI projected tier-1 + disc 39 DHC + disc 40 VSAT projected Pass-2-required. **Pass-2 re-fetches consume Schwab API quota for DHC + VSAT** (2 calls; each writes `schwab_api_calls` audit rows; NO journal mutations per §8.2 dry-run scope LOCK). **Pre-gate operator check: confirm Schwab refresh-token TTL > 1hr** (operator may need to re-auth via `/schwab/setup` web form OR `swing schwab setup` CLI if the production token expired since 2026-05-15T17:05:00+00:00). |
| **S3** | `swing journal reconcile-backfill --apply --ticker CVGI` against production | **PRODUCTION WRITE.** Verifies disc 41 auto-corrected end-to-end per spec §10.1: `fills.fill_id=<CVGI>.price=$5.30` (was $5.23); `trades.<CVGI>.current_avg_cost = $5.30`; `reconciliation_corrections` row with `correction_action='auto_applied'`; `reconciliation_discrepancies.discrepancy_id=41.resolution='auto_corrected_from_schwab'`; `trade_events` row with `event_type='reconciliation_auto_correct'`; CLI summary line "Tier 1 applied: 1; Tier 2 stamped: 0". |
| **S4** | `swing journal reconcile-backfill --apply --ticker DHC` AND `--apply --ticker VSAT` (separate invocations OR single invocation; operator preference) | **PRODUCTION WRITE.** Verifies DHC 39 + VSAT 40 stamped tier-2 with `resolution='pending_ambiguity_resolution'` + `ambiguity_kind` populated per actual Pass-2 outcomes (one of §10.2/§10.3 Cases A/B/C). Phase 10 dashboard banner now shows count=2 (T-D.10 banner widening verified end-to-end). |
| **S5** | `swing journal discrepancy show-ambiguity 39` | Operator runs the show command; verifies output matches expected menu for DHC 39's actual `ambiguity_kind` per S4 Pass-2 outcome. Verifies `[RECOMMENDED]` tag on `keep_journal_as_is` if `multi_partial_vs_consolidated`. |
| **S6** | **S6a synthetic-fixture-only payload-contract acceptance test + S6b operator-real-disposition of production DHC 39** | **S6a (LOCKED post-Codex R6 M#3 + R7 M#3 + R8 M#1+M#2):** the gate fixture runs the T-D.11 table-driven integration test suite which exercises ALL 11 payload-required choices PLUS all 7 no-payload choices against isolated tmp DBs (one fresh DB per case; discarded at case end). Each payload-required case exercises BOTH parse-time `--custom-value` rejection AND success-path. **Per-class assertions** — mutation-class / split-class / audit-only-class / no-payload-class per spec §15.5 LOCK. **S6b operator's REAL disposition of production DHC 39 per their actual data — NO contortion.** Options: `keep_journal_as_is` (V1 default; expected most common if no broker-statement consultation) OR `consolidate_using_operator_vwap` / `split_into_partials` / `operator_truth` / `custom` with real `--custom-value` if operator has execution-level data. Post-S6b: DHC 39 in `resolution='operator_resolved_ambiguity'`; banner count=1. |
| **S7** | `swing journal discrepancy show-ambiguity 40` + `resolve-ambiguity 40 --choice <picked> --reason "..."` for VSAT 40 | Operator's REAL disposition per actual Pass-2 outcome. **Codex R8 Minor #2 LOCK:** payload-contract surface already satisfied at S6a's synthetic-fixture run — S7 does NOT need to exercise a payload-required choice on the production VSAT case. Operator dispositions per their actual data without contortion. Post-S7: VSAT 40 in `resolution='operator_resolved_ambiguity'`; banner count=0. |
| **S8** | Phase 10 dashboard banner clears to ZERO via `swing web --port 8081` | **PRODUCTION-WRITE-VERIFICATION SURFACE.** Operator opens `/dashboard` in browser via worktree-side `swing web --port 8081` (NOT 8080 — operator's main session uses 8080); asserts banner count=0. T-D.10 banner widening verified end-to-end. Verify banner correctly incremented at S4 (count=2 when DHC + VSAT landed in pending) AND decremented after S6+S7 (count=0). OQ-7 acceptance evidence. **Stop the web server when done.** |
| **S9** | `ruff check swing/ --statistics` | Reports 18 E501 unchanged. |
| **S10** | Cycle-checklist + CLAUDE.md gotcha additions verified | Operator reads T-D.12 cycle-checklist updates + T-D.13 CLAUDE.md gotcha additions; confirms cadence makes sense + gotchas accurately describe the architectural pivot. |

**Gate session budget:** 10 surfaces. **The largest in project history.** Expect a long-haul operator-paired session (per `feedback_orchestrator_vs_implementer_execution.md` + handoff brief §0 LOCK).

**Production-write classifier soft-block awareness at S3+S4:** `reconcile-backfill --apply` against production DB is production-write. Operator pre-authorizes via gate-path AskUserQuestion OR plain-chat "yes" if Claude Code's production-write classifier soft-blocks. DO NOT proceed without explicit operator authorization.

**Production state post-gate:** 3 historical discrepancies dispositioned (all terminal states); banner cleared. **Production state CLEAN.**

---

## §4 OUT OF SCOPE (do not do)

- **Web Tier-2 surface** — spec §6.1 LOCK V1 CLI-only; web is V2 candidate (banked at plan §I.3). NOT C.D scope. (Note: a `/schwab/setup` web form precedent exists from Phase 12 Sub-bundle B; a similar `/discrepancies` route group is the V2 target, NOT C.D scope.)
- **Schema additions or migrations** — per C.A return report lesson #7 + NEW lesson 2026-05-15 at `657b8a0`. If C.D implementer encounters a need for a schema element NOT in plan §E + spec §3, STOP + escalate to orchestrator BEFORE adding inline. Do NOT bank-after-write. (e.g., the V2 candidate §I.13 `candidate_choices_json` column on `reconciliation_discrepancies` for richer Tier-2 surface — V1 LOCK uses `resolution_reason` text; do NOT add column.)
- **V2 mapper widening + auto-VWAP classifier path** — operator-locked next-architectural-dispatch slot (post-C.D ship). Banked at plan §I.1. NOT C.D scope. T-D.13 CLAUDE.md gotcha #3 documents the V1 Pass-2-tier-1-FORBIDDEN limitation — that documentation is the V1 deliverable; the actual mapper widening is V2.
- **New classifier sub-classifiers OR new validators** — C.B already shipped 10 sub-classifiers + 4 validators + `default_validator_chain` dispatcher. C.D consumes them; do NOT add new ones.
- **New `reconciliation_corrections` columns OR new CHECK enum values** — C.A schema is LOCKED at 20 columns + 4 indexes; C.A T-A.4 widenings (resolution + correction_action + ambiguity_kind + trade_events event_type) are LOCKED. If C.D implementer surfaces a need, STOP + escalate.
- **Behavioral changes to existing surfaces beyond the locked touch list** — see §0.4. NO other production files should change.
- **Re-litigating spec §1.3 four operator-locked architectural constraints** — accepted as given.
- **Re-litigating spec §6 + §8 + §15.5 LOCKs** — all spec LOCKS via Codex R9 convergence; do NOT re-open.
- **Re-litigating plan §E acceptance criteria** — all per-task LOCKs via plan-time Codex R6 convergence; do NOT re-open.
- **Operator-real disposition contortion at S6/S7 (production DHC 39 + VSAT 40)** — per spec §15.5 LOCK + Codex R8 cascade, operator dispositions per actual data; NO contrived `--custom-value` payloads required on real production cases; payload-contract surface satisfied via S6a synthetic-fixture-only acceptance test.
- **Direct DB edits OR `acknowledged_immaterial` resolutions for broker-truth divergences** — architectural anti-pattern per orchestrator-context.md "Operator architectural pushback supersedes orchestrator scope assumptions". Operator's reconciliation auto-correct architectural pivot is the architecturally-correct path; honor it end-to-end at gate.

---

## §5 Return report shape

After all 16 tasks land + Codex chain converges + before final return-report commit, draft a return report at `docs/phase12-bundle-C-D-return-report.md` (mirroring `docs/phase12-bundle-C-C-return-report.md` shape):

1. Final HEAD on branch + commit count breakdown (16 task-impl + N Codex-fix + 1 return-report).
2. Codex round chain (R1-RN summary table + convergent shape; finding-count taper).
3. Test count delta + ruff baseline delta + schema version delta (v19 unchanged — C.D touches no schema).
4. Operator-witnessed verification surfaces (PENDING orchestrator-driven gate; 10 surfaces).
5. Per-task deviations from plan (if any) with rationale.
6. Codex Major findings ACCEPTED with rationale (if any).
7. Watch items for orchestrator (V2 candidates surfaced; Sub-bundle C arc-closer aggregate readiness).
8. Worktree teardown status.
9. Per-task disposition LOCKS (any task-level decisions worth banking).
10. Forward-binding lessons for future bundles (especially V2 mapper widening dispatch).
11. CLAUDE.md status-line refresh draft text for orchestrator paste-in at integration-merge time. **AND** Sub-bundle C arc-closer aggregate draft text (per Phase 9 + Phase 10 + Phase 11 arc-closer aggregate precedents): commit count A+B+C+D; Codex rounds total; +cumulative fast tests; arc-cumulative ACCEPT-WITH-RATIONALE banked; CLAUDE.md gotchas promoted; V2.1 §VII.F amendments pending; V2 candidates banked.
12. Composition-surface verification: `^def ` grep on `swing/trades/reconciliation_backfill.py` + `swing/trades/reconciliation_ambiguity_choices.py` confirming public surface matches plan §E acceptance criteria.
13. Pipeline-exclusion-guard verification evidence (`BackfillPipelineActiveError` raised cleanly under `pipeline_runs.state='running'`).
14. Backward-compat verification evidence (T-D.6.1 existing `get_account_orders(...)` signature unchanged; existing callsites at `swing/pipeline/runner.py` + `swing/trades/schwab_reconciliation.py` compile + tests pass).
15. Phase 10 banner regression verification evidence (T-D.10 14-VM regression suite confirmed GREEN; banner correctly increments + decrements per S4 → S6+S7 lifecycle).
16. Synthetic-fixture acceptance test verification evidence (T-D.11 table-driven all 18 entries GREEN under `-m slow`).

---

## §6 Dispatch metadata

- **Subagent type:** `general-purpose` (full tool surface needed).
- **Foreground vs background:** foreground (default).
- **Worktree:** YES — per §1.1.
- **Model:** defer to harness default.
- **Expected duration:** 16-22 hr implementation + 4-7 hr Codex; total ~20-29 hr.

---

## §7 If you get stuck

- If plan §E binding contracts conflict with what spec §6/§8/§15.5 says, **plan wins** (writing-plans Codex chain ratified plan §E; spec is upstream input).
- If a Codex round produces a finding you can't disposition without orchestrator input, ACCEPT-with-rationale + flag explicitly in return report.
- If you need a schema element NOT in plan §E + spec §3, **STOP + escalate** (C.A return report lesson #7 + NEW lesson 2026-05-15 at `657b8a0`; bank-after-write costs 2-3 cascade-cleanup rounds).
- If a per-(ambiguity_kind, choice_code) menu entry at T-D.2 needs an enumeration NOT in spec §6.2.1, STOP + escalate (spec §6.2.1 is LOCKED post-Codex chain; new ambiguity_kind or choice_code values require spec amendment).
- If a per-handler shape predicate at T-D.3 surfaces edge cases not covered by C.B lesson #5 family, log as deviation in return report §9 for orchestrator review.
- DO NOT propose new classifier sub-classifiers, new validators, OR new C.C service functions within C.D scope (§4 lock).
- DO NOT propose web Tier-2 surface within C.D scope (§4 lock; V2 candidate at plan §I.3).
- DO NOT propose schema additions within C.D scope (§4 lock; lesson #7 family).
- DO NOT add `Co-Authored-By` footer to any commit message (per §1.3 + fresh forward-binding lesson #7; C.B R1 fix-bundle precedent of accidental drift required orchestrator-side rebase-strip pre-merge — C.C ship's explicit citation prevented recurrence — do NOT regress).
- DO NOT propose V2 mapper widening within C.D scope (§4 lock; operator-locked post-C.D dispatch slot per OQ-4).
- DO NOT propose direct DB edits OR `acknowledged_immaterial` resolutions for broker-truth divergences (architectural anti-pattern).
- If you encounter a Phase 7/8/9/10/11/12-A/12-B/12-C-A/12-C-B/12-C-C lesson that conflicts with a C.D implementation proposal, the prior-phase lesson wins (validated by ship-experience). Surface the conflict as a constraint.
- If Codex pushes back on the backfill autocommit posture at T-D.6 (e.g., "but a single outer tx is simpler..."), HOLD THE LINE — the LOCK is Codex R2 Major #1 fix at writing-plans time; service helpers own their own transactions; backfill is autocommit because the per-service BEGIN IMMEDIATE owns each per-discrepancy boundary atomically.
- If Codex pushes back on the Pass-2-tier-1-FORBIDDEN LOCK at T-D.8 (e.g., "but Pass 2 data could redirect tier-1..."), HOLD THE LINE — the LOCK is spec §8.4 + Codex R3 Critical #1 + Major #1 fix at writing-plans time; V1 mapper exposes only order-level price; auto-correcting from order-level to execution-level is a §4.4 determinism violation. V2 mapper widening dispatch unblocks this.
- If Codex pushes back on the synthetic-fixture-only acceptance test at T-D.11 (e.g., "operator-real cases would be more realistic..."), HOLD THE LINE — the LOCK is spec §15.5 + Codex R6 M#3 + R7 M#3 + R8 M#1+M#2 cascade; audit-trail integrity of production DB is binding; forcing operator into contrived dispositions to exercise payload-required contract surfaces would contaminate the production audit trail.
- **Pre-Codex orchestrator-side review (NEW C.C lesson #6)**: before invoking `copowers:adversarial-critic`, dispatch a focused reviewer subagent with the plan §E acceptance criteria + brief §0.5 BINDING contracts as anchors; ask for a deviation list ≤600 words. Cheap; absorbs LOCK divergences pre-Codex; saved 1-2 Codex rounds on C.C. Apply explicitly here given C.D's 10-surface gate stakes.

---

## §8 Operator-paired gate notes

C.D's 10-surface gate is the LARGEST in project history. Plan for a long-haul operator-paired session:

- **Production refresh-token clock** — expires ~2026-05-22; verify TTL > 1hr at S2 pre-check; operator re-auths via `/schwab/setup` web form OR `swing schwab setup` CLI if needed.
- **Production-write classifier soft-block** — S3 + S4 are production writes; operator pre-authorizes via gate-path AskUserQuestion OR plain-chat "yes".
- **One command at a time** — per operator preference (handoff brief §0 LOCK); orchestrator sends ONE command per turn, waits for output, verifies, sends next.
- **Worktree-side web server** — S8 uses `swing web --port 8081` (NOT 8080); stop the server when S8 done.
- **S6a runs FIRST** before S6b — synthetic-fixture acceptance test discharge BEFORE operator real-disposition (per spec §15.5 LOCK).
- **Schwab API quota awareness** — S2 dry-run consumes 2 Pass-2 re-fetches (DHC + VSAT); S4 apply re-fetches the same window (potentially another 2 calls if caching doesn't reuse). Operator's Schwab Developer Portal has rate limits; pace accordingly.
