# Phase 12 Sub-bundle C Sub-sub-bundle C.B (Classifier + validator-shim) — executing-plans return report

**Branch:** `phase12-bundle-C-B-classifier-and-validator-shim`
**Final HEAD:** `008f392`
**Baseline:** `fdb4276` (post-C.A integration merge + dispatch-brief commit)
**Plan:** `docs/superpowers/plans/2026-05-15-phase12-bundle-C-auto-correct-reconciliation-plan.md` §C (T-B.1..T-B.14)
**Spec:** `docs/superpowers/specs/2026-05-15-phase12-bundle-C-auto-correct-reconciliation-design.md` §4 + §5.5 + §6.2.1 + §8.4 + §10
**Dispatch brief:** `docs/phase12-bundle-C-B-classifier-and-validator-shim-executing-plans-dispatch-brief.md`

---

## §1 Final HEAD + commit breakdown

**25 commits on branch** (14 task-impl + 1 UP035 ruff style + 4 Codex R1 fixes + 2 Codex R2 fixes + 1 R2-style N806 followup + 2 Codex R3 fixes + 1 Codex R4 fix; return-report commit forthcoming):

| SHA | Type | Description |
|---|---|---|
| `94ebb9f` | T-B.1 | `classify_discrepancy` public entry + `ClassificationResult` dataclass + dispatch table skeleton + determinism (100×) + graceful-degradation tests |
| `0122cdd` | T-B.2 | `reconciliation_validators` shim — 4 dry-run callable validators |
| `732b308` | T-B.3 | `entry_price_mismatch` sub-classifier (CVGI 41 walkthrough) |
| `94d9b79` | T-B.4 | `unmatched_open_fill` sub-classifier (DHC+VSAT walkthroughs; **tier-2-always per Pass-2-tier-1-FORBIDDEN LOCK**) |
| `c2bfe85` | T-B.5 | `unmatched_close_fill` sub-classifier (mirrors T-B.4) |
| `5e75045` | T-B.6 | `stop_mismatch` sub-classifier (advisory-not-validator family preserved) |
| `7e9ba80` | T-B.7 + shared helpers | `position_qty_mismatch` sub-classifier + bundled `_candidate_choices_*` helpers used across T-B.7..T-B.12 (per plan-deviation #1 below) |
| `a9b9371` | T-B.8 | `close_price_mismatch` sub-classifier (tier-2-always V1) |
| `18b1dcc` | T-B.9 | `cash_movement_mismatch` sub-classifier (tier-1 single-match + tier-2 otherwise) |
| `7875a2e` | T-B.10 | `sector_tamper` sub-classifier (tier-2-always V1) |
| `006c2a7` | T-B.11 | `snapshot_mismatch` sub-classifier (tier-2-always V1) |
| `4c56919` | T-B.12 | `equity_delta` sub-classifier (tier-2-always V1) |
| `5a52b64` | T-B.13 | `default_validator_chain(conn)` dispatcher (composes 4 shim validators via `affected_table` partial-application) |
| `6937cb3` | T-B.14 | un-skip cross-bundle pin tests from T-A.7 |
| `7e12cae` | style | mechanical UP035 fix — `Callable`/`Mapping` from `collections.abc` |
| `6e4bd30` | Codex R1 C#1 | `entry_price_mismatch` (ticker, date, quantity) consistency check + NaN/inf/non-numeric guard + 9 discriminating tests |
| `fcff4d3` | Codex R1 M#1 | `pick_schwab_record_<N>` choices `requires_custom_value=True` per spec §4.3.2 LOCK |
| `180838e` | Codex R1 M#2 | `math.isfinite()` guard on all 5 numeric validator fields (mirrors `swing/data/models.py` REAL-field discipline) |
| `78d98b2` | Codex R1 M#3 | strengthen cross-bundle pin tests to discriminatingly pin `classify_discrepancy` + `default_validator_chain` behavior |
| `ee195f4` | Codex R2 M#1 | `entry_price_mismatch` requires EITHER persisted-JSON-only `{'price'}` OR full match-tuple (ticker+date+quantity); partial tuple → tier-2 `unsupported` |
| `d5f2520` | Codex R2 m#1 | close SQLite connection in cross-bundle pin tmp_path fixture (Windows file-handle hygiene) |
| `458c8f6` | R2 style | rename in-function constants to lowercase per ruff N806 (R2 M#1 followup) |
| `d14a107` | Codex R3 M#1 | `entry_price_mismatch` Shape B rejects contradictory SOURCE date evidence (date vs fill_datetime divergence) |
| `e7ef6ed` | Codex R3 m#1 | remove dead `source_tuple_keys_present` variable from `entry_price_mismatch` (R2 predicate rewrite leftover) |
| `008f392` | Codex R4 M#1 | `entry_price_mismatch` Shape B rejects contradictory JOURNAL date evidence (mirrors R3 source-side fix; determinism principle) |

---

## §2 Codex round chain (5 rounds → NO_NEW_CRITICAL_MAJOR)

| Round | Findings | Verdict | Convergence |
|---|---|---|---|
| R1 | 1C / 3M / 0m | ISSUES_FOUND | All 4 resolved with code-content fixes (ZERO accept-with-rationale). |
| R2 | 0C / 1M / 1m | ISSUES_FOUND | Both resolved + 1 ruff N806 style followup for R2 M#1's new helper constants. |
| R3 | 0C / 1M / 1m | ISSUES_FOUND | Both resolved (Major source-date contradiction check; Minor dead-variable cleanup). |
| R4 | 0C / 1M / 0m | ISSUES_FOUND | Resolved with mirror-image journal-date contradiction check. |
| R5 | 0C / 0M / 0m | **NO_NEW_CRITICAL_MAJOR** | Convergent shape; chain closed. |

**5 rounds total** — convergent tapering (1C/3M/0m → 1M/1m → 1M/1m → 1M/0m → 0/0/0). **ZERO ACCEPT-WITH-RATIONALE banked entire chain** — every finding (1 Critical + 6 Major + 2 Minor) resolved with code-content fixes.

R1 Critical #1 + R2 M#1 + R3 M#1 + R4 M#1 form a single **determinism-principle-tightening sequence on `entry_price_mismatch`** — each round tightened the Shape B predicate further. R5 converged.

---

## §3 Test count + ruff baseline + schema version deltas

| Metric | Baseline (`fdb4276`) | C.B HEAD (`008f392`) | Delta |
|---|---|---|---|
| Fast suite passing | 3971 | **4110** | **+139** |
| Pre-existing failures | 3 (3 phase8 walkthrough — banked per CLAUDE.md C.A entry) | 3 (unchanged) | 0 |
| Skipped tests | 7 | 5 | −2 (C.A's 2 cross-bundle pin tests un-skipped at T-B.14) |
| Ruff E501 baseline | 18 | **18** | **unchanged** |
| Schema version | 19 | **19** | unchanged (consumer-side only) |

**Net +139 fast tests** — above the +85-130 dispatch-brief projection upper bound; above the +55-95 plan §H projection. Matches Phase 9 Sub-bundle A (+205) / B (+147) / C (+130) / D (+16) / E (+10) overshoot precedent + Phase 10 Sub-bundles overshoot family.

Delta breakdown:
- Initial 14-task implementation: +107 (3971 → 4078; reported by implementer).
- Codex R1 fix bundle: +27 (4078 → 4105; reported by implementer — adjusted from raw count of test files vs `git diff` because some R1 fixes were additions to existing test files).
- Codex R2 fix bundle: +8 (4105 → 4113? reported as 4106 in implementer logs; small discrepancy due to a test rename during R2 M#1 fix where one ticker-quantity-no-date positive test was edited rather than added; final count from authoritative pytest run = **4108**, see below).
- Codex R3 fix bundle: +2 (4108 → 4110).
- Codex R4 fix bundle: +2 inline-test bonus on top of the cumulative passage count; final authoritative `pytest -m "not slow" -q` run reports **4110 passed**.

Authoritative final pytest output:
```
3 failed, 4110 passed, 5 skipped, 637 warnings in 74.23s (0:01:14)
```

---

## §4 Operator-witnessed verification gate (PENDING — orchestrator-driven)

Per dispatch brief §3 + plan §G.2 (3 surfaces; gate budget ≤ 3):

| Surface | Type | Expected acceptance | Implementer-side status |
|---|---|---|---|
| **S1** | Inline `pytest -m "not slow" -q` | GREEN at ~4110 fast tests; 3 pre-existing failures unchanged | **PASS** worktree-side (4110 passed; 3 phase8 failures unchanged; 5 skipped) |
| **S2** | Classifier against CVGI 41 + DHC 39 + VSAT 40 fixtures emits expected `ClassificationResult` shapes per spec §10 | Operator-driven walkthrough via dispatched harness OR `python -c`. CVGI 41 (Pass 1 single-fill): `tier=1, ambiguity_kind=None, correction_target={'price': 5.30}`. DHC 39 (Pass 1 only — `actual={"matched": null}`): `tier=2, ambiguity_kind='unsupported', _pass_2_required=True` signal in `correction_reason`. VSAT 40 (Pass 1 only): same shape as DHC 39. | **PENDING orchestrator-driven**. Coverage worktree-side via the strengthened cross-bundle pin tests (CVGI 41 walkthrough now pinned in `tests/integration/test_phase12_bundle_c_cross_bundle_pin.py`) + the 27 sub-classifier discriminating tests under `tests/trades/test_classifier_*.py`. |
| **S3** | `ruff check swing/ --statistics` | Reports 18 E501 unchanged | **PASS** (18 E501; both new modules clean) |

**Gate session ≤ 3 surfaces budget honored.** S1+S3 inline. S2 operator-driven via tiny harness. No browser surfaces, no production writes.

**Production state post-gate:** NO behavioral changes to existing surfaces. C.B is consumer-side passive — the new modules are imported only by C.B's own tests (no production callsites until C.C ships). Existing 3 unresolved-material discrepancies (39 DHC + 40 VSAT + 41 CVGI) UNCHANGED — left for C.D backfill.

---

## §5 Per-task deviations from plan (with rationale)

### Deviation 1 — T-B.7 commit bundles shared `_candidate_choices_*` helpers used by T-B.7..T-B.12

**Plan §C.7 acceptance:** T-B.7 was scoped to `position_qty_mismatch` sub-classifier only.

**Shipped behavior:** T-B.7 commit `7e9ba80` adds the `position_qty_mismatch` sub-classifier AND the 4 shared `_candidate_choices_*` helper functions used by T-B.7 + T-B.8 + T-B.9 + T-B.10 + T-B.11 + T-B.12. T-B.8..T-B.12 commits add ONLY their respective test files.

**Rationale:** the candidate-choices menu shapes are spec §6.2.1 LOCKED — they are brittle to per-task drift if each sub-classifier inlined its own helper. Bundling 4 helpers into a single atomic landing matches CLAUDE.md gotcha "Schema-CHECK + Python-constant + dataclass-validator MUST land in the same task for atomic consistency" — same principle applied to candidate-choice menu helpers.

Per-task test attribution preserved in git history; each test file commits separately under T-B.N.

### Deviation 2 — Float formatting in `correction_reason` strings uses `:.2f`

**Plan §C.3 + §C.6 acceptance** says tier-1 reasons include journal-price + source-price + delta in human-readable form.

**Shipped behavior:** dollar amounts render with `f"${value:.2f}"` formatting to guarantee 2-decimal representation (`$5.30` not `$5.3`).

**Rationale:** discriminating test substring assertions on `"5.30"` would fail under Python's default `repr(5.30)` which truncates trailing zeros. The `:.2f` choice matches existing project formatting precedent for currency rendering. Banked as V2.1 §VII.F amendment candidate so plan-text could pin the exact format string.

### Deviation 3 — `Co-Authored-By: Claude Opus 4.7` footer in R1 fix-bundle commits

**CLAUDE.md convention:** "NO Claude co-author footer."

**Shipped behavior:** R1 fix-bundle commits (`6e4bd30` + `fcff4d3` + `180838e` + `78d98b2`) include the `Co-Authored-By: Claude Opus 4.7 (1M context) <noreply@anthropic.com>` footer. The implementer subagent interpreted the system Bash tool's default footer template as authoritative; CLAUDE.md overrides but the subagent missed the override. Discovered at R1 verification step and corrected at R2 dispatch — R2/R3/R4 fix-bundle commits omit the footer.

**Rationale:** banked for orchestrator post-merge cleanup. The 4 R1 commits could be rebased to strip the footer pre-integration-merge, OR the convention drift could be accepted into the project history. Operator-decidable at integration-merge time. The original 14 task-impl commits (`94ebb9f`..`6937cb3`) + the UP035 style commit (`7e12cae`) DO NOT carry the footer — only the R1 fix bundle does.

### Deviation 4 — R2 style commit `458c8f6` exists because amending was disallowed

**Plan + brief discipline:** "No `--amend`."

**Shipped behavior:** R2 M#1's new in-function constants `_TUPLE_KEYS` + `_RECOGNIZED_KEYS` triggered ruff N806 (uppercase-in-function); renamed to lowercase `tuple_keys` / `recognized_keys` in a separate style commit since amending was disallowed.

**Rationale:** preserves no-amend discipline + ruff baseline 18 cleanly. Minor pollution in commit graph; integration merge via `--no-ff` preserves the chain transparently.

---

## §6 Codex Major findings ACCEPTED with rationale (0 of 7)

**ZERO ACCEPT-WITH-RATIONALE banked.** Every Major + Critical finding across R1-R4 resolved with code-content fixes.

This matches Phase 12 Sub-bundle A clean record (1 ACCEPT-WITH-RATIONALE; but lifecycle-invariant pattern) and Sub-bundle B clean record (1 ACCEPT-WITH-RATIONALE family across R2+R3). C.A had 1; C.B has zero.

---

## §7 Watch items for orchestrator triage

1. **R1 fix-bundle commits carry `Co-Authored-By: Claude Opus 4.7` footer** — see §5 deviation #3 above. Orchestrator decides at integration-merge time: rebase-strip OR accept-drift.

2. **3 pre-existing `test_phase8_pipeline_walkthrough` failures** persist on `main` HEAD (`fdb4276`) — NOT a C.B regression. Banked for separate triage per the standing CLAUDE.md status-line note.

3. **R3 source-date contradiction check + R4 journal-date contradiction check** form a paired pattern. If the operator wants to add similar contradiction checks for ticker/quantity (e.g., source carries both `ticker` and `symbol` keys disagreeing), that's a V2 hardening candidate banked in §8.

4. **The `_pass_2_required=True` signal in `correction_reason`** is a free-form-string convention not yet consumed by C.D backfill. Plan §F-4 pins this as the C.B→C.D interface; ensure C.D dispatch brief enumerates the exact convention string to parse.

5. **`default_validator_chain` dispatch contract** — C.B test at `tests/trades/test_default_validator_chain.py` exercises `functools.partial`-style composition. C.C `apply_tier1_correction` will need to construct chains with caller-context (`affected_table` + `affected_row_id`) at INSERT time. Ensure C.C dispatch brief enumerates this composition pattern.

---

## §8 V2.1 §VII.F amendment candidates banked (6 items)

| # | Origin | Amendment |
|---|---|---|
| 1 | R2 M#1 resolution | Spec §4.3.1 LOGIC for `entry_price_mismatch` describes the source_payload shape loosely ("the Schwab transaction"). The Shipped C.B implementation pins TWO acceptable shapes for tier-1: Shape A (persisted-JSON-only `{'price'}`) OR Shape B (full match-tuple ticker+date+quantity). Spec should be tightened to enumerate these two shapes explicitly. |
| 2 | R3 M#1 + R4 M#1 resolutions | Spec §4.3.1 doesn't address contradictory date evidence — neither source-side (when source_payload has both `date` and `fill_datetime` disagreeing) nor journal-side (when journal_row has both keys disagreeing). C.B classifier rejects both as tier-2 `unsupported` per determinism principle §4.4; banked for explicit spec text covering both cases. |
| 3 | T-B.3 plan-deviation #2 | Plan §C.3 acceptance says "tier-1 reasons include journal-price + source-price + delta". Implementation uses `:.2f` for 2-decimal currency rendering. Plan text could pin the exact format string. |
| 4 | T-B.9 plan deviation | Plan §C.9 acceptance #1 cash_movement_mismatch tier-1 case implies a multi-field `correction_target`. Implementation builds the multi-field target by diffing source vs journal over `('date', 'kind', 'amount', 'ref')`. Plan text should enumerate the canonical 4-field comparison vector. |
| 5 | T-B.13 implementation | Plan §C.13 acceptance #4 describes the `functools.partial` composition contract; T-B.13 test demonstrates it. Spec §5.5 should also document the partial-application requirement explicitly so C.C implementer doesn't miss it. |
| 6 | R1 M#1 resolution | Spec §6.2.1 / Codex R7 M#2 LOCK is correctly enforced (`pick_schwab_record_<N>` choices have `requires_custom_value=True`). The spec already locks this; banking only for cross-reference completeness. |

---

## §9 Worktree teardown status

**PENDING orchestrator-driven** (per CLAUDE.md memory `feedback_orchestrator_performs_merge` + dispatch brief §1.4):

- Branch `phase12-bundle-C-B-classifier-and-validator-shim` exists on worktree.
- Marker file `c:\Users\rwsmy\swing-trading\.copowers-subagent-active` will be removed by orchestrator before integration merge.
- Worktree husk at `.worktrees/phase12-bundle-C-B-classifier-and-validator-shim` will be cleaned by `cleanup-locked-scratch-dirs.ps1 -DeregisterFirst` (regex matches `phase\d+[-_]` per Phase 12 Sub-bundle A T-A.4 fix).

---

## §10 Per-task disposition LOCKS (worth banking)

1. **`classify_discrepancy` signature LOCKED at T-B.1** — kwargs-only beyond `discrepancy`; `validator_chain: ValidatorChainCallable | None = None` optional. Matches spec §4.2 verbatim.
2. **`ClassificationResult` frozen dataclass shape LOCKED at T-B.1** — `tier: int (∈ {1, 2})`, `ambiguity_kind: str | None`, `correction_target: dict | None`, `correction_reason: str (non-empty)`, `candidate_choices: list[dict] | None`. Tier-3 NEVER emitted (operator-initiated post-tier-1 in C.C). `@dataclass(frozen=True)` enables determinism-test deep equality.
3. **Pass-2-tier-1-FORBIDDEN LOCKED at T-B.4 + T-B.5** — `unmatched_open_fill` + `unmatched_close_fill` NEVER emit tier=1 for any Pass-2 input shape. Spec §8.4 LOCK preserved verbatim. Parametrized regression test plants 6 distinct Pass-2 shapes (None, `{"matched": null}`, [], [1-order], [N-orders sum-matches], [N-orders sum-mismatches]) + asserts `result.tier == 2` for all.
4. **`entry_price_mismatch` Shape A vs Shape B LOCKED at R2 M#1** — Shape A: persisted-JSON-only `set(source_payload.keys()) == {'price'}`. Shape B: full match-tuple (ticker + date-form + quantity) ALL present + matching journal_row. Any partial-tuple shape → tier-2 `unsupported`. Determinism principle §4.4 enforcement.
5. **Contradictory date evidence on either side → tier-2** LOCKED at R3 M#1 + R4 M#1 — source-side OR journal-side internal date-form inconsistency surfaces tier-2 `unsupported` with reason naming "contradictory" + the conflicting `YYYY-MM-DD` prefixes. Determinism principle §4.4 mirror-image.
6. **NaN/inf/-inf guard on all numeric inputs** LOCKED at R1 M#2 + R1 C#1 — all 5 numeric validator fields (`quantity`, `price`, `current_stop`, `amount`, `equity_dollars`) AND `source_payload['price']` in entry_price_mismatch reject NaN/inf via `math.isfinite()` BEFORE inequality checks. Mirrors `swing/data/models.py:888-896` REAL-field discipline.
7. **`pick_schwab_record_<N>` choices `requires_custom_value=True`** LOCKED at R1 M#1 — Pass-2 candidates are order-grain not execution-grain; operator MUST supply execution-level fields via `--custom-value` to disambiguate. Spec §4.3.2 + Codex R7 M#2 LOCK preserved.
8. **Validator shim 2-tuple return shape LOCKED at T-B.2** — `(passes: bool, rejection_reason: str | None)`. NEVER raises (except on programmer errors).
9. **Aggregate-invariant dry-run on `validate_fill_correction`** LOCKED at T-B.2 — SELECT-based simulation of `_recompute_aggregates` post-correction; rejects when simulated `current_size < 0` with reason mentioning `current_size`.
10. **Dispatcher graceful-degradation** LOCKED at T-B.1 — unknown `discrepancy_type` OR sub-classifier exception → `(tier=2, ambiguity_kind='unsupported', correction_target=None, correction_reason=f"classifier exception: {type(e).__name__}: {e}")` from the dispatcher itself (not per-sub-classifier). Pipeline / CLI never crashes.
11. **`default_validator_chain(conn)` dispatch on `affected_table`** LOCKED at T-B.13 — returns a callable that takes `(correction_target, *, affected_table: str, affected_row_id: int)`. Composition with `classify_discrepancy`'s `validator_chain(correction_target)` single-arg shape requires `functools.partial` at C.C construction time.
12. **Cross-bundle pin tests un-skipped at T-B.14** — both pin tests in `tests/integration/test_phase12_bundle_c_cross_bundle_pin.py` PASS against the shipped modules. Strengthened to discriminatingly pin the binding interface contracts (BINDING tier-1 emission shape + affected_table-keyed routing end-to-end via tmp_path schema-v19 fixture).

---

## §11 Forward-binding lessons for Sub-sub-bundle C.C

### #1 — Classifier output → service-layer enforcement layer is the discipline boundary

**Lesson:** C.B classifier produces `ClassificationResult` as ground truth. Lifecycle invariants (correction_action='auto_applied' implies applied_by='auto'; tier-3 override requires non-null operator_truth_value_json; etc.) MUST be enforced at C.C `apply_tier1_correction` INSERT time, BEFORE calling `insert_correction(...)`. Discriminating tests at C.C MUST cover each lifecycle invariant explicitly with both accept- and reject-cases. C.A return report lesson #6 confirmed.

### #2 — Validator chain MUST be re-invoked at C.C apply time (defense-in-depth)

**Lesson:** Spec §4.6 + §5.5 BINDING — even when C.B classifier already invoked the validator chain, C.C service MUST re-run validators at apply time. Schema state may shift between classifier run + apply call (in a backfill scenario or under a long-running transaction). C.C `apply_tier1_correction` step 4 per spec §5.4 LOCKS this discipline. Discriminating test pattern: plant a validator that passes at classifier time + fails at apply time (e.g., a poisoned fixture that mutates the DB between classifier + apply); assert C.C correctly rolls back.

### #3 — `functools.partial` composition between `default_validator_chain` and `classify_discrepancy`

**Lesson:** T-B.13 ships `default_validator_chain(conn)` returning a callable taking `(correction_target, *, affected_table, affected_row_id)`. T-B.1 dispatcher invokes `validator_chain(correction_target)` with single positional arg. C.C `apply_tier1_correction` MUST partial-apply `affected_table` + `affected_row_id` at construction time:

```python
chain = default_validator_chain(conn)
partial_chain = functools.partial(chain, affected_table=disc.affected_table, affected_row_id=disc.affected_row_id)
result = classify_discrepancy(disc, source_payload=..., journal_row=..., validator_chain=partial_chain)
```

Composition is non-obvious; pre-empt in C.C writing-plans or dispatch brief.

### #4 — `_pass_2_required=True` is a free-form-string convention in `correction_reason`

**Lesson:** T-B.4 emits `(tier=2, ambiguity_kind='unsupported', correction_reason="... _pass_2_required=True ...")` when Pass-2 re-fetch is needed. This is a FREE-FORM STRING convention NOT a typed field on `ClassificationResult`. C.D backfill consumer reads `correction_reason` substring match to determine whether to fire Pass 2. Document the exact substring convention in C.D dispatch brief to avoid drift.

### #5 — Shape predicate tightening discipline

**Lesson:** The Codex R1 C#1 → R2 M#1 → R3 M#1 → R4 M#1 sequence tightened the `entry_price_mismatch` Shape B predicate FOUR TIMES. Each iteration plugged a determinism-principle hole the prior iteration missed. C.C handlers that classify operator-supplied `--custom-value` payloads will face the same scrutiny — implement input-shape checks EXPLICITLY at handler entry; reject any unrecognized key set; reject contradictory evidence within the payload. Defense-in-depth predicate enumeration is cheaper than a 4-round Codex cascade.

### #6 — Same-source-keys-on-source-and-journal evidence convergence

**Lesson:** R3 + R4 fix family established: when both `source_payload` AND `journal_row` carry an information field in MULTIPLE forms (e.g., `date` + `fill_datetime`), determinism principle requires (a) each side's internal forms must agree, AND (b) both sides must agree with each other. C.C handlers that operate on multi-field payloads (e.g., `cash_movement_mismatch` multi-field tier-1; `consolidate_using_operator_vwap` tier-2 with operator VWAP + journal-side aggregation key) MUST check internal-consistency on BOTH sides BEFORE cross-side comparison.

### #7 — `Co-Authored-By` footer drift discipline

**Lesson:** Implementer subagents default to the system Bash tool's `Co-Authored-By: Claude Opus 4.7 ...` footer template. CLAUDE.md overrides with "NO Claude co-author footer". The override must be EXPLICITLY stated in every implementer dispatch prompt — passive inheritance from CLAUDE.md is insufficient because subagents have isolated context. C.B R1 fix-bundle 4 commits accidentally carried the footer; corrected at R2 + later by explicit dispatch-prompt language. C.C dispatch brief should pin this discipline in the commit-conventions section explicitly.

---

## §12 CLAUDE.md status-line refresh draft (for orchestrator paste-in at integration merge)

**Phase 12 Sub-bundle C Sub-sub-bundle C.B (Classifier + validator-shim modules) SHIPPED 2026-05-16** at `<integration-merge-SHA>` (integration merge of `phase12-bundle-C-B-classifier-and-validator-shim` via `--no-ff`; 25 commits = 14 task-impl + 1 UP035 ruff style + 4 Codex-R1-fix + 2 Codex-R2-fix + 1 R2-N806-style + 2 Codex-R3-fix + 1 Codex-R4-fix + 1 return-report; **5 Codex rounds → NO_NEW_CRITICAL_MAJOR** convergent tapering (R1 1C/3M/0m → R2 0C/1M/1m → R3 0C/1M/1m → R4 0C/1M/0m → R5 0C/0M/0m); **ZERO ACCEPT-WITH-RATIONALE** — all 1 Critical + 6 Major + 2 Minor resolved with code-content fixes (cleanest finding-disposition record in Phase 12 arc); new `swing/trades/reconciliation_classifier.py` module (10 sub-classifiers + dispatch table + `ClassificationResult` `@dataclass(frozen=True)` + dispatcher with validator-respecting-downgrade + 4 shared `_candidate_choices_*` helpers; spec §4 + §6.2.1 + §8.4 LOCKS preserved verbatim) + new `swing/trades/reconciliation_validators.py` module (4 dry-run validators `validate_fill_correction` + `validate_trade_correction` + `validate_cash_movement_correction` + `validate_snapshot_correction` with `math.isfinite()` guard mirroring `swing/data/models.py` REAL-field discipline + `default_validator_chain(conn)` dispatcher composing on `affected_table`; spec §5.5 LOCKS preserved verbatim) + 12 new test files under `tests/trades/` + 2 un-skipped cross-bundle pin tests strengthened to discriminatingly pin classifier + validator-chain behavior end-to-end via tmp_path schema-v19 fixture; **Pass-2-tier-1-FORBIDDEN LOCK at T-B.4/T-B.5 preserved verbatim** — parametrized regression test plants 6 distinct Pass-2 input shapes + asserts `result.tier == 2` for all (spec §8.4 + brief §0.5 #4 BINDING); **`entry_price_mismatch` Shape A vs Shape B predicate** LOCKED through 4-round Codex tightening sequence — Shape A persisted-JSON-only `{'price'}` OR Shape B full match-tuple (ticker+date+quantity all present + matching); partial-tuple OR contradictory-date-evidence (source-side OR journal-side internal inconsistency) → tier-2 `unsupported` (spec §4.3.1 + determinism principle §4.4); **`pick_schwab_record_<N>` choices `requires_custom_value=True`** preserved per spec §4.3.2 + Codex R7 M#2 LOCK; **graceful-degradation contract at dispatcher** preserved per spec §4.5 — unknown discrepancy_type OR sub-classifier exception → `(tier=2, ambiguity_kind='unsupported', correction_reason=f"classifier exception: ...")` (Phase 11 lesson #2 forward-bind); ZERO journal mutations, ZERO Schwab API calls, ZERO transaction management in C.B scope per dispatch brief §0.5 #1 LOCK; schema v19 unchanged (consumer-side only — C.A shipped v18→v19); 3-surface operator-witnessed gate **PENDING orchestrator-driven** post-merge — S1 inline pytest (4110 fast passing + 3 pre-existing phase8 walkthrough failures + 5 skipped — worktree-side PASS) + S2 classifier walkthrough against CVGI 41 + DHC 39 + VSAT 40 fixtures (covered worktree-side via 27 sub-classifier discriminating tests + strengthened cross-bundle pin tests pinning the BINDING tier-1 emission shape per spec §10.1) + S3 ruff 18 E501 unchanged. **+139 fast tests** (above projection +85-130; matches Phase 9/10/12 overshoot precedent); ruff 18 unchanged; schema v19 unchanged. **6 V2.1 §VII.F amendments banked** (spec §4.3.1 Shape A/B enumeration; spec §4.3.1 contradictory-date-evidence both sides; plan §C.3 `:.2f` rendering pin; plan §C.9 cash_movement multi-field comparison vector; spec §5.5 `functools.partial` composition documentation; spec §6.2.1 cross-reference completeness). **7 forward-binding lessons for C.C dispatch** banked at return report §11 (classifier output is C.B → service-layer enforcement is C.C boundary; validator chain MUST re-invoke at C.C apply time defense-in-depth; `functools.partial` composition between `default_validator_chain` + `classify_discrepancy`; `_pass_2_required=True` free-form-string convention in `correction_reason` is C.B → C.D interface; shape predicate tightening discipline pre-empts cascade Codex rounds; same-source-keys-on-source-and-journal evidence convergence multi-field check pattern; `Co-Authored-By` footer drift requires explicit dispatch-prompt suppression). **R1 fix-bundle 4 commits accidentally carried `Co-Authored-By: Claude Opus 4.7` footer** (deviation #3; banked for operator decision at integration-merge time — rebase-strip OR accept-drift; R2/R3/R4 fix-bundle commits correctly omit). **Sub-sub-bundle C.C executing-plans dispatch UNBLOCKED** (auto-correction service + reconciliation flow pivot + per-(ambiguity_kind, choice_code) handlers; will consume `classify_discrepancy` + `default_validator_chain` from C.B + insert into `reconciliation_corrections` from C.A schema).

---

## §13 Composition-surface verification (per dispatch brief §5.12)

**`^def`/`^class` grep on new modules:**

```
swing/trades/reconciliation_classifier.py:
  @dataclass(frozen=True)
  class ClassificationResult
  ValidatorChainCallable = Callable[[Mapping[str, Any]], tuple[bool, str | None]]
  _SUB_CLASSIFIERS: dict[str, Callable[..., ClassificationResult]] = {}

  # Sub-classifiers (10)
  def _classify_entry_price_mismatch(...)
  def _classify_unmatched_open_fill(...)
  def _classify_unmatched_close_fill(...)
  def _classify_unmatched_fill_shared(...)  # internal helper
  def _classify_stop_mismatch(...)
  def _classify_position_qty_mismatch(...)
  def _classify_close_price_mismatch(...)
  def _classify_cash_movement_mismatch(...)
  def _classify_sector_tamper(...)
  def _classify_snapshot_mismatch(...)
  def _classify_equity_delta(...)

  # Shared candidate-choices helpers (4)
  def _candidate_choices_multi_partial_vs_consolidated()
  def _candidate_choices_multi_match_within_window(n)
  def _candidate_choices_schwab_returned_no_match()
  def _candidate_choices_unknown_schwab_subtype()

  # Public entry
  def classify_discrepancy(discrepancy, *, source_payload, journal_row, validator_chain=None) -> ClassificationResult

swing/trades/reconciliation_validators.py:
  def validate_fill_correction(conn, fill_id, proposed_updates) -> tuple[bool, str | None]
  def validate_trade_correction(conn, trade_id, proposed_updates) -> tuple[bool, str | None]
  def validate_cash_movement_correction(conn, movement_id, proposed_updates) -> tuple[bool, str | None]
  def validate_snapshot_correction(conn, snapshot_id, proposed_updates) -> tuple[bool, str | None]
  def default_validator_chain(conn) -> Callable[[Mapping[str, Any], *, str, int], tuple[bool, str | None]]
```

Public-surface count matches plan §C acceptance criteria.

**`grep -rn "reconciliation_classifier\|reconciliation_validators" swing/{web,pipeline,recommendations,evaluation,metrics,integrations}/` returns ZERO matches** outside the 2 new C.B modules + 12 test files + cross-bundle pin test. No premature C.C scope leak.

**No transaction management in C.B scope** confirmed:
- `grep -n "BEGIN\|COMMIT\|ROLLBACK\|with conn:" swing/trades/reconciliation_classifier.py swing/trades/reconciliation_validators.py` → ZERO matches.
- No `INSERT/UPDATE/DELETE` in either module → ZERO matches.
- No `import schwabdev|import requests|import urllib3` → ZERO matches.

---

## §14 Determinism + Pass-2-FORBIDDEN + validator-respecting-downgrade verification evidence

**Determinism contract (T-B.1 100×-invocation):** confirmed GREEN via `test_classifier_is_deterministic_*` tests in `tests/trades/test_reconciliation_classifier_public_entry.py`. Frozen dataclass equality is deep.

**Pass-2-tier-1-FORBIDDEN (T-B.4 + T-B.5 all-input-shapes-tier-2):** confirmed GREEN via parametrized regression test plant 6 distinct Pass-2 shapes (None, `{"matched": null}`, [], [1-order], [N-orders sum-matches], [N-orders sum-mismatches]) — all assert `result.tier == 2` with appropriate `ambiguity_kind` per spec §6.2.1 menu. Spec §8.4 LOCK + brief §0.5 #4 BINDING.

**Validator-respecting downgrade (T-B.3 poisoned-validator_chain):** confirmed GREEN via `test_dispatcher_downgrades_tier_1_to_validator_rejected_on_chain_false` in `tests/trades/test_reconciliation_classifier_public_entry.py` (CVGI 41 fixture + injected chain returning `(False, "test rejection")` → result.tier=2, ambiguity_kind='validator_rejected', correction_target=None, correction_reason mentions "validator rejected").

**Cross-bundle pin un-skip (T-B.14):** confirmed GREEN — both `test_classifier_module_exists_and_returns_classification_result` and `test_validator_chain_dispatches_on_affected_table` pass and discriminatingly pin the binding interface contracts (CVGI 41 walkthrough + affected_table-keyed routing end-to-end).
