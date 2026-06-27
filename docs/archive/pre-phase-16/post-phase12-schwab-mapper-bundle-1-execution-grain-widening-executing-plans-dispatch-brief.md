# Post-Phase-12 Sub-bundle 1 — V2 mapper widening + classifier consumer + comparator + housekeeping (FOLDED) — Executing-plans Dispatch Brief

**Audience:** Fresh Claude Code instance with no prior conversation context.

**Mission:** Execute Sub-bundle 1 of the post-Phase-12 Schwab mapper execution-grain widening implementation plan via `copowers:executing-plans`. Plan is `docs/superpowers/plans/2026-05-17-schwab-mapper-execution-grain-widening-plan.md` §A (Sub-bundle 1 scope; 14 tasks T-1.0 … T-1.13; housekeeping micro-fixes FOLDED per operator decision 2026-05-17). All per-task acceptance criteria + tests + commit shapes are in the plan; this dispatch brief is a worktree-config + scope wrapper, NOT a duplicate spec.

**Expected duration:** ~10-16 hr implementation + ~3-6 hr Codex convergence + 1 operator-paired cassette session (~30-60 min). Total ~14-23 hr. Sub-bundle 1 is the **architectural headline** closing the V1 limit-vs-fill defect family (CVGI + LION 2026-05-17 falsification evidence; CLAUDE.md `Pass-2-tier-1-FORBIDDEN` gotcha amendment becomes V1-RESOLVED for Pass-1). Includes the **mid-dispatch operator pause for cassette session** (T-1.0 ships first, operator records cassettes on the worktree branch, then T-1.1..T-1.13 implementation resumes).

**Skill posture:**
- Invoke `copowers:executing-plans` against the plan path scoped to Sub-bundle 1 (`PLAN_PATH=docs/superpowers/plans/2026-05-17-schwab-mapper-execution-grain-widening-plan.md`, `SCOPE=Sub-bundle 1 only (T-1.0..T-1.13)`).
- The skill wraps `superpowers:subagent-driven-development` + adversarial Codex review.
- Adversarial review runs after all 14 tasks land. Expected **3-5 Codex rounds** (matches Phase 12 Sub-sub-bundle C.C 3 rounds for mid-complexity scope; Sub-bundle C.D 4 rounds + Phase 12 Sub-bundle B 4 rounds for multi-surface scope; rounds may compress because plan §A absorbed 6 rounds of Codex review at writing-plans time + ZERO ACCEPT-WITH-RATIONALE banked + 4 brief-vs-shipped-code deviations already flagged + addressed).

---

## §0 Inputs

### §0.1 Plan

- **PLAN_PATH:** `docs/superpowers/plans/2026-05-17-schwab-mapper-execution-grain-widening-plan.md` (1215 lines; Codex R1-R6 convergence with all findings closed at MAX_ROUNDS+1 per operator-override pattern; LOCKED at `cc6fd2d`).
- **Sub-bundle 1 section** is plan §A (lines 57-622). Self-contained per-task spec with TDD checkboxes (`- [ ]`).
- **Plan §A.0** pre-verifications all completed against shipped code with verbatim grep results (12 verifications; pinned at file:line citations).
- **Plan §A.0.1** brief-vs-shipped-code deviations flagged (D1-D4; all addressed in-plan): D1 `show-correction` subcommand NEW at T-1.12; D2 CVGI date typo no-op-with-note at T-1.11; D3 status triplet LIVE/PROVISIONAL/DEGRADED (Sub-bundle 2 concern; V2.1 §VII.F amendment banked); D4 comparator candidate-pool filter widening at T-1.6 + T-1.7.
- **Plan §H.1** Sub-bundle 1 operator-witnessed gate (9 surfaces; see §3 below).
- **Plan §F** cassette runbook + sanitization filter spec (drafted in T-1.0; HARD PREREQ for T-1.1..T-1.13).
- **Plan §G** cassette acceptance criteria (per T-1.0 + T-1.13).

### §0.2 Spec

- **SPEC_PATH:** `docs/superpowers/specs/2026-05-17-schwab-mapper-execution-grain-widening-design.md` (1086 lines; Codex R1-R4 substantive + R5 advisory; ZERO ACCEPT-WITH-RATIONALE; LOCKED at `dda8730`).
- **Read for §3 architectural shape** (Shape C predicate emergence; V1 LIFT scope = Pass-1 only; module touch list) + **§4 SchwabExecutionLeg + SchwabOrderResponse extension** (BINDING) + **§5 comparator path** (`_compute_execution_price` helper + `_resolve_match_quantity` helper + comparator switch at line 693) + **§6 OQ dispositions** (all 6 LOCKED) + **§8 housekeeping micro-fixes** (CVGI date no-op; gotcha amendment; show-correction generic addendum) + **§10 discriminating-example walkthroughs** (CVGI fill_id=9 + LION fill_id=15 + 4 cassette order types).

### §0.3 Project state at dispatch time

- **HEAD on `main`:** `cc6fd2d` (post-writing-plans-merge). Brief commit lands at HEAD+1 pre-dispatch.
- **Test count:** **~4363 fast passing on main** + 3 pre-existing failures (phase8 walkthrough; unchanged since Phase 8) + 5 skipped. Verify inline at brief drafting time.
- **Ruff baseline:** **18** (E501 only; unchanged across Phase 11 + Phase 12 + post-Phase-12 brainstorm + writing-plans).
- **Schema version:** **v19** (LOCKED since Phase 12 Sub-sub-bundle C.A 2026-05-15; Sub-bundle 1 is consumer-side only). **Sub-bundle 1 MAY NOT widen schema** (spec §1.3 + plan §C.5 escalation rule).
- **Production discrepancy state:** ZERO unresolved-material (all 7 from C.D gate dispositioned in terminal states). Phase 10 dashboard banner count=0. **Sub-bundle 1 ship is the architectural fix that prevents CVGI/LION-family false-positive emissions going forward** (the historical correction chains at correction_ids 1-6 remain leave-as-is per OQ-G; T-1.12 generic ID-free `show-correction` CLI help-text addendum documents the V1 limit-vs-fill historical context).
- **Production refresh-token clock:** expires ~2026-05-22T17:05:00+00:00. **Operator may need to re-auth via `/schwab/setup` web form OR `swing schwab setup` CLI before T-1.0 cassette session.** T-A.2 self-healing means recovery is one CLI/web invocation now.
- **Production-write classifier soft-block awareness:** S3 dry-run + S4 OPTIONAL apply at the gate are production-writes against operator's REAL DB. Operator pre-authorizes via gate-path AskUserQuestion or plain-chat "yes" if Claude Code's production-write classifier soft-blocks. **DO NOT proceed without explicit operator authorization** (4 NEW C.D-arc lesson #2: production-write classifier soft-block fires PER-INVOCATION even after AskUserQuestion authorization).
- **Worktree husks:** ALL CLEAN as of brief drafting time.

### §0.4 Sub-bundle 1 scope (14 tasks per plan §A)

| Task | Title | Files (illustrative; plan §A locks) |
|---|---|---|
| **T-1.0** | Cassette runbook + sanitization filter spec + NEW `scripts/record_schwab_cassettes.py` recording script (DOCS + TEST-INFRA; FIRST commit; lands BEFORE operator cassette session) | NEW `scripts/record_schwab_cassettes.py` + extend `tests/conftest.py` `vcr_config` + plan §F runbook docs + NEW `tests/integrations/test_record_schwab_cassettes_script.py` |
| **T-1.1** | NEW `SchwabExecutionLeg` dataclass + `__post_init__` validators (`math.isfinite()` on price/quantity; positive guards) | MODIFY `swing/integrations/schwab/models.py` + NEW `tests/integrations/test_schwab_execution_leg_dataclass.py` |
| **T-1.2** | `SchwabOrderResponse.executions: list[SchwabExecutionLeg] \| None = None` tri-valued field extension | MODIFY `swing/integrations/schwab/models.py` + NEW `tests/integrations/test_schwab_order_response_executions_field.py` |
| **T-1.3** | `map_orders_to_fill_candidates` body extension (extract `orderActivityCollection[].executionLegs[]`; defensive parsing; mapper coherence-check distinguishing legitimate partial fills from malformed leg totals — `sum(legs.quantity) == order.filledQuantity` preserves; else collapses to `executions=None`) | MODIFY `swing/integrations/schwab/mappers.py` + NEW `tests/integrations/test_mapper_execution_grain_extension.py` |
| **T-1.4** | NEW `_compute_execution_price(so)` helper (single-leg → leg price; multi-leg → VWAP; absent → None) | MODIFY `swing/trades/schwab_reconciliation.py` + NEW `tests/trades/test_compute_execution_price.py` |
| **T-1.5** | NEW `_resolve_match_quantity(so)` helper for quantity-grain switch (`sum(legs.quantity)` when executions populated; else `so.quantity`) | MODIFY `swing/trades/schwab_reconciliation.py` + NEW `tests/trades/test_resolve_match_quantity.py` |
| **T-1.6** | Comparator price-path switch at `schwab_reconciliation.py:693` to execution-grain via `_compute_execution_price` + Path B `execution_unavailable=true` sentinel emit when None + **comparator candidate-pool filter widening via `_is_execution_bearing_candidate` for MARKET fills with `price=None` + partial-then-canceled CANCELED-with-filledQuantity>0** (per plan §A.0.1 D4 + Codex R1 M#1+M#2) | MODIFY `swing/trades/schwab_reconciliation.py` + NEW `tests/trades/test_comparator_price_path_switch.py` |
| **T-1.7** | Comparator quantity-match switch to execution-grain via `_resolve_match_quantity` (Codex R1 M#2 fix at writing-plans; closes the in-row quantity comparison defect) | MODIFY `swing/trades/schwab_reconciliation.py` + NEW `tests/trades/test_comparator_quantity_match_switch.py` |
| **T-1.8** | NEW Shape C predicate `source_keys == {"price"} \| _EXECUTION_AUDIT_KEYS` at `_classify_entry_price_mismatch` + `_classify_close_price_mismatch` (Sub-bundle C.B Shape A + Shape B preserved unchanged); 4-case parametrize discriminating test (Shape A preserved; Shape B preserved; Shape C newly recognized; mixed/partial Shape C → tier-2) + audit-key persistence contract | MODIFY `swing/trades/reconciliation_classifier.py` + NEW `tests/trades/test_shape_c_predicate.py` |
| **T-1.9** | `_classify_unmatched_fill_shared` Path B `execution_unavailable=true` sentinel recognition (V1 Pass-2 STAYS tier-2-always; Pass-2 LIFT entirely deferred OQ-F V2; this task ONLY adds sentinel recognition emitting tier-2 `unsupported` with clearer `correction_reason`) | MODIFY `swing/trades/reconciliation_classifier.py` + NEW `tests/trades/test_unmatched_fill_path_b_sentinel.py` |
| **T-1.10** | CLAUDE.md `Pass-2-tier-1-FORBIDDEN` gotcha amendment (V1-RESOLVED for Pass-1; Pass-2 stays V1 tier-2-always; retain V1 historical context — CVGI + LION 2026-05-17 falsification evidence; reference V2 mapper widening dispatch + this spec + commit chain) — HOUSEKEEPING #2 FOLDED | MODIFY `CLAUDE.md` |
| **T-1.11** | CVGI date typo verification + no-op-with-note (housekeeping §8.1; brainstorm + brief verified ZERO matches; T-1.11 ships as no-op-with-note in commit message + plan §A.1.11) | NO FILE CHANGES (commit message only documenting the no-op) |
| **T-1.12** | NEW `swing journal discrepancy show-correction <id>` CLI subcommand + generic ID-free help-text addendum (per spec §8.3 OQ-G + plan §A.0.1 D1) — works on ANY DB; cites spec path + V1 limit-vs-fill historical context; renders via `--help` flag — HOUSEKEEPING #3 FOLDED | MODIFY `swing/cli.py` + NEW `tests/cli/test_discrepancy_show_correction_cli.py` |
| **T-1.13** | End-to-end integration test against cassette-recorded 4 order types (LIMIT BUY + LIMIT SELL + STOP FIRED + MARKET BUY; stretch STOP_LIMIT FIRED) — consumes cassettes at `tests/integrations/cassettes/schwab/test_e2e_*.yaml` | NEW `tests/integration/test_schwab_mapper_widening_e2e.py` |

**Cross-bundle dependencies:** Sub-bundle 1 CONSUMES Sub-bundle C.A schema (`reconciliation_corrections` table + `ambiguity_kind` column + CHECK enum widenings at v19) + Sub-bundle C.B `classify_discrepancy` + `default_validator_chain` + Sub-bundle C.C `apply_tier1_correction` + Sub-bundle C.D `swing journal discrepancy` CLI group + Phase 11 Sub-bundle B `SchwabOrderResponse` dataclass + Phase 11 Sub-bundle B `map_orders_to_fill_candidates` mapper + Phase 12 Sub-bundle B `apply_overrides(cfg)` + `resolve_credentials_env_or_prompt(cfg, environment, allow_prompt=False)` + `construct_authenticated_client` 4-arg signature.

**Module boundaries (BINDING — preserve discipline):**
- `swing/integrations/schwab/models.py`: dataclass extension layer. `SchwabExecutionLeg` NEW + `SchwabOrderResponse.executions` field. `__post_init__` validators per Sub-bundle C.B forward-binding lesson #5 (shape predicate tightening discipline).
- `swing/integrations/schwab/mappers.py`: mapping layer. Defensive parsing; never raises on malformed leg; coherence-check distinguishes legitimate partial fills vs malformed leg totals.
- `swing/trades/schwab_reconciliation.py`: comparator + helpers (`_compute_execution_price`, `_resolve_match_quantity`, `_is_execution_bearing_candidate`). Pure functions; no DB writes; no transaction management.
- `swing/trades/reconciliation_classifier.py`: classifier layer. NEW Shape C predicate at Pass-1 classifiers; Path B sentinel recognition at `_classify_unmatched_fill_shared` (Pass-2 STAYS tier-2-always V1).
- `swing/cli.py`: CLI entry points. T-1.12 `show-correction` subcommand under existing `swing journal discrepancy` group.
- `scripts/record_schwab_cassettes.py`: standalone cassette recording script (NEW; T-1.0). Decoupled from test file; `argparse` CLI; `apply_overrides(cfg)` + `resolve_credentials_env_or_prompt(cfg, environment, allow_prompt=False)` + `construct_authenticated_client` discipline preserved.

### §0.5 BINDING contracts from plan §A + §D (DO NOT re-litigate)

Per writing-plans return report + plan §A locked-decisions:

1. **Schema MUST stay at v19** (plan §C.5 escalation rule + spec §1.3). If implementer surfaces a need for schema element NOT in spec §3 + plan §A, STOP + escalate to orchestrator BEFORE adding inline. Bank-after-write cost: 2-3 cascade-cleanup rounds.
2. **V1 LIFT scope = Pass-1 only LOCK** (spec §1.5 + §6.6). Pass-2 `unmatched_*_fill` classifier widening LIMITED to Path B `execution_unavailable=true` sentinel recognition. Re-running Sub-bundle C.B's Pass-2-tier-1-FORBIDDEN parametrized test (6 distinct input shapes) MUST still pass post-Sub-bundle-1.
3. **Shape C predicate is ADDITIONAL** (not replacement). Sub-bundle C.B Shape A + Shape B predicates preserved unchanged. Discriminating test 4-case parametrize: Shape A preserved (C.B tests still pass); Shape B preserved (C.B tests still pass); Shape C newly recognized; mixed/partial Shape C → tier-2 (defense-in-depth determinism principle per spec §4.4 inheritance from Sub-bundle C.B).
4. **Comparator candidate-pool filter widening at T-1.6 + T-1.7** (Codex R1 M#1+#2 fix). V1 filter at `schwab_reconciliation.py:641-645` excluded MARKET fills with `price=None` AND partial-then-canceled `status='CANCELED'`-with-`filledQuantity>0` orders. V2's mapper widening is useless for these cases without filter widening. `_is_execution_bearing_candidate` helper distinguishes execution-bearing vs non-execution-bearing candidates.
5. **Backward-compat fall-through = Path B** (spec §6.1 OQ-A LOCK). When `orderActivityCollection` missing/empty → comparator emits `unmatched_open_fill`/`unmatched_close_fill` with `execution_unavailable=true` sentinel → classifier emits tier-2 `unsupported` with clearer reason. Discriminating test for both branches.
6. **VWAP comparator V1** (spec §6.2 OQ-B LOCK). Single-leg → leg price; multi-leg → `sum(leg.price * leg.quantity) / sum(leg.quantity)`. Leg-by-leg audit deferred OQ-F V2.
7. **`price_tolerance=0.01` retained** (spec §6.3 OQ-C LOCK). NO tightening to mil precision.
8. **FIRED-stop discipline = Path A mirror entry-fill** (spec §6.4 OQ-D LOCK). `executionLegs[].price` consumed uniformly for FILLED orders regardless of `order_type` (LMT/MKT/STOP/STOP_LIMIT). `stop_mismatch` path for WORKING stops UNCHANGED.
9. **Cassette session HARD PREREQ for T-1.1..T-1.13** (spec §6.5 OQ-E + operator decision 2026-05-17 + plan line 61). Mid-dispatch operator pause after T-1.0 ships (see §0.7 below). 4 order types minimum (LIMIT BUY + LIMIT SELL + STOP FIRED + MARKET BUY); stretch STOP_LIMIT FIRED.
10. **Tier-1 auto-redirect OQ-F deferred V2** (spec §6.6 LOCK). V1 mapper widening's classifier branch for `_classify_unmatched_fill_shared` does NOT lift Pass-2-tier-1-FORBIDDEN — only adds Path B sentinel recognition.
11. **Historical audit-row leave-as-is OQ-G** (spec §6.7 LOCK). NO retroactive UPDATE/DELETE on `reconciliation_corrections` rows 1-6. T-1.12 generic ID-free `show-correction` CLI help-text addendum documents the V1 historical context.
12. **`construct_authenticated_client` 4-arg signature BINDING** (writing-plans forward-binding lesson #1; Codex R6 M#1 fix). Every new Schwab API consumer (T-1.0 recording script) MUST resolve `client_id` + `client_secret` via `resolve_credentials_env_or_prompt(cfg, environment, allow_prompt=False)` BEFORE invoking the helper. Phase 12 Sub-bundle B + writing-plans precedent.
13. **vcrpy URI/path sanitization requires `before_record_request`** (writing-plans forward-binding lesson #2; Codex R2 C#1 fix). `filter_query_parameters` does NOT scrub URL path segments. Schwab Trader API embeds `accountHash` in `/trader/v1/accounts/{accountHash}/orders` path. T-1.0 cassette infrastructure installs BOTH `before_record_request` (URI/path) AND `before_record_response` (body) filters.
14. **NO behavioral changes to NON-touched existing surfaces** (plan §C.4). Especially: `stop_mismatch` path at `swing/trades/schwab_reconciliation.py:_find_working_stop_for_ticker` UNCHANGED (spec §1.1 lock #2); Sub-bundle C.A schema UNCHANGED; Sub-bundle C.B classifier Shape A + Shape B predicates UNCHANGED.

### §0.6 Forward-binding lessons inherited (BINDING for Sub-bundle 1)

**~60 cumulative lessons** through Sub-bundle 1 executing-plans:
- Phase 11 Schwab arc: 17 lessons (A 5 + B 7 + C 5 + D 0)
- Phase 12 Sub-bundle A: 5 lessons
- Phase 12 Sub-bundle B: 12 lessons
- Phase 12 Sub-bundle C brainstorm: 5 lessons
- Phase 12 Sub-sub-bundles C.A: 3 + C.B: 7 + C.C: 7 + C.D: 7 + 4 NEW C.D-arc = 28 lessons
- Post-Phase-12 brainstorm: ~5 lessons
- Post-Phase-12 writing-plans: 5 NEW lessons (return report; see top of brief)

**5 NEW writing-plans-banked lessons** (return report) — particularly load-bearing for Sub-bundle 1:

1. **`construct_authenticated_client` 4-arg signature BINDING.** Already in §0.5 #12 above.
2. **vcrpy URI/path sanitization requires `before_record_request`.** Already in §0.5 #13 above. T-1.0 sanitization filter spec extends `tests/conftest.py:88-110` `vcr_config`.
3. **Standalone recording scripts decouple cassette recording from test-file ordering.** Why this matters: T-1.13 is the test that consumes cassettes, but it doesn't exist at T-1.0 commit time. `scripts/record_schwab_cassettes.py` is the standalone recording script that ships in T-1.0 + ships BEFORE T-1.13 exists. Operator runs the script during the mid-dispatch pause to produce cassette YAML files. Prefer this over `@pytest.mark.vcr(record_mode='new_episodes')` when cassettes must exist before consumer test code.
4. **Spec-cited CLI surfaces MUST be empirically verified at writing-plans time.** Already absorbed via plan §A.0.1 deviations (D1 + D3 addressed). For Sub-bundle 1: T-1.12 NEW `show-correction` subcommand IS the spec-cited surface that didn't exist (D1) — implementation MUST land it.
5. **Candidate-pool filters need widening when adding new data sources.** Already absorbed via T-1.6 + T-1.7 + `_is_execution_bearing_candidate` helper. Codex R1 M#1+#2 caught the V1 filter at `schwab_reconciliation.py:641-645` excluded MARKET fills with `price=None` + partial-then-canceled orders.

**4 NEW C.D-arc lessons** (orchestrator-context.md `4b392fc`) — particularly load-bearing for Sub-bundle 1 gate:

1. **Operator-architectural-pushback mid-gate triggers STOP-and-recover.** S3 PRODUCTION DRY-RUN + S4 OPTIONAL APPLY at the gate may surface architectural divergences — if so, STOP, investigate, recover. NOT push-through.
2. **Production-write classifier soft-block fires PER-INVOCATION even after AskUserQuestion authorization.** S3 + S4 expect plain-chat "yes" per invocation; gate-driver does NOT batch authorizations.
3. **Orchestrator-inline gate-fix is a durable Phase-12-arc pattern (3 cumulative instances in C.D alone).** Discriminating-test enumeration includes the C.D gate-fix #1-#3 family pre-emptions: Windows cp1252 stdout encoder (avoid non-ASCII glyphs in any new CLI output OR rely on `swing/cli.py` entry's UTF-8 stdout reconfigure as defense-in-depth); synthetic-fixture-vs-production-emitter shape drift (per Sub-bundle 1 cassette-recorded test fixtures planting Schwab response shapes that match production emitter byte-for-byte).
4. **Pass-1 tier-1 entry_price_mismatch inherits limit-vs-fill defect from Pass-2-tier-1-FORBIDDEN family.** **THIS IS THE ARCHITECTURAL FIX SHIPPING IN SUB-BUNDLE 1.** Spec §8.2 Pass-2-tier-1-FORBIDDEN gotcha amendment marking V1-RESOLVED for Pass-1 ships in T-1.10.

### §0.7 Mid-dispatch operator pause for cassette session (CRITICAL)

Per plan line 61 + spec §6.5 OQ-E + operator decision 2026-05-17 — Sub-bundle 1 executing-plans dispatch has a **mid-dispatch operator pause** between T-1.0 and T-1.1..T-1.13:

**Sequence:**

1. **Implementer lands T-1.0** (cassette runbook + sanitization filter spec + NEW `scripts/record_schwab_cassettes.py` recording script + tests for the script). Commits land on worktree branch `schwab-mapper-bundle-1`.
2. **Implementer HALTS** with an explicit handoff message to operator citing the cassette runbook section §F.2 + the recording script's `--help` output + the expected cassette paths (`tests/integrations/cassettes/schwab/test_e2e_*.yaml`). DO NOT proceed to T-1.1.
3. **Operator pauses execution + runs the recording session ON THE WORKTREE BRANCH** (per plan line 61 wording — `cd .worktrees/schwab-mapper-bundle-1 ; python scripts/record_schwab_cassettes.py --order-type limit_buy ...` etc.). Operator may need to re-auth Schwab refresh-token first if expired (`/schwab/setup` web form OR `swing schwab setup` CLI; T-A.2 self-healing path).
4. **Operator commits the cassette YAML files** to the worktree branch (`git add tests/integrations/cassettes/schwab/ ; git commit`).
5. **Operator signals implementer to resume** (plain-chat "resume" or equivalent).
6. **Implementer resumes** with T-1.1..T-1.13 implementation, consuming cassettes via T-1.13 integration test.

**Implementer subagent MUST:**
- Land T-1.0 with explicit acceptance criteria PINNED in commit: (a) `scripts/record_schwab_cassettes.py` exists + `--help` flag works; (b) `tests/conftest.py:88-110` `vcr_config` extended with `before_record_request` + `before_record_response` filters; (c) plan §F runbook docs updated.
- After T-1.0 commit, output a clear handoff message: "**T-1.0 SHIPPED. Pausing for operator cassette session. Operator: please run `python scripts/record_schwab_cassettes.py` per plan §F.2 against your production Schwab credentials, commit the cassettes to this worktree branch, then signal resume.**"
- DO NOT proceed to T-1.1 until operator signals resume.

**Operator-paired session safety:**
- Recording script's `before_record_request` MUST scrub `accountHash` from URL paths before write.
- Recording script's `before_record_response` MUST scrub `access_token` + `refresh_token` + `accountHash` + `client_id` + `client_secret` from response bodies + headers.
- Recording script's `filter_query_parameters` + `filter_post_data_parameters` MUST cover OAuth params + authorization headers.
- Post-record validation gate at end of script SHOULD grep cassette files for sentinel-leak (per Phase 11 Sub-bundle A T-A.10 D1 redaction pattern).

### §0.8 Sub-bundle 1 test projection

Per plan §E: **+60-115 fast tests projected** (matches Phase 9/10/12 overshoot precedent at midline; actual likely +80-130 upper bound).

Final main HEAD post-Sub-bundle-1-merge: **~4423-4493 fast tests** (was ~4363 + +60-130).

---

## §1 Worktree + binding conventions

### §1.1 Worktree

- **Branch:** `schwab-mapper-bundle-1`
- **Worktree directory:** `.worktrees/schwab-mapper-bundle-1/`
- **BASELINE_SHA:** `cc6fd2d` (current main HEAD pre-brief-commit; resolve via `git rev-parse main` at worktree-creation time after this brief lands).
- **Branch naming intent:** `schwab-mapper-bundle-1` matches the cleanup-script `schwab(?:-\w+)?-bundle-` regex (verified at `cleanup-locked-scratch-dirs.ps1:156`); operator's `-DeregisterFirst` pass cleans cleanly post-merge.

### §1.2 Marker-file workflow

- After worktree creation: `New-Item -ItemType File c:\Users\rwsmy\swing-trading\.copowers-subagent-active`
- **BEFORE handing off for operator cassette session (T-1.0 ship):** keep marker present (subagent is technically still active).
- After cassette session + operator resume signal: marker stays present (resume).
- After all 14 tasks land + tests GREEN + before invoking adversarial-critic: `Remove-Item c:\Users\rwsmy\swing-trading\.copowers-subagent-active`

### §1.3 Commits

- Conventional prefixes:
  - `feat(schwab-bundle-1-T-1.0): <description>` for cassette runbook + recording script
  - `feat(schwab-bundle-1-T-1.1..2): <description>` for dataclass extensions
  - `feat(schwab-bundle-1-T-1.3): <description>` for mapper widening
  - `feat(schwab-bundle-1-T-1.4..5): <description>` for helper functions
  - `feat(schwab-bundle-1-T-1.6..7): <description>` for comparator switches
  - `feat(schwab-bundle-1-T-1.8..9): <description>` for classifier widening
  - `docs(schwab-bundle-1-T-1.10): <description>` for CLAUDE.md gotcha amendment
  - `docs(schwab-bundle-1-T-1.11): <description>` for CVGI date no-op-with-note
  - `feat(schwab-bundle-1-T-1.12): <description>` for show-correction CLI
  - `test(schwab-bundle-1-T-1.13): <description>` for E2E cassette test
  - `fix(schwab-bundle-1): Codex RN <severity> #N — <description>` for Codex-driven fixes
- **NO Claude co-author footer.** This is a CLAUDE.md binding convention. Per fresh forward-binding lesson #7 (Phase 12 Sub-sub-bundle C.B 2026-05-15) — do NOT add `Co-Authored-By: Claude Opus 4.7 (1M context) <noreply@anthropic.com>` (or any other Co-Authored-By footer attributing the AI assistant) to ANY commit message. Subagent context starts isolated; the Bash tool's default footer template is NOT authoritative for this project — CLAUDE.md is. C.B R1 fix-bundle 4 commits carried the footer accidentally + required orchestrator-side rebase-strip pre-merge; C.C + C.D + post-Phase-12 brainstorm + writing-plans chains' explicit citation produced ZERO footer drift across 23 + 33 + 6 + 2 commits respectively — pattern is DURABLE. **This dispatch MUST NOT regress.**
- **NO `--no-verify`**, **NO `--amend`** (per CLAUDE.md binding conventions: prefer `git add <specific-files>` over `git add -A`).
- **TDD:** failing test first, minimal implementation, pass, commit. Per-task `- [ ]` checkboxes in plan §A mark per-step boundaries.

### §1.4 Branch isolation + ownership

- Commits on branch only; no push to origin from worktree until Sub-bundle 1 integration commit (T-1.13 worktree push).
- **Implementer (you) owns:** task-family TDD commits → T-1.0 ship + operator-handoff message → operator cassette session resume signal → T-1.1..T-1.13 implementation → marker-file removal → pre-Codex review (NEW C.C lesson #6) → adversarial-critic → return report.
- **Operator owns:** cassette-recording session via T-1.0 script + witnessed verification gate (§3 surfaces below — 9 surfaces).
- **Orchestrator owns:** integration merge to main + post-merge housekeeping + Sub-bundle 2 dispatch commissioning.

### §1.5 Verify command

PowerShell from inside worktree:

```powershell
git log --oneline HEAD~25..HEAD
python -m pytest -m "not slow" -q
python -m pytest -m slow tests/integration/test_schwab_mapper_widening_e2e.py -v   # T-1.13 cassette-driven
ruff check swing/ --statistics
python -c "from swing.integrations.schwab.models import SchwabExecutionLeg, SchwabOrderResponse; print('models OK')"
python -c "from swing.trades.schwab_reconciliation import _compute_execution_price, _resolve_match_quantity, _is_execution_bearing_candidate; print('helpers OK')"
python -c "from swing.trades.reconciliation_classifier import classify_discrepancy; print('classifier OK')"
python scripts/record_schwab_cassettes.py --help
```

---

## §2 Adversarial review (Codex)

Invoked automatically by `copowers:executing-plans` after all 14 tasks land + tests GREEN + after the pre-Codex orchestrator-side review (C.C lesson #6 — implementer MUST do an explicit dispatched-reviewer-subagent pass BEFORE invoking adversarial-critic).

**Expected chain shape:** 3-5 substantive Codex rounds (matches Phase 12 Sub-sub-bundle C.C 3 rounds + C.D 4 rounds for mid-complexity scope). Plan §A absorbed 6 rounds of Codex review at writing-plans time + ZERO ACCEPT-WITH-RATIONALE banked + 4 brief-vs-shipped-code deviations addressed. Execution rounds should converge faster.

**Adversarial review watch items (Sub-bundle 1-specific; pass as targeted prompts to `copowers:adversarial-critic`):**

1. **Shape C predicate is ADDITIONAL not replacement** (§0.5 #3). Sub-bundle C.B Shape A + Shape B preserved unchanged. Re-running C.B's parametrized tests (T-B.4/T-B.5 6-shape Pass-2-tier-1-FORBIDDEN) MUST still pass post-Sub-bundle-1.
2. **V1 LIFT scope = Pass-1 only LOCK** (§0.5 #2). `_classify_unmatched_fill_shared` widening LIMITED to Path B `execution_unavailable=true` sentinel recognition. Discriminating test: plant `unmatched_open_fill` discrepancy WITHOUT `execution_unavailable=true` sentinel; classifier emits tier-2 `unsupported` per V1 LOCK. With sentinel; classifier emits tier-2 `unsupported` with clearer reason citing `execution_unavailable=true`.
3. **Backward-compat fall-through = Path B** (§0.5 #5). When `orderActivityCollection` missing/empty → comparator emits `unmatched_open_fill`/`unmatched_close_fill` with `execution_unavailable=true` sentinel. Discriminating test for both branches.
4. **Mapper coherence-check at T-1.3** (§0.5 #4). `sum(legs.quantity) == order.filledQuantity` → `executions` preserved; else `executions=None` collapse + comparator Path B fall-through. Discriminating test: plant Schwab fixture with legitimate partial fills (sum matches filledQuantity) → assert `executions` populated; plant fixture with malformed legs (sum != filledQuantity) → assert `executions=None`.
5. **Comparator candidate-pool filter widening at T-1.6 + T-1.7** (Codex R1 M#1+#2 + plan §A.0.1 D4). `_is_execution_bearing_candidate` helper distinguishes execution-bearing vs non-execution-bearing candidates. Discriminating tests for MARKET fills with `price=None` (V1 excluded; V2 includes if `executions` populated) + partial-then-canceled CANCELED-with-`filledQuantity>0` orders (V1 excluded; V2 includes if `executions` populated).
6. **VWAP precision for multi-leg** (§0.5 #6). Worked example: 2-leg fill with `leg[0].price=$10.00, quantity=50, leg[1].price=$10.20, quantity=50` → VWAP = $10.10. Discriminating test asserting journal `price=$10.10` → no discrepancy emit; journal `price=$10.00` → tier-1 with `correction_target.price=$10.10`.
7. **`_compute_execution_price` None-fall-through** (§0.5 #5). When `so.executions is None` OR empty → returns None → comparator emits Path B sentinel.
8. **FIRED-stop discipline = Path A mirror entry-fill** (§0.5 #8). T-1.13 cassette includes STOP FIRED order type; assert comparator uses `executionLegs[].price` for `close_price_mismatch` (NOT `stopPrice` trigger).
9. **`stop_mismatch` UNCHANGED** (§0.5 #14 + spec §1.1 lock #2). T-1.6 + T-1.7 implementations MUST NOT touch `_find_working_stop_for_ticker` code path. Regression test: assert WORKING-stop fixtures emit `stop_mismatch` per V1 semantics (trigger vs trigger).
10. **`construct_authenticated_client` 4-arg signature at T-1.0** (§0.5 #12). T-1.0 `scripts/record_schwab_cassettes.py` MUST follow: `apply_overrides(cfg)` → `resolve_credentials_env_or_prompt(cfg, environment, allow_prompt=False)` → `construct_authenticated_client(...)`. Discriminating test asserting cascade-resolved values threaded through.
11. **vcrpy URI/path sanitization at T-1.0** (§0.5 #13). Cassette filter installs BOTH `before_record_request` (URI/path) AND `before_record_response` (body). Discriminating test: record a fixture with embedded `accountHash` in URL path → grep cassette file → assert sentinel-leak ZERO matches.
12. **`show-correction` CLI generic ID-free help-text at T-1.12** (§0.5 #11 + plan §A.0.1 D1). Subcommand exists + `--help` flag renders generic addendum citing spec path + V1 limit-vs-fill historical context. Subcommand body fetches discrepancy by id + renders detail (no per-row engine_version metadata required; that's V2-banked).
13. **CLAUDE.md gotcha amendment at T-1.10** (§0.5 inheritance). Amendment preserves V1 historical context (CVGI + LION 2026-05-17 falsification evidence + 3 orchestrator-inline gate-fix instances + Pass-2-FORBIDDEN family); adds NEW V1-RESOLVED-for-Pass-1 top-section; references V2 mapper widening dispatch + spec + commit chain.
14. **CVGI date typo no-op-with-note at T-1.11** (§0.5 inheritance). T-1.11 commit message documents the no-op + grep result confirming ZERO matches in CLAUDE.md.
15. **NO behavioral changes to NON-touched existing surfaces** (§0.5 #14). Codex SHOULD verify the touch surface is bounded; especially: `stop_mismatch` path UNCHANGED; Sub-bundle C.A schema UNCHANGED; Sub-bundle C.B Shape A + Shape B predicates UNCHANGED; Sub-bundle C.D banner predicate UNCHANGED.
16. **Schema additions during executing-plans cycle (C.A return report lesson #7).** If Codex surfaces a need for schema element NOT in plan §A + spec §3, implementer MUST STOP + escalate to orchestrator BEFORE adding inline. Cost of bank-after-write: 2-3 cascade-cleanup rounds.
17. **Synthetic-fixture-vs-production-emitter shape drift pre-emption** (C.D gate-fix #2 family). T-1.13 cassette-recorded fixtures plant Schwab response shapes matching production emitter byte-for-byte. Pre-empt via discriminating tests using production-shape values (from cassette YAML).
18. **Windows cp1252 stdout encoder pre-emption** (C.D gate-fix #1+#3 family). NEW CLI output at T-1.12 `show-correction` subcommand MUST NOT contain non-ASCII glyphs (`§`/`→`/etc.) OR rely on `swing/cli.py` entry's UTF-8 stdout reconfigure as defense-in-depth. Discriminating test invoking subcommand under cp1252-emulated stdout.

---

## §3 Operator-witnessed verification gate (Sub-bundle 1 integration — 9 surfaces)

Per plan §H.1:

| Surface | Type | Acceptance |
|---|---|---|
| **S1** | Inline `pytest -m "not slow" -q -n auto` | GREEN at ~4423-4493 fast tests (worktree-side; +60-130 net from 4363 baseline). 3 pre-existing phase8 walkthrough failures unchanged; 5 skipped. T-1.13 slow-marked cassette-driven E2E PASSES under `-m slow`. |
| **S2** | Cassette-driven mapper test PASS | T-1.13 invokes the E2E test against the 4 cassette-recorded order types (LIMIT BUY + LIMIT SELL + STOP FIRED + MARKET BUY); each asserts `SchwabExecutionLeg` mapping output byte-for-byte matches the cassette + downstream comparator + classifier paths emit expected results. |
| **S3** | `swing journal reconcile-tos --dry-run --schwab` (or equivalent) against operator's production DB | **PRODUCTION DRY-RUN** (operator pre-authorizes per C.D-arc lesson #2 if classifier soft-blocks). Expected: NO false-positive `entry_price_mismatch`/`close_price_mismatch` for CVGI + LION (V2 mapper correctly compares execution-grain; historical fills 9+15 already have correct journal values per C.D gate cleanup). No Pass-1-tier-1 limit-vs-fill regression. |
| **S4** | OPTIONAL `swing journal reconcile-tos --apply --schwab` against production | **OPTIONAL PRODUCTION APPLY** (operator preference at gate-time). If applied, verify no false-positive discrepancies emitted + reconciliation_run completes cleanly + audit log clean. Operator may elect to SKIP S4 if S3 dry-run output is clean. |
| **S5** | Phase 10 dashboard banner count=0 | `swing web --port 8081` worktree-side OR production state inspection. Banner count UNCHANGED at 0 (production state remains clean). |
| **S6** | CLAUDE.md gotcha amendment text operator review | Operator reads T-1.10 amendment text; confirms V1-RESOLVED-for-Pass-1 wording + V1 historical context preserved + V2 mapper widening dispatch + spec + commit chain references intact. |
| **S7** | `show-correction` CLI generic help-text operator review | Operator invokes `swing journal discrepancy show-correction --help` worktree-side; reads generic addendum + spec citation; confirms operator-actionable. Optionally invokes `show-correction <id>` against a historical correction-chain row to verify subcommand body renders detail. |
| **S8** | `ruff check swing/ --statistics` | Reports 18 E501 unchanged. |
| **S9** | OPTIONAL `schwab_api_calls` audit-log spot-check | Operator inspects most-recent `schwab_api_calls` rows post-S3/S4 to verify audit attribution + cassette consumption pattern (if S3 dry-run consumed cassettes; if S3 hit live Schwab API). |

**Gate session budget:** 9 surfaces. Long-haul operator-paired session (per `feedback_orchestrator_vs_implementer_execution.md` + handoff brief §0 LOCK). Operator-paired-gate driving — ONE COMMAND AT A TIME (per operator stated preference 2026-05-15).

**Production-write classifier soft-block awareness at S3+S4:** dry-run + apply against production DB are production-writes from Claude Code's classifier perspective (audit-row writes count). Operator pre-authorizes via gate-path AskUserQuestion OR plain-chat "yes" if classifier soft-blocks. **EXPECT BLOCKS PER-INVOCATION** per NEW C.D-arc lesson #2 (production-write classifier soft-block fires PER-INVOCATION even after AskUserQuestion authorization).

**Production state post-gate:** ZERO unresolved-material discrepancies preserved; banner count=0 preserved. **Production state CLEAN.** No CVGI/LION-family false-positive emissions going forward (architectural fix landed end-to-end).

---

## §4 OUT OF SCOPE (do not do)

- **Schema additions or migrations** — spec §1.3 + plan §C.5 escalation rule. If implementer encounters a need for schema element NOT in plan §A + spec §3, STOP + escalate to orchestrator BEFORE adding inline.
- **Pass-2 LIFT** — spec §1.5 V1 LIFT scope = Pass-1 only. `_classify_unmatched_fill_shared` widening LIMITED to Path B sentinel recognition.
- **OQ-F multi-leg tier-1 auto-redirect** — spec §6.6 V2 follow-up dispatch.
- **Per-row `engine_version` metadata column** — spec §8.3 V2 candidate (requires schema v20).
- **`/config?schwab_setup=ok` hard removal** — passive no-op retained one release window per spec §7.3 + R1 m#2 LOCK.
- **Per-leg audit surfacing for tier-2 outside-tolerance VWAP** — spec §9.2 V2 candidate.
- **schwabdev SDK upgrade or token encryption-at-rest** — Sub-bundle B V2 candidates.
- **Fill auto-population at trade-entry time** — Sub-bundle C §1.6 separate sub-bundle.
- **Web Tier-2 discrepancy-resolution surface** — Sub-bundle C plan §I.3 V2 candidate.
- **Mocked-only fallback path** — OQ-E operator-decided cassette-required default; mocked-only NOT-elected.
- **Sub-bundle 2 work** — `/schwab/status` web counterpart is Sub-bundle 2 scope (T-2.0..T-2.6); separate executing-plans dispatch after Sub-bundle 1 ships.
- **Behavioral changes to non-touched surfaces** — plan §C.4. Especially: `stop_mismatch` UNCHANGED; Sub-bundle C.A schema UNCHANGED; Sub-bundle C.B Shape A + Shape B predicates UNCHANGED; Sub-bundle C.D banner predicate UNCHANGED.
- **Re-litigating spec §1 binding constraints** — accepted as given. Operator-locked.
- **Re-litigating plan §A acceptance criteria** — all per-task LOCKs via writing-plans Codex R6 convergence; do NOT re-open.

---

## §5 Return report shape

After all 14 tasks land + Codex chain converges + before final return-report commit, draft a return report at `docs/post-phase12-schwab-mapper-bundle-1-return-report.md` (mirroring `docs/phase12-bundle-C-D-return-report.md` shape):

1. Final HEAD on branch + commit count breakdown (14 task-impl + N Codex-fix + 1 return-report).
2. Codex round chain (R1-RN summary table + convergent shape; finding-count taper).
3. Test count delta + ruff baseline delta + schema version delta (v19 unchanged — Sub-bundle 1 touches no schema).
4. Operator-witnessed verification surfaces (PENDING orchestrator-driven gate; 9 surfaces).
5. Per-task deviations from plan (if any) with rationale.
6. Codex Major findings ACCEPTED with rationale (if any).
7. Watch items for orchestrator (V2 candidates surfaced; Sub-bundle 2 dispatch readiness).
8. Worktree teardown status.
9. Per-task disposition LOCKS (any task-level decisions worth banking).
10. Forward-binding lessons for future bundles (especially Sub-bundle 2 + OQ-F V2 dispatch).
11. CLAUDE.md status-line refresh draft text for orchestrator paste-in at integration-merge time.
12. Composition-surface verification: `^def ` grep on `swing/trades/schwab_reconciliation.py` + `swing/trades/reconciliation_classifier.py` + `scripts/record_schwab_cassettes.py` confirming public surface matches plan §A acceptance criteria.
13. Cassette session verification evidence (4 order types recorded; sanitization sentinel-leak audit GREEN; cassette YAML files committed to worktree branch).
14. Pass-2-tier-1-FORBIDDEN regression evidence (C.B's parametrized test still PASSES post-Sub-bundle-1; V1 Pass-2 LOCK preserved).
15. `stop_mismatch` regression evidence (`_find_working_stop_for_ticker` path UNCHANGED; trigger-vs-trigger comparison preserved).
16. CVGI + LION historical-correction-chain non-regression evidence (production-DB read-only inspection at S3 dry-run; correction_ids 1-6 untouched).

---

## §6 Dispatch metadata

- **Subagent type:** `general-purpose` (full tool surface needed).
- **Foreground vs background:** foreground (default).
- **Worktree:** YES — per §1.1.
- **Model:** defer to harness default.
- **Expected duration:** ~10-16 hr implementation + ~3-6 hr Codex + 1 operator-paired cassette session (~30-60 min) + 9-surface operator-witnessed gate. Total ~14-23 hr.

---

## §7 If you get stuck

- If plan §A binding contracts conflict with what spec §3-§8 says, **plan wins** (writing-plans Codex R6 chain ratified plan §A; spec is upstream input).
- If a Codex round produces a finding you can't disposition without orchestrator input, ACCEPT-with-rationale + flag explicitly in return report.
- If you need a schema element NOT in plan §A + spec §3, **STOP + escalate** (spec §1.3 + plan §C.5 escalation rule; bank-after-write costs 2-3 cascade-cleanup rounds).
- If operator's cassette session produces unexpected Schwab API response shapes (e.g., `orderActivityCollection` populated for STOP_LIMIT but `executionLegs` empty), STOP + surface to orchestrator as deviation from spec §6.5 OQ-E LOCK.
- If `_is_execution_bearing_candidate` filter widening surfaces edge cases beyond Codex R1 M#1+#2 catalog (e.g., FILLED-but-zero-quantity orders; phantom orders), STOP + surface as deviation.
- DO NOT propose new classifier sub-classifiers within Sub-bundle 1 scope (§4 lock).
- DO NOT propose web Tier-2 surface within Sub-bundle 1 scope (§4 lock; V2 candidate).
- DO NOT propose schema additions within Sub-bundle 1 scope (§4 lock; lesson #7 family).
- DO NOT add `Co-Authored-By` footer to any commit message (per §1.3 + fresh forward-binding lesson #7; C.B R1 fix-bundle precedent of accidental drift required orchestrator-side rebase-strip pre-merge — C.C + C.D + post-Phase-12 brainstorm + writing-plans ship's explicit citation produced ZERO drift across 4 dispatches — do NOT regress).
- DO NOT propose Pass-2 LIFT beyond Path B sentinel recognition within Sub-bundle 1 scope (§4 lock; spec §1.5 + §6.6 OQ-F V2).
- DO NOT propose magnitude-based threshold gating (§4 lock; spec §1.1 lock #6 inheritance).
- DO NOT propose retroactive `reconciliation_corrections` rewriting (§4 lock; spec §1.1 lock #4 + OQ-G operator-decided leave-as-is).
- If you encounter a Phase 7/8/9/10/11/12-A/12-B/12-C-A/12-C-B/12-C-C/12-C-D lesson that conflicts with a Sub-bundle 1 implementation proposal, the prior-phase lesson wins (validated by ship-experience). Surface the conflict as a constraint.
- If Codex pushes back on the V1 LIFT scope = Pass-1 only LOCK at T-1.8 + T-1.9 (e.g., "but Pass-2 LIFT seems straightforward..."), HOLD THE LINE — the LOCK is spec §1.5 + §6.6 + Codex R2 M#1 + R3 M#1 + R4 M#1 + R5 m#1 unified at writing-plans time. V1 mapper exposes only order-level price for Pass-2 re-fetches; OQ-F V2 follow-up dispatch unblocks Pass-2 LIFT.
- If Codex pushes back on the comparator candidate-pool filter widening LOCK at T-1.6 + T-1.7 (e.g., "but V1 filter was conservative for safety..."), HOLD THE LINE — the LOCK is plan §A.0.1 D4 + Codex R1 M#1+#2 at writing-plans time. V1 filter excluded MARKET fills + partial-then-canceled orders that DO carry execution-grain data when `orderActivityCollection` is populated.
- If Codex pushes back on the cassette runbook URI/path sanitization LOCK at T-1.0 (e.g., "filter_query_parameters should be sufficient..."), HOLD THE LINE — the LOCK is plan §F.3 + Codex R2 C#1 at writing-plans time. Schwab Trader API embeds accountHash in URL path segments; filter_query_parameters does NOT scrub paths; cassettes would leak operator's accountHash into git history.
- If Codex pushes back on the standalone recording-script LOCK at T-1.0 (e.g., "in-test `@pytest.mark.vcr(record_mode='new_episodes')` is simpler..."), HOLD THE LINE — the LOCK is plan §A.1.0 + Codex R3 M#1 at writing-plans time. Cassettes must exist BEFORE the consumer test code (T-1.13) is written; standalone script enables this ordering.
- **Pre-Codex orchestrator-side review (NEW C.C lesson #6)**: before invoking `copowers:adversarial-critic`, dispatch a focused reviewer subagent with the plan §A acceptance criteria + brief §0.5 BINDING contracts as anchors; ask for a deviation list ≤600 words. Cheap; absorbs LOCK divergences pre-Codex; saved 1-2 Codex rounds on C.C + 2 absorbed Majors on C.D + 1 absorbed Major + 1 absorbed Minor on C.D pre-Codex review. Apply explicitly here.

---

## §8 Operator-paired gate notes

Sub-bundle 1's 9-surface gate is medium-sized (LARGER than C.D's mid-cycle gates of 4-7 surfaces; smaller than C.D's headline 10-surface gate). Plan for an operator-paired session:

- **Cassette session is mid-dispatch (not at gate)** — operator runs T-1.0 recording script during implementer's mid-dispatch pause; cassettes are committed to worktree branch BEFORE T-1.1..T-1.13 lands.
- **Production refresh-token clock** — expires ~2026-05-22; verify TTL > 1hr at cassette session pre-check; operator re-auths via `/schwab/setup` web form OR `swing schwab setup` CLI if needed.
- **Production-write classifier soft-block** — S3 + S4 are production-writes from classifier perspective; operator pre-authorizes via gate-path AskUserQuestion OR plain-chat "yes" PER INVOCATION (C.D-arc lesson #2).
- **One command at a time** — per operator preference (handoff brief §0 LOCK); orchestrator sends ONE command per turn, waits for output, verifies, sends next.
- **Worktree-side web server** — S5 uses `swing web --port 8081` (NOT 8080); stop the server when S5 done. Optional — operator may inspect production state directly without spinning up worktree web server.
- **S4 is OPTIONAL** — operator's preference at gate-time. If S3 dry-run output is clean, S4 may be skipped without scope contortion.
- **Operator-architectural-pushback STOP-and-recover** — if S3+S4 surface architectural divergences (e.g., unexpected reconciliation_discrepancies emit; unexpected cassette consumption pattern), STOP, investigate, recover (C.D-arc lesson #1). NOT push-through.

---

*End of brief. Sub-bundle 1 executing-plans dispatch with mid-dispatch operator pause for cassette session. Branch `schwab-mapper-bundle-1` matches cleanup-script regex. Schema unchanged (v19); architectural fix lands end-to-end via 14 tasks T-1.0..T-1.13 with housekeeping FOLDED; CLAUDE.md `Pass-2-tier-1-FORBIDDEN` gotcha amendment marks V1-RESOLVED for Pass-1 family. Expected duration ~14-23 hr including 1 operator-paired cassette session + 9-surface operator-witnessed gate.*
