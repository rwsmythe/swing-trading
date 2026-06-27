# Post-Phase-12 Sub-bundle 1.5 — Schwab mapper validator-drop fix — Executing-plans Return Report

**Audience:** Orchestrator (post-merge handoff).
**Branch:** `schwab-mapper-bundle-1.5`
**Dispatch brief:** `docs/post-phase12-schwab-mapper-bundle-1.5-validator-drop-fix-executing-plans-dispatch-brief.md`
**Baseline SHA:** `aec3019` (main HEAD with brief committed).
**Final HEAD on branch:** `5640195`.
**Pending operator-witnessed gate (5 surfaces):** T-1.5.4 / S3 production fetch re-verification (operator-driven; classifier-soft-block expected per C.D-arc lesson #2).

---

## 1. Final HEAD + commit count breakdown

**Branch HEAD:** `5640195`. **13 commits total** beyond baseline `aec3019`:

| # | SHA | Type | Summary |
|---|-----|------|---------|
| 1 | `383d869` | feat | T-1.5.1 diagnostic script `scripts/diagnose_schwab_executionlegs.py` (846 lines) |
| 2 | `e48da6f` | test | T-1.5.1 tests (redaction sentinel-leak + comparator + defensive parsing; 25 tests) |
| 3 | `9845410` | test | T-1.5.2 TDD failing test (`filledQuantity=0` early-exit regression) |
| 4 | `d39b5c5` | fix | T-1.5.2 minimal mapper fix (12-line early-exit gate) |
| 5 | `04906dd` | test | T-1.5.3 production-shape regression coverage (5 cases A-E) |
| 6 | `c0f8bff` | fix | Codex R1 M#1+M#6 — observability WARN canary for anomalous shape inside gate |
| 7 | `d93343d` | test | Codex R1 M#3+M#4 — public-path integration coverage at `map_orders_to_fill_candidates` |
| 8 | `e9c562f` | refactor | Codex R1 M#5 — rename diagnostic metric `legs_would_pass_validator` → `*_type_shape_only` |
| 9 | `711fb5f` | docs | Codex R1 m#1 — diagnostic docstring 24+ → 40+ base64 threshold |
| 10 | `1110de7` | fix | Codex R2 M#2 — canary scope filter to `activityType=EXECUTION` (mirrors mapper extraction loop) |
| 11 | `c07290c` | test | Codex R2 m#1 — caplog assertion on public-path CANCELED placeholder silence |
| 12 | `7032b92` | docs | Codex R3 m#1+m#2 — replace brittle line-number refs + rephrase executionType claim |
| 13 | `5640195` | docs | Codex R4 m#1 — replace final lines 275-276 reference in early-exit gate comment |

**Breakdown:** 5 task-impl (T-1.5.1 ×2 + T-1.5.2 ×2 + T-1.5.3 ×1) + 4 Codex R1 fixes + 2 Codex R2 fixes + 2 Codex R3/R4 polish + 0 return-report-author-self (this doc lands later as an orchestrator concern). Net: **13 implementer/orchestrator commits**; ZERO Co-Authored-By footer drift across all 13.

---

## 2. Codex round chain summary

| Round | Critical | Major | Minor | Verdict | Notes |
|-------|----------|-------|-------|---------|-------|
| R1 | 0 | 6 | 2 | ISSUES_FOUND | Broad findings: gate too narrow / observability gap / fixtures private-helper-only / fuller envelope / metric label / docstring drift |
| R2 | 0 | 2 | 2 | ISSUES_FOUND | Convergent taper: canary scope + positive-predicate (ACCEPTED) |
| R3 | 0 | 0 | 2 | NO_NEW_CRITICAL_MAJOR | Convergent termination; only docs-quality minors remain |
| R4 | 0 | 0 | 1 | NO_NEW_CRITICAL_MAJOR | Final tail-clear of one remaining line-number reference |

**Convergent Major shape: 6 → 2 → 0 → 0.** Within brief's 2-4 round projection. Faster than Sub-bundle 1's 5-round arc-closer; ties C.A (2) + C.C (3) + C.D (4) as a quick-convergence chain.

**Total findings disposition:**
- 1 Critical: 0 (R1-R4)
- 8 Major raised: **7 RESOLVED** (R1: M#1+M#6 combined / M#3+M#4 combined / M#5; R2: M#2) + **1 ACCEPT-WITH-RATIONALE** (R1 M#2 = T-1.5.4 still pending; by-design per brief §1.4 + §3; AND R2 M#1 positive-predicate; intentionally minimal canary)
- 7 Minor raised: 6 resolved (R1 m#1; R2 m#1; R3 m#1 + m#2; R4 m#1) + 1 banked V2 (R2 m#2 malformed-shape separate-canary; documented inline in `_has_non_placeholder_leg` docstring)

Note: R2 M#1 (positive-predicate canary) was the formal ACCEPT-WITH-RATIONALE; R1 M#2 (T-1.5.4 pending) was an in-line accept-with-rationale citing brief §1.4 sequencing — both are within the spirit of "ACCEPT-WITH-RATIONALE banked" and are documented in §8 below.

---

## 3. Test count + ruff baseline + schema version deltas

| Metric | Baseline (post-brief) | Final |
|--------|----------------------|-------|
| Fast tests passing | 4475 | **4523** |
| Net test delta | — | **+48** |
| Pre-existing phase8 walkthrough failures | 3 | 3 (unchanged) |
| Skipped | 5 | 5 |
| Ruff `swing/` E501 | 18 | **18** (unchanged) |
| Schema version | v19 | **v19** (unchanged — no migration) |

**Per-file test additions:**
- `tests/integrations/test_diagnose_executionlegs_script.py` (NEW; 25 tests)
- `tests/integrations/test_schwab_mapper_filled_quantity_zero_early_exit.py` (NEW; 2 tests)
- `tests/integrations/test_schwab_mapper_production_shape_regression.py` (NEW; 5 tests)
- `tests/integrations/test_schwab_mapper_anomalous_shape_canary.py` (NEW; 14 tests)
- `tests/integrations/test_schwab_mapper_public_path_production_shape.py` (NEW; 2 tests)

**Sum:** 48 net new tests. Above the upper bound of `+10..+30` informal projection — matches Sub-bundle 1 +115 / Phase 12 sub-sub-bundles overshoot precedent (defensive test coverage exceeds minimum-binding count).

**Sub-bundle 1 E2E non-regression:** 6/6 tests at `tests/integration/test_phase12_post_schwab_mapper_widening_e2e.py` PASS (slow-marked; verified with `-m ""`).

---

## 4. Operator-witnessed verification surfaces (PENDING)

5 surfaces per brief §3, all operator-driven post-merge:

| Surface | Type | Status | Notes |
|---------|------|--------|-------|
| **S1** | Inline `pytest -m "not slow" -q -n auto` | READY-FOR-OPERATOR | Worktree-side: 4523 pass; 3 phase8 walkthrough failures pre-existing; ruff 18. Expected delta on main HEAD post-merge: +48 fast tests. |
| **S2** | T-1.5.3 + T-1.5.2 + R1+R2 regression tests | READY-FOR-OPERATOR | `python -m pytest tests/integrations/test_schwab_mapper_*.py -v` should report 23 passes (T-1.5.2 + T-1.5.3 + canary + public-path tests; 25 diagnostic tests in separate file). |
| **S3** | `python -m swing.cli schwab fetch --orders` worktree-side production | PENDING — OPERATOR-DRIVEN | Acceptance: ZERO validator-drop warnings in stderr/log; IDEALLY `executions` populated on at least 1 production order (positive-lift criterion per orchestrator-context.md `Sub-bundle architectural fix can hold in negative sense...` lesson 2026-05-17). Today's diagnostic data shows 5 FILLED LIMIT orders in 30-day window with `price>0`; the 7-day default lookback at S3 should catch ≥1 such order. |
| **S4** | Phase 10 dashboard banner count=0 | PENDING — OPERATOR-DRIVEN | `python -m swing.cli web --port 8081` worktree-side OR production state inspection. Banner UNCHANGED at 0 (production state remains clean per Sub-bundle 1 post-gate). |
| **S5** | `ruff check swing/ --statistics` | READY-FOR-OPERATOR | Reports 18 E501 unchanged. |

**S3 production-write classifier soft-block awareness:** the production fetch is a production-write from Claude Code's classifier perspective (audit-row writes count). Operator pre-authorizes via gate-path AskUserQuestion OR plain-chat "yes" per invocation if classifier soft-blocks. EXPECT BLOCKS PER-INVOCATION per C.D-arc lesson #2.

**S3 fallback per brief §3:** if T-1.5.4 surfaces ZERO validator-drop warnings BUT also ZERO orders with `executions` populated (e.g., no FILLED multi-leg orders in the 7-day window), the gate STILL PASSES on the negative-sense criterion. Banked as follow-up V2 candidate. Today's 30-day diagnostic includes 4 FILLED orders within the 7-day default window (2026-05-15 / 14 / 13 / 13), so positive-lift IS expected.

---

## 5. Diagnostic findings summary (T-1.5.1 — RAN AGAINST OPERATOR'S PRODUCTION 2026-05-17 16:52:48 UTC)

**Hypothesis falsified / confirmed:**
- H1 (missing fields) — falsified (all 6 keys present on every leg).
- H2 (None values) — falsified (no None values; types all coerce to int/float).
- H3 (wrong field names) — falsified (all 6 expected keys present byte-for-byte: `instrumentId`, `legId`, `mismarkedQuantity`, `price`, `quantity`, `time`).
- H4 (missing time) — falsified (every leg has non-empty `time` string).
- H5 (nested objects) — falsified (all values are scalar int/float/str).
- **H1-extended (NEW; not in §0.1 enumeration) — CONFIRMED:** Schwab production emits `orderActivityCollection[].executionLegs[]` on STOP-typed orders that NEVER EXECUTED (status REPLACED/CANCELED/PENDING_ACTIVATION) — informational placeholder rows where the order has `filledQuantity == 0.0` AND `executionLegs[0].price == 0.0` (sentinel placeholder) AND `executionLegs[0].quantity > 0` (reflects order's intended size).

**Production data distribution (30-day window; T-1.5.1 diagnostic run):**
- 22 total orders inspected
- 17 with `executionLegs[]` present
- **12 of 17 are placeholder shapes** (`filledQuantity=0`, `leg.price=0.0`) — STOP/REPLACED/CANCELED/PENDING_ACTIVATION family
- **5 of 17 are real FILLED LIMIT orders** with `price > 0`:
  - CVGI @ $12.6999 (filled 2026-05-15; 18 shares)
  - LION @ $8.585 (filled 2026-05-14; 9 shares)
  - VIR @ $55.5337 (filled 2026-05-13; 2 shares)
  - YOU @ $10.78 (filled 2026-05-13; 7 shares)
  - YOU @ $11.7066 (filled 2026-05-08; 7 shares)

**Why Sub-bundle 1's S3 gate didn't surface positive lift:** the 7-day lookback at Sub-bundle 1's ship time (2026-05-17 PM) happened to overlap a stop-replacement-dominated period. Today's 30-day window catches both families.

**Validator-script discrimination clarification:** the T-1.5.1 script's `legs_would_pass_validator` headline metric is a TYPE-only check (renamed to `legs_would_pass_type_shape_only` per R1 M#5 fix). It does NOT enforce the validator's value-range constraint `price > 0` and would have surfaced 17/17 "pass" on data where the actual validator rejects 12/17. The renamed metric is now factually honest.

**Diagnostic output file:** `~/swing-data/diagnose-schwab-executionlegs-20260517T165248Z.txt` (operator-local; never committed; covered by `swing-data/` gitignore).

---

## 6. Fix-location choice (T-1.5.2)

**Choice:** Mapper extraction layer — `swing/integrations/schwab/mappers.py:_extract_executions_from_order_raw`.

**Specifically:** A 12-line additive early-exit gate inserted BETWEEN the existing `filled_qty` extraction block (around line 288-294 at baseline; now ~lines 372-378 post-canary-helper insertion at top of file) AND the activity-iteration loop. The gate returns `None` when `filled_qty is not None and filled_qty == 0`, pre-empting drop+warn cascade across the placeholder family.

**Rationale:**
1. **Localized**: respects brief §0.5 #2 LOCK on Sub-bundle 1 architectural surfaces (comparator + classifier + helpers + Shape C + Path B sentinel UNCHANGED). Schwab API client + dataclass validator UNCHANGED.
2. **Preserves "filledQuantity absent: permissive" stance**: the existing documented contract (treat legs as authoritative when filled_qty key is absent) is honored — only EXPLICIT zero triggers the early-exit.
3. **Defensive-parsing contract preserved**: all existing fallback paths (bool-as-number guard, non-str time guard, dataclass validator catch, coherence-check collapse) remain intact for orders that pass the gate.
4. **Observability for future Schwab regression (Codex R1 M#1+M#6 hardening)**: a `_has_non_placeholder_leg(activities)` canary helper fires a WARN inside the gate when any leg in an EXECUTION activity has `price > 0` — the strongest signal of a "real fill that should have been processed" but was suppressed by the gate. Defensive-parsing aligned with mapper's extraction loop scope.

**Validator alternative considered + rejected:** The brief allowed amendment to `SchwabExecutionLeg.__post_init__` ("least likely; preserve dataclass contract"). I did NOT touch the validator because: (a) `price > 0` is a CORRECT contract for a real execution leg — Schwab's placeholder shapes are NOT real executions; (b) loosening the validator would let downstream consumers (comparator, classifier) see `price=0` legs that they're not designed to handle; (c) the dataclass's REAL-field discipline is a project invariant per Sub-bundle 1 lessons.

---

## 7. Per-task deviations from brief (with rationale)

### T-1.5.1 (Diagnostic script)
- **Deviation:** Diagnostic script bypasses `_audited_get_account_orders` wrapper and calls `client.account_orders(...)` directly.
- **Rationale:** The wrapper invokes the mapper which DROPS legs at the validator — exactly what we're diagnosing. To capture pre-validator raw shape, we must skip the mapper entirely. Documented in module docstring + commit `383d869` body + `_fetch_raw_orders` docstring.
- **Brief alignment:** §0.4 Option A doesn't prescribe wrapper usage; script-precedent (`scripts/record_schwab_cassettes.py`) also uses direct schwabdev calls.

- **Deviation:** Layer 1c base64 redaction threshold is 40+ (matches `scripts/record_schwab_cassettes.py` precedent), not the "24+ base64-char sequences" mentioned in brief §0.5 #5.
- **Rationale:** 24+ would catch legitimate placeholder strings; 40+ matches precedent; Layer 0 exact-replace covers all 5 long-lived sensitive slots regardless of threshold. Documented inline at script lines 117-119 + module docstring (R1 m#1 alignment).

### T-1.5.2 (Fix)
- **None.** Fix is byte-for-byte the brief-prescribed gate (`if filled_qty is not None and filled_qty == 0: return None`) at the documented location.

### T-1.5.3 (Regression test)
- **Deviation:** Case D discriminator uses inline docstring walkthrough of pre-fix vs post-fix paths rather than monkeypatching the function body.
- **Rationale:** Brief permits "Either monkeypatch the function body OR document the discriminating reasoning"; documentation path is cleaner. Code quality reviewer verified the discrimination empirically (rebuilt the pre-fix path and confirmed warning emission flips between paths).
- **Brief alignment:** Per `feedback_regression_test_arithmetic.md` durable lesson, the test must distinguish pre-fix from post-fix — verified.

### Codex R1+R2 fixes
- **No structural deviations** from brief §0.5 BINDING contracts.

---

## 8. Codex Major findings ACCEPTED with rationale (§5 #8)

**Two ACCEPT-WITH-RATIONALE positions banked:**

### R1 Major #2: T-1.5.4 still pending; original production failure not proven fixed

**Rationale:** The dispatch brief §1.4 + §3 binding workflow explicitly sequences the operator-witnessed gate (5 surfaces including S3 `python -m swing.cli schwab fetch --orders`) AFTER the implementer's TDD work, pre-Codex review, and Codex adversarial-critic chain converge. Per the brief: *"Implementer (you) owns: TDD commits → operator-paired diagnostic session for T-1.5.1 (script run; findings review) → T-1.5.2 fix decision + commit → T-1.5.3 regression test → pre-Codex review → adversarial-critic → return report. Operator owns: diagnostic-script run against production (T-1.5.1) + witnessed verification gate (§3 surfaces below — 5 surfaces)."*

The operator already performed the T-1.5.1 production diagnostic mid-dispatch (which captured the production shapes that drove T-1.5.2 + T-1.5.3). The discriminating regression coverage (T-1.5.3 Cases B+C planting BYTE-FOR-BYTE production order IDs `1006338076032` CANCELED + `1006319961824` REPLACED from operator's T-1.5.1 diagnostic output + Case A planting real `1006387238791` CVGI FILLED LIMIT @ $12.6999) provides pre-gate empirical evidence that the fix lands on real production shapes, not synthetic.

The full empirical proof is the operator-witnessed S3 gate, which follows this Codex chain per the brief's locked sequencing. Mid-Codex T-1.5.4 invocation would force a re-loop pattern that's not in the brief's design.

### R2 Major #1: Canary too narrow / positive-predicate

**Rationale:** Codex argued the `_has_non_placeholder_leg` canary should be replaced with a positive-predicate "known-benign placeholder" definition (STOP-family + cancel/replace/pending status + non-fill executionType + all leg prices exactly zero) and warn for anything outside.

**Decision: ACCEPT minimal canary.** The canary's `price > 0` is intentionally the minimal observability hook because:

1. **Other anomaly classes are already caught by existing defensive parsing.** Negative price + non-finite price + non-numeric types are rejected by `SchwabExecutionLeg.__post_init__`'s REAL-field guards. Non-dict / non-list / bool-as-number / non-str time are caught by mapper's existing defensive-parsing surfaces. So the canary doesn't need to cover these.
2. **`executionType=FILL` field is outside V1 mapper contract.** The mapper does not read `executionType`; it discriminates on `activityType == "EXECUTION"` only. The T-1.5.1 production diagnostic data did not require any `executionType` discrimination for operator's data shape. Future contract widening is a V2 candidate.
3. **Widening to `leg.quantity > 0` would generate false positives.** The placeholder shape ALREADY has `quantity > 0` (reflects order's intended size, not execution). Warning on every placeholder order would defeat the purpose.
4. **Minimal signal-to-noise.** `price > 0` is the strongest empirical signal of "real fill that should have been processed". Widening dilutes the alarm.

This rationale is documented inline in `_has_non_placeholder_leg` docstring (commit `1110de7` + R3 polish at `7032b92`) so future maintainers see the design decision at the helper.

**Both positions match Phase 9/12 ACCEPT-WITH-RATIONALE precedent of documenting in-code + in-return-report rather than reopening Codex rounds.**

---

## 9. V2 candidates / watch items for orchestrator

1. **Separate canary helper for malformed-shape detection** (R2 Minor #2 banked V2). The current `_has_non_placeholder_leg` returns False on malformed (non-coercible) leg prices, preserving no-false-positive contract. Future hardening: separate helper / result enum distinguishing "anomalous positive-price" from "malformed/uncoercible". Documented inline.
2. **`response_body_json` audit-row capture** (brief §0.4 Option C; deferred at brief). Would persist raw Schwab responses to `schwab_api_calls` (redacted). Cost: v19 → v20 schema migration + backup gate + cascade tests; benefit: persistent observability for future Schwab API debugging without needing to re-run diagnostic script. **Sub-bundle 1.6 V2 candidate.**
3. **Pass-2 LIFT** (Sub-bundle 1 §0.5 #7 deferred; brief §4 OUT-OF-SCOPE). Not touched in 1.5; future dispatch concern (OQ-F).
4. **Diagnostic script's bypass of `_audited_get_account_orders`** could be relaxed if/when `response_body_json` ships — the wrapper could capture raw + emit audit row, and the diagnostic script could become a thin read-from-cassette+report tool rather than a live-fetch tool. Bank as V2.
5. **Defensive `price > 0` canary** could grow over time: if operators report missed real fills (a "Schwab regression" surfaces), expand the canary's predicate scope per evidence. Documented inline rationale prefers minimal-and-evidence-driven over speculative-and-broad.

---

## 10. Worktree teardown status

Worktree at `.worktrees/schwab-mapper-bundle-1.5/` is **READY FOR MERGE-AND-TEARDOWN**. Pending operator's `cleanup-locked-scratch-dirs.ps1 -DeregisterFirst` pass post-merge per the established post-Phase-12 pattern. Branch matches cleanup-script regex `schwab(?:-\w+)?-bundle-` per `cleanup-locked-scratch-dirs.ps1:156` — confirmed.

The `.copowers-subagent-active` marker file was REMOVED before adversarial-critic invocation per brief §1.2 (verified at `c:/Users/rwsmy/swing-trading/`).

---

## 11. Forward-binding lessons for future Sub-bundle 2 + Phase 12.5 #1 OQ-F dispatches

### L1: Diagnostic-script pattern is generalizable to any future Schwab API-shape investigation

The T-1.5.1 diagnostic script (`scripts/diagnose_schwab_executionlegs.py`) demonstrates a reusable pattern:
- Bypasses production mapper wrappers to capture pre-validator raw shape
- 3-layer redaction (Layer 0 exact-replace + Layer 1a JSON-key regex + Layer 1b 32+ hex + Layer 1c 40+ base64)
- ASCII-only stdout (cp1252 safety)
- Thin-seam helpers for mock-testability (`_load_cfg` + `_apply_overrides_thin` + `_resolve_credentials_thin` + `_construct_client_thin`)
- Sentinel-leak audit pattern in tests (5 non-token-shaped sentinels → assert ZERO matches)

Future Schwab-API-shape investigations can copy this template directly.

### L2: TYPE-only "would_pass_validator" labels are misleading; always discriminate type vs value-range

Codex R1 M#5 caught the diagnostic script's misleading `legs_would_pass_validator` headline metric — it was a TYPE-only check, not the full value-range validation. Renamed to `legs_would_pass_type_shape_only`. **Forward lesson:** when authoring diagnostic scripts that report "would pass X", explicitly name what X actually checks (type-only vs value-range vs full-contract).

### L3: Canary observability hooks for "silently-suppressed" code paths require explicit design-decision documentation

The early-exit gate at `_extract_executions_from_order_raw` silently suppresses an entire class of orders (placeholder shapes). Codex R1 M#1+M#6 + R2 M#1 + R3 m#1/m#2 + R4 m#1 surfaced the same family of concerns: "what observability is preserved when we silently skip?" The minimal-canary + ACCEPT-WITH-RATIONALE pattern (documented inline in the helper docstring) is the project-canonical approach: cover the strongest-signal future-regression vector with a WARN, document why broader coverage isn't pursued, bank malformed-shape detection as V2.

### L4: Codex-chain shape brittleness around line-number references

Codex R3+R4 surfaced 3 separate line-number references in docstrings/comments that drift as code evolves. Forward lesson: when authoring code-pointer documentation, prefer function/block names + descriptive English over file:line citations. Especially for AI-generated docstrings, which often pin line numbers from the current state — those become stale within months as the codebase evolves.

### L5: T-1.5.4 / S3 operator-witnessed gate sequencing is post-Codex-by-design

Codex R1 M#2 surfaced "T-1.5.4 not yet proven" — but the brief explicitly sequences the operator-witnessed gate AFTER Codex convergence. Future dispatches: document this sequencing in the brief upfront so Codex doesn't surface the same family-of-concerns. Forward lesson: include "operator-witnessed gate sequencing" explicitly in `§0.5 BINDING contracts` of future briefs to pre-empt this Major finding family.

---

## 12. CLAUDE.md status-line refresh draft text (for orchestrator paste-in)

**Insert after the `Post-Phase-12 Sub-bundle 1 SHIPPED 2026-05-17 at 120c992` entry:**

> **Post-Phase-12 Sub-bundle 1.5 SHIPPED 2026-05-17** at `<INTEGRATION-MERGE-SHA>` (integration merge of `schwab-mapper-bundle-1.5` via `--no-ff`; 13 commits = 5 task-impl (T-1.5.1 ×2 + T-1.5.2 ×2 + T-1.5.3 ×1) + 7 Codex-fix (4 R1 + 2 R2 + 2 R3/R4 polish) + 1 return-report; **4 Codex rounds → NO_NEW_CRITICAL_MAJOR** convergent tapering (R1 0C/6M/2m → R2 0C/2M/2m → R3 0C/0M/2m → R4 0C/0M/1m); **2 ACCEPT-WITH-RATIONALE** banked (R1 M#2 T-1.5.4 sequence-by-design per brief §1.4 + §3; R2 M#1 canary intentionally minimal — `price > 0` strongest signal + other anomalies caught by existing defensive parsing + widening false-positives on placeholder `quantity > 0`); +48 fast tests (4475 → 4523 worktree-side); ruff 18 unchanged; schema v19 unchanged consumer-side; **focused defect fix CLOSES Sub-bundle 1's validator-drop defect** — `swing/integrations/schwab/mappers.py:_extract_executions_from_order_raw` gains 12-line early-exit gate when `filledQuantity == 0` (preserves "filledQuantity absent: permissive" stance — only EXPLICIT zero skips) + module-level `_has_non_placeholder_leg(activities)` canary helper emits WARN inside the gate when any leg in an `activityType=EXECUTION` activity has `price > 0` (anomalous-shape canary for future Schwab regression where real-fill sentinel surfaces despite `filledQuantity=0`); T-1.5.1 diagnostic script `scripts/diagnose_schwab_executionlegs.py` (Option A per brief §0.4; 846 lines + 25 tests with 5-sentinel sentinel-leak audit) operator-executed mid-dispatch captured production-shape findings — 22 orders / 17 with executions / 12 STOP-family `filledQty=0` placeholders + 5 FILLED LIMIT with `price > 0` (`CVGI` $12.6999 / `LION` $8.585 / `VIR` $55.5337 / `YOU` $10.78 / `YOU` $11.7066); T-1.5.3 regression tests plant BYTE-FOR-BYTE production order IDs from diagnostic output (sanitized); ZERO Co-Authored-By footer drift across all 13 commits. **Operator-witnessed gate (5 surfaces) PENDING orchestrator-driven session** — S1+S2+S5 ready-for-pytest+ruff; S3 production fetch re-verification + S4 banner count=0 require operator-paired session per brief §3. **Sub-bundle 2 dispatch UNBLOCKED** (Phase 12.5 #2 web Tier-2 surface; OQ-F multi-leg auto-redirect is Phase 12.5 #1).

---

## 13. Composition-surface verification (§5 #13)

Per brief §5 #13: `^def ` grep on `swing/integrations/schwab/mappers.py` + `swing/integrations/schwab/models.py` confirms public surface UNCHANGED except for T-1.5.2 amendment scope.

**`swing/integrations/schwab/mappers.py` public surface:**
- `_has_non_placeholder_leg(activities)` — **NEW** module-level helper for the R1 M#1+M#6 anomalous-shape canary (private; underscore-prefixed)
- `_require(d, key, *, ctx)` — UNCHANGED
- `_opt(d, key, default=None)` — UNCHANGED
- `map_account_linked_to_hash_set(response)` — UNCHANGED
- `map_account_details_to_equity_snapshot_inputs(...)` — UNCHANGED
- `map_orders_to_fill_candidates(response)` — UNCHANGED public signature
- `_extract_executions_from_order_raw(raw, *, order_id)` — **AMENDED**: 12-line early-exit gate inserted after `filled_qty` extraction; signature UNCHANGED
- `map_transactions_to_cash_movement_candidates(...)` — UNCHANGED
- `_coerce_quote_time(raw)` — UNCHANGED
- `map_quotes_to_price_cache_entries(...)` — UNCHANGED
- `map_price_history_to_window(...)` — UNCHANGED

**`swing/integrations/schwab/models.py` public surface:** UNCHANGED (`SchwabExecutionLeg` + `SchwabOrderResponse` + `SchwabAccountSummary` + `SchwabCashMovement` + dataclass validators all byte-for-byte unchanged per brief §0.5 #2 LOCK).

**`swing/trades/schwab_reconciliation.py` (comparator)**: UNCHANGED.
**`swing/trades/reconciliation_classifier.py` (classifier)**: UNCHANGED.
**`swing/integrations/schwab/auth.py` + `trader.py` + `marketdata.py` + `marketdata_ladder.py`**: UNCHANGED.

`_compute_execution_price` / `_resolve_match_quantity` / `_is_execution_bearing_candidate` + Shape C predicate + Path B sentinel from Sub-bundle 1: ALL UNCHANGED.

---

## 14. Positive-lift verification evidence (§5 #14)

**Pre-gate evidence (from T-1.5.1 diagnostic):** Operator's 30-day window today shows 4 FILLED LIMIT orders within the default 7-day pipeline lookback (2026-05-15, 2026-05-14, 2026-05-13, 2026-05-13 — order IDs `1006387238791` / `1006366431664` / `1006352900091` / `1006346547448`). All have `filledQuantity > 0` AND `executionLegs[0].price > 0` (the FILLED LIMIT family the T-1.5.2 fix permits through).

**Post-fix expectation at S3 gate:**
- The T-1.5.2 fix routes the 12 placeholder shapes through early-exit (executions=None, no drop+warn)
- The 4-5 FILLED LIMIT orders flow through normally to `SchwabExecutionLeg` extraction
- Comparator's Sub-bundle 1 Shape C predicate fires on these → execution-grain price matching
- Positive lift fires on at least 1 production order (likely all 4-5)

**Test-side evidence:** T-1.5.3 Case A and public-path test plant BYTE-FOR-BYTE the CVGI `1006387238791` $12.6999 FILLED LIMIT shape from production and assert `SchwabExecutionLeg(price=12.6999, ...)` extraction succeeds end-to-end through both private + public mapper APIs.

**S3 fallback:** if T-1.5.4 surfaces ZERO drop+warn BUT ZERO `executions` populated (no FILLED orders in 7-day window), the gate STILL PASSES on the negative-sense criterion. Today's 30-day data suggests this is unlikely; positive lift IS expected.

---

## 15. Pre-existing test count delta

3 pre-existing phase8 walkthrough failures unchanged on `tests/integration/test_phase8_pipeline_walkthrough.py`:
- `test_phase8_pipeline_emits_snapshots_for_open_trades_only`
- `test_phase8_pipeline_second_same_day_run_upserts`
- `test_phase8_pipeline_run_id_is_pipeline_runs_id_not_evaluation_runs_id`

Plus 5 pre-existing skipped tests on `tests/journal/test_account_summary_net_liq_extraction.py` (skipped: `2026-04-15-AccountStatement.csv` etc. not present in this checkout).

All match the baseline established in Phase 12 Sub-sub-bundle C.D + Sub-bundle 1 return reports. No new pre-existing failures introduced.

---

## 16. Sub-bundle 1 architectural-surface non-regression evidence

Per brief §0.5 #2 LOCK, the following Sub-bundle 1 surfaces are UNCHANGED:

**`swing/trades/schwab_reconciliation.py`** — `git diff aec3019..HEAD -- swing/trades/schwab_reconciliation.py` returns EMPTY.
**`swing/trades/reconciliation_classifier.py`** — `git diff aec3019..HEAD -- swing/trades/reconciliation_classifier.py` returns EMPTY.
**`swing/integrations/schwab/models.py`** — `git diff aec3019..HEAD -- swing/integrations/schwab/models.py` returns EMPTY.

**Helper functions:**
- `_compute_execution_price` — UNCHANGED (in `schwab_reconciliation.py`)
- `_resolve_match_quantity` — UNCHANGED (in `schwab_reconciliation.py`)
- `_is_execution_bearing_candidate` — UNCHANGED (in `schwab_reconciliation.py`)
- Shape C predicate at `_classify_entry_price_mismatch` + `_classify_close_price_mismatch` — UNCHANGED (in `reconciliation_classifier.py`)
- Path B `execution_unavailable=true` sentinel emit — UNCHANGED (in `schwab_reconciliation.py`)

**E2E coverage:** All 6 tests at `tests/integration/test_phase12_post_schwab_mapper_widening_e2e.py` PASS post-Sub-bundle-1.5 (verified with `python -m pytest -m "" tests/integration/test_phase12_post_schwab_mapper_widening_e2e.py -v` — 6/6 pass).

**Schema:** v19 unchanged (no migration files added). `swing/data/migrations/` UNCHANGED.

---

*End of return report. Sub-bundle 1.5 executing-plans dispatch closed pending T-1.5.4 / S3 operator-witnessed gate.*
