# Phase 9 Sub-bundle C — Return Report

**Phase:** `phase9-bundle-C-hypothesis-and-equity`
**Final HEAD:** `96d10a0` on `phase9-bundle-C-hypothesis-and-equity`
**Baseline:** `932584a` (BASELINE_SHA per dispatch brief §1.1; post-Sub-bundle-B-merge + housekeeping)
**Worktree-branching-point:** `74432c7` (Sub-bundle C dispatch-brief commit on main)
**Implementer-spawn → final-commit wall-clock:** ~6 hours implementation + ~1 hour Codex convergence ≈ **~7 hours total**. Below dispatch brief §0 expected range (7–11 hr).

---

## §1 Commit chain

| Order | SHA | Type | Subject |
|---|---|---|---|
| 1 | `0ee69ef` | test(data) | T-C.0 — consumer-side schema verification for hypothesis_status_history + account_equity_snapshots |
| 2 | `4bd0b9b` | test(data) | T-C.1 — verify hypothesis_status_history seed rows from T-A.1 migration |
| 3 | `b288c0c` | feat(trades) | T-C.2 — account_equity_snapshots dataclass + repo + service + CLI |
| 4 | `a63c6e6` | feat(data) | T-C.3 — hypothesis_status_history repo |
| 5 | `7a7ae79` | feat(trades) | T-C.4 — hypothesis status audit service + DELETE legacy + CLI rewire |
| 6 | `3e3cfaf` | test(integration) | T-C.5 — E2E for sub-bundle C |
| 7 | `83c3ddc` | feat(trades,journal) | T-C.6 — equity_delta cross-bundle wiring |
| 8 | `1601fdc` | fix(phase9-bundle-C) | Codex R1 Major #2 + #3 + Minor #1 |
| 9 | `96d10a0` | fix(phase9-bundle-C) | Codex R2 Major #1 + Minor #1 + #2 + #3 |

**Breakdown:** 7 task-impl + 2 Codex-fix = **9 commits**.

---

## §2 Codex adversarial-review chain

| Round | Critical | Major | Minor | Verdict | Disposition |
|---|---:|---:|---:|---|---|
| **R1** | 0 | 3 | 1 | ISSUES_FOUND | M#1 ACCEPTED-with-rationale (sign convention spec-vs-brief). M#2 RESOLVED (NaN/0.0 parser footgun → strict parse + None). M#3 RESOLVED (post-migration synth predecessor). m#1 RESOLVED (forbidden-string in Bundle-C docstrings). |
| **R2** | 0 | 1 | 3 | ISSUES_FOUND | M#1 RESOLVED (NaN/inf can pass float() — added math.isfinite check). m#1 RESOLVED (_normalize_to_ms_day_start strict ISO validation + fallback). m#2 RESOLVED (synth marker promoted to constant). m#3 RESOLVED (test_cli_hypothesis _setup() now monkeypatches USERPROFILE+HOME defensively). |
| **R3** | 0 | 0 | 3 | **NO_NEW_CRITICAL_MAJOR** | All R3 minors banked as advisory follow-ups (see §7). |

**ZERO Critical findings across all 3 rounds.** All 4 raised Major findings (1 ACCEPTED-WITH-RATIONALE; 3 RESOLVED in-tree) closed with discriminating regression tests. **Convergent in 3 rounds**, faster than the dispatch-brief §0 estimate of 3–4 rounds and well under Sub-bundle B's 5-round chain.

**Codex thread:** `019e1d0b-ea46-7483-9aa6-2aa48fdabcd8` (preserved through R3).

---

## §3 Test count delta + ruff baseline delta

| Metric | Baseline (post-B-ship) | Post-Bundle-C | Delta |
|---|---:|---:|---:|
| Fast tests passing | 2611 | **2741** | **+130** |
| Fast tests skipped | 1 | 5 | +4 (real-world fixture CSVs not in worktree — SKIP-on-absent pattern) |
| Pre-existing failures | 3 | 3 | 0 (same 3 Phase 8 pipeline-walkthrough rows) |
| Ruff baseline | 18 (E501) | **18 (E501)** | **0** |

Plan §J.3 projected +50–75 for Bundle C; T-C.6 added a parser + 11 service tests on top. Including Codex-fix-driven additions (+7 in R1: 4 synth tests + 3 parser tests; +6 in R2: 5 NaN/inf parser tests + 1 service NaN regression + 1 fallback synth test + 1 malformed-format service test), the +130 net matches the Sub-bundle A + B "biased high" overshoot precedent.

---

## §4 Operator-witnessed verification surfaces (per dispatch brief §3)

| Surface | Result | Notes |
|---|---|---|
| **S1** Post-B-merge baseline | PASS via implementer-side `pytest -m "not slow"` + `swing config policy show` smoke read | Same 2611 pre-bundle baseline; pre-existing Phase 8 walkthrough failures untouched. |
| **S2** Consumer-side schema verification | PASS via T-C.0 (11 tests) + T-C.1 (9 tests) | hypothesis_status_history (7 cols + partial-unique current index + FK CASCADE) + account_equity_snapshots (8 cols + unique (date,source) + CHECK enum + CHECK > 0) all verified against the v17 schema landed by T-A.1; 4 seeded hypothesis_status_history rows confirmed shape. |
| **S3** account_equity_snapshots CLI | Pending operator gate | Operator runs `swing account snapshot --equity 1300` (today's last completed session) + `--equity 1400 --date 2026-04-01` (back-record advisory). Implementer-side coverage: 8 CLI tests cover happy path + --date override + back-recorded advisory + re-record UPSERT + invalid-input rejection. |
| **S4** hypothesis status audit | Pending operator gate | Operator runs `swing hypothesis update <id> --status paused --reason "operator gate S4"` + re-runs (identity transition; INFO message "already paused"; no new history row). Implementer-side coverage: 28 service tests + the test_hypothesis_update_identity_returns_info_not_error CLI test (per CLI test added in T-C.4). |
| **S5** Read-path source-ladder precedence | Pending operator gate | Operator invokes `get_latest_snapshot_on_or_before(asof=today)` from REPL/test. Implementer-side coverage: T-C.2 repo tests cover schwab_api > tos_csv > manual + same-date tie-break + with_provenance shape; Bundle C E2E §3 verifies the path end-to-end with all 3 sources inserted. |
| **S6** T-C.6 equity_delta integration | Pending operator gate | Operator runs `swing journal reconcile-tos --csv-path <real-world-export> --period-end <date> --notes "operator gate S6 equity_delta"`. Implementer-side coverage: 11 service tests pin happy-path emit, both-NULL when journal missing / source missing, $10.00 boundary strict-GT, $10.01 emit, $9.99 no-emit, source-ladder on journal snapshot fetch, snapshot-on-or-before period_end semantics, snapshot dated after period_end skipped, within-run dedup single row, regression-clean on non-equity fixtures, NaN-poisoned source row gracefully NULLed. |
| **S7** pytest + ruff | PASS implementer-side | 2741 fast tests pass; ruff baseline 18 (E501 only) unchanged. |

**Production-write classifier soft-block awareness:** S3-S6 are production writes that the orchestrator will surface to the operator with a plain-chat confirmation request before invocation. This does NOT affect the implementer; it's an orchestrator-side gating concern.

---

## §5 Per-task deviations from the plan

| Task | Deviation | Rationale |
|---|---|---|
| T-C.2 | Plan envisaged `AccountEquitySnapshot` dataclass landing in T-C.2 commit; `HypothesisStatusHistory` dataclass landing separately in T-C.3 commit. Both landed in the T-C.2 models.py edit (single `swing/data/models.py` trailing-block addition with shared helper constants `_AES_SOURCES` + `_HYPOTHESIS_STATUSES`). | Benign consolidation: the two dataclasses share the section docstring + format. Plan §B file map lists both at MODIFY `swing/data/models.py` so the deviation is on commit-boundary, not file-boundary. Discoverable via `git log -p -- swing/data/models.py`. |
| T-C.3 | The legacy `update_hypothesis_status` repo function + `HypothesisStatusTransitionError` + `_VALID_STATUSES` + `_ALLOWED_TRANSITIONS` were all DELETED from `swing/data/repos/hypothesis.py` in T-C.4, NOT a separate T-C.3 step. | Plan §A.1.1 binds T-C.4 to do the delete; that's where it landed. The repo file shrunk from ~131 lines to ~67 lines (CRUD reads only). The transition rules + exception class moved to the new service module per single-write-path discipline. |
| T-C.4 | 8-step transactional sequence has a 5a substep landed in Codex R1 Major #3 fix: when `update_close_open_interval` returns rowcount=0 (no open interval found for a post-migration hypothesis), synthesize the missing predecessor row inline BEFORE the new transition row INSERT. Brief / plan did NOT enumerate this case. | Forward-binding hardening: future hypothesis-creation surfaces (V2 web form) would create a hypothesis_registry row WITHOUT a seed history row; the first transition without the synth path would orphan the initial-status audit interval. The fix adds: SELECT created_at alongside status; synthesize predecessor with status=current_status + effective_from=registry.created_at-day-start-anchor (via NEW `_normalize_to_ms_day_start` helper) + effective_to=now + change_reason=`SYNTH_PREDECESSOR_CHANGE_REASON` constant + recorded_at=now. Discriminating clamps for future-dated created_at + malformed date prefix. +4 service tests pin the path. |
| T-C.6 | The dispatch brief §0.5 #5 sign convention says `equity_delta_dollars = source - journal`. Spec §3.2 says `account_equity_journal_dollars - account_equity_source_dollars` (journal - source). Implementation follows the SPEC (the LOCKED authoritative artifact at 31ee51c). | ACCEPT-WITH-RATIONALE banked in §6 below. The brief has an inverted-sign typo; the spec is canonical. Banked for orchestrator to ratify in next Bundle dispatch. |
| T-C.6 | Within-run dedup tuple shape for `equity_delta`: brief §0.7 forward-binding lesson predicted `(None, "equity_delta", None, None, None, None, <payload-hash-or-None>)` (with `field_name=None`). Implementation passes `field_name="net_liquidating_value"` (the actual disagreeing field per spec §3.3). Dedup tuple becomes `(None, "equity_delta", "net_liquidating_value", None, None, None, <payload>)`. | Stronger dedup discriminator: identifies the field that disagreed (spec §3.3 makes `field_name` NOT NULL on the schema; the dedup tuple stays consistent). Run-grain emission means dedup is naturally single-row regardless of disambiguator. Discriminating regression test in T-C.6 §10 (`test_equity_delta_dedup_single_row_per_run`) pins exactly-one row per run. |

No other plan deviations.

---

## §6 Codex Major findings ACCEPTED with rationale

**1 ACCEPT-WITH-RATIONALE banked. Three prior Sub-bundles' precedent: Sub-bundle A = 2, Sub-bundle B = 1, Sub-bundle C = 1. Trend remains at or below 2 per bundle.**

### R1 Major #1 — equity_delta sign convention (brief vs spec mismatch)

**Codex finding:** dispatch brief §0.5 #5 directs `equity_delta_dollars = source - journal` while spec §3.2 says `account_equity_journal_dollars - account_equity_source_dollars` (i.e., journal - source). The implementation matches the spec (journal - source) at `swing/trades/reconciliation.py:365-367` + tests at `tests/trades/test_reconciliation_service.py:953-955` pin negative deltas when source is higher than journal.

**Acceptance rationale:** the SPEC is the LOCKED authoritative artifact (locked at commit `31ee51c` per spec metadata + plan §A.0 binding-decisions). The dispatch brief is a worktree-config + scope wrapper authored during the orchestrator pipeline; brief-vs-spec conflicts resolve in favor of the spec per the project's source-of-truth correction protocol (V2.1 §VII.F). The brief carries an inverted-sign typo that does NOT alter the implementation outcome — the spec wording is correct + binding.

**Forward-binding consequence:** the next Bundle dispatch (Sub-bundle D) MUST inherit the spec sign convention. Orchestrator triage at the brief-author level should align the brief's §0.5 #5 wording with spec §3.2 on the next dispatch (cosmetic; no schema or implementation impact).

**Verification:** the existing T-C.6 tests pin the spec sign:
- `test_equity_delta_emit_when_both_sides_available_and_above_threshold` asserts `out.equity_delta_dollars == -100.0` when journal=$1300, source=$1400 (i.e., 1300 - 1400 = -100).
- All boundary tests use the spec convention.

No further action; documenting here for orchestrator follow-up.

---

## §7 Watch items surfaced but not acted on

(For Sub-bundles D/E to absorb OR for orchestrator-context capture.)

1. **R3 m#1: tests/cli/test_cli_hypothesis.py monkeypatch backwards-compat path uses `os.environ` mutation when caller doesn't pass `monkeypatch` parameter.** The `_setup()` helper accepts an optional `monkeypatch` parameter (Codex R2 hardening) + falls back to direct `os.environ["USERPROFILE"]` / `os.environ["HOME"]` mutation for the 8 existing tests that call `_setup(tmp_path)` without the parameter. This still leaks a tmp home into later tests at the process level. Codex banked it: "apply the same env monkeypatch pattern there in a follow-up." V2/polish-bundle hardening: add `monkeypatch` to each hypothesis CLI test signature + pass it through.

2. **R3 m#2: test_equity_delta_not_emit_when_source_is_nan_or_inf only tests NaN, not inf, despite the test name implying both.** Parser-level tests cover all spellings (nan/NaN/NAN + inf/-inf/infinity/Infinity); service-level regression covers only NaN. Codex banked it: "either parameterize the service regression, or narrow the test name/docstring." V2/polish-bundle: parameterize.

3. **R3 m#3: a corrupted or direct-SQL non-finite `account_equity_snapshots.equity_dollars` row would fail reconciliation when `get_latest_snapshot_on_or_before` hydrates the dataclass.** Codex banked it as acceptable: "service/repo public paths validate on normal use, and direct DB corruption should be loud. Bank this as acceptable unless V2 Schwab ingestion adds a lower-level write path." Forward-binding for V2 Schwab API: if the integration emits snapshot rows via repo bypass (raw SQL), add an `__post_init__` failure-tolerance mode OR migrate the dataclass hydrate to raise a domain-specific exception.

4. **`DeprecationWarning` on `datetime.utcnow()` in `swing/data/datetime_helpers.py`.** Carried forward from Sub-bundle A return report §7 + Sub-bundle B return report §7. Python 3.12+ deprecates `utcnow()`. Bundle C tests pile on more warnings; V2 should migrate to `datetime.now(UTC).replace(tzinfo=None)`.

5. **3 pre-existing `test_phase8_pipeline_walkthrough.py` failures.** Confirmed pre-existing on main HEAD `74432c7` (NOT Bundle C regressions). Banked from Sub-bundles A + B return reports. Triage pending — separate dispatch.

6. **Real-world Schwab/TOS fixture CSVs at `thinkorswim/*.csv` are NOT tracked in git.** The 4 parametric tests in `test_account_summary_net_liq_extraction.py` SKIP-on-absent in the worktree (they would PASS on the operator's main checkout where the fixtures live). Operator-witnessed gate S6 covers the production-write path against the actual fixtures.

---

## §8 Worktree teardown status

Pending integration merge by orchestrator. Branch + worktree retained at `96d10a0`. ACL-locked husk expected after orchestrator's merge + cleanup script (per Phase 8 / Sub-bundle A + B precedent).

Marker file `c:/Users/rwsmy/swing-trading/.copowers-subagent-active` removed before Codex R1 invocation per dispatch brief §2.1 step 1.

---

## §9 Composition-surface verification

Per dispatch brief §0.8 + plan §I item #11 + §J.2 #8 — `^def` grep enumeration of new service entry points returns exactly one match per function:

```
$ grep -rn "^def supersede_active_policy" swing/
  swing/trades/risk_policy.py:81  (Sub-bundle A; out of scope)

$ grep -rn "^def run_tos_reconciliation" swing/
  swing/trades/reconciliation.py:106  (Sub-bundle B; T-C.6 modified body)

$ grep -rn "^def update_hypothesis_status_with_audit" swing/
  swing/trades/hypothesis.py:107  (T-C.4 NEW)

$ grep -rn "^def record_snapshot" swing/
  swing/trades/account_equity_snapshots.py:65  (T-C.2 NEW)

$ grep -rn "^def extract_account_summary_net_liq" swing/
  swing/journal/tos_import.py:218  (T-C.6 NEW)
```

Cross-references in plan text + brief enumerated correctly. No hand-duplication of definitions surfaced.

`SYNTH_PREDECESSOR_CHANGE_REASON`, `HYPOTHESIS_STATUSES`, `EQUITY_DELTA_EMIT_THRESHOLD_DOLLARS`, `BACK_RECORD_THRESHOLD_DAYS`, `MATERIAL_BY_TYPE`, `DISCREPANCY_TYPES`, `RESOLUTION_TYPES` constants are defined ONCE at their canonical module + imported by tests. Single source of truth.

Plan §J.2 acceptance gates:

```
$ grep -E "^EXPECTED_SCHEMA_VERSION = 17$" swing/data/db.py
  swing/data/db.py:25:EXPECTED_SCHEMA_VERSION = 17

$ test -f swing/data/migrations/0017_phase9_risk_policy_and_reconciliation.sql
  (exists)

$ test ! -f swing/data/migrations/0016_phase9_risk_policy_and_reconciliation.sql
  (correctly absent)

$ grep -rn "INSERT OR REPLACE\|REPLACE INTO" swing/  (executable code only)
  (only comments in Sub-bundle A + B docstrings + migration SQL banner;
   Bundle C new files all reworded to avoid the literal phrases.
   ZERO executable matches.)

$ ! grep -n "^def update_hypothesis_status" swing/data/repos/hypothesis.py
  (empty — function deleted per plan §A.1.1; ImportError test
   tests/trades/test_hypothesis_service.py::test_legacy_repo_function_is_deleted
   pins it.)

$ grep -rn "conn.commit()" swing/data/repos/account_equity_snapshots.py swing/data/repos/hypothesis_status_history.py
  (empty — Bundle C new repos respect caller-controlled-tx convention.)

$ grep -rn "CallerHeldTransactionError\|in_transaction" swing/trades/risk_policy.py swing/trades/reconciliation.py swing/trades/account_equity_snapshots.py swing/trades/hypothesis.py
  (4+ matches — all 4 services correctly reject caller-held tx.)

$ grep -rn "__post_init__" swing/data/models.py
  5+ matches (RiskPolicy, ReconciliationRun, ReconciliationDiscrepancy,
   AccountEquitySnapshot, HypothesisStatusHistory)
```

All §J.2 grep gates GREEN.

---

## §10 Hand-off notes for Sub-bundle D dispatch

(Forward-binding contracts Bundle D + E must mirror / consume.)

1. **Migration 0017 schema is at v17 + UNCHANGED.** Bundle C is consumer-side only. `EXPECTED_SCHEMA_VERSION = 17`. Sub-bundle D ships sector/industry tamper hardening on top of the same v17 schema; no migration.

2. **`update_hypothesis_status_with_audit` is the canonical service entry point.** Bundle D + future web surfaces for hypothesis management MUST route through it. The legacy repo function is GONE (ImportError pin in `test_hypothesis_service.py::test_legacy_repo_function_is_deleted`).

3. **`SYNTH_PREDECESSOR_CHANGE_REASON` is the operator-/code-filterable marker for auto-synthesized predecessor rows.** Future code that audits hypothesis_status_history may filter on this constant via exact equality. Avoid string drift.

4. **`record_snapshot` is the canonical service entry point for account_equity_snapshots.** Future Schwab API V2 path emits its own snapshot rows; the service is reusable for that with `source="schwab_api"` instead of `"manual"`.

5. **Source-ladder precedence on `get_latest_snapshot_on_or_before`:** `schwab_api > tos_csv > manual` at the same snapshot_date. Bundle D's ad-hoc `system_audit` reconciliation_run (per plan §A.4) does NOT touch account_equity_snapshots; the source-ladder lookup stays scoped to the 3 spec-enumerated sources.

6. **`EQUITY_DELTA_EMIT_THRESHOLD_DOLLARS = 10.00` (strict GT).** Bundle D's `sector_tamper` discrepancy is INDEPENDENT of equity_delta; no threshold interaction.

7. **`extract_account_summary_net_liq` is in `swing/journal/tos_import.py`.** Future TOS parser additions (e.g., the banked Bundle E Account Order History multi-line fix) should NOT touch the Account Summary parsing path. The parser is strict — returns None on missing-row, malformed-value, NaN, inf, dash placeholder, N/A.

8. **`_normalize_to_ms_day_start` helper at `swing/trades/hypothesis.py`** with strict ISO-prefix validation + caller-supplied fallback. Could be promoted to `swing/data/datetime_helpers.py` if a future caller in another bundle needs the same normalization. Not a blocker.

9. **`account` CLI group is freshly registered** with `swing account snapshot`. Bundle D + E may add subcommands here (e.g., `swing account snapshot-history --limit N`).

10. **The 4 ACCEPT-WITH-RATIONALE positions across Sub-bundles A+B+C are all banked for orchestrator-context capture:**
    - A R1 M#2 user-config hand-edit V2-hardening
    - A R3 M#1 ratification single-fire by-design
    - B R1 M#1 partial — equity_delta deferred (NOW RESOLVED via T-C.6)
    - **C R1 M#1 — equity_delta sign convention spec-vs-brief (this report §6)**

11. **3 R3 Minor watch items banked at §7** for D/E or polish-bundle absorption.

12. **CLAUDE.md gotcha promotions:** the Codex R2 finding (NaN/inf can pass `float()` un-guarded) is a NEW gotcha candidate. Suggest orchestrator promote to CLAUDE.md "Python `float()` happily accepts non-finite spellings ('nan', 'inf', 'Infinity', case-insensitive); always pair with `math.isfinite()` when parsing external numeric sources." Pattern complement to the existing yfinance + matplotlib drift family.

---

## §11 Operator-side action items

1. **Verify the new `swing account snapshot` CLI against today's actual account equity** during the operator-witnessed gate S3 walkthrough. Recommend running both happy-path (today's date implicit) + back-record (`--date 2026-04-01 --equity 1300` or similar) to confirm advisory printing.

2. **Verify the new `swing hypothesis update` CLI** still rejects invalid transitions (active → closed-target-met allowed; closed-target-met → active rejected) AND now treats identity transitions (active → active) as INFO `already <status>`, NOT ERROR. The legacy repo function behaviour was reject-as-error.

3. **Verify the T-C.6 equity_delta integration** during operator-witnessed gate S6 against the real-world Schwab/TOS export at `thinkorswim/2026-05-12-AccountStatement.csv` (or any of the 4 fixtures). Confirm:
   - reconciliation_run row's `account_equity_source_dollars` matches the Account Summary's Net Liquidating Value verbatim.
   - reconciliation_run row's `account_equity_journal_dollars` matches the most-recent `account_equity_snapshots` row on-or-before the period_end (from operator-supplied snapshot via S3, or NULL if S3 hasn't seeded one).
   - if |delta| > $10.00, an `equity_delta` discrepancy row exists with material_to_review=0.
   - if |delta| ≤ $10.00, NO `equity_delta` discrepancy row exists.

4. **Phase 9 risk_policy is at policy_id=4 in production** (per Sub-bundle A return report §11). Bundle C does NOT mutate risk_policy; the row stays at 4 regardless of how many account snapshot or hypothesis update invocations execute.

5. **Production DB schema_version remains at v17** post-Bundle-C (no migrations in Bundle C). Operator can verify via `python -c "from swing.data.db import EXPECTED_SCHEMA_VERSION; print(EXPECTED_SCHEMA_VERSION)"` → 17.

6. **The 3 pre-existing `test_phase8_pipeline_walkthrough.py` failures** remain unchanged; triage out of scope for Bundle C.

7. **Optional V2 hardening items** banked in §7 above:
   - tests/cli/test_cli_hypothesis.py full monkeypatch plumbing
   - parametrize the service NaN-vs-inf regression
   - low-level (Schwab API) write-path defensive validation
   - `datetime.utcnow()` migration to timezone-aware
   - thinkorswim/*.csv fixtures: tracked-in-git policy decision

---

## §12 Dispatch metadata

- **Brief author:** Orchestrator session 2026-05-12 (post-Sub-bundle-B-merge + housekeeping).
- **Brief commit:** `74432c7` on main.
- **Implementer-spawn:** 2026-05-12.
- **Total wall-clock:** ~6 hr implementation + ~1 hr Codex convergence (3 rounds at MCP-driven cycle). Total **~7 hr**. Below dispatch brief §0 expected duration of "7–11 hr"; consumer-side bundle precedent (Sub-bundle A + B return reports).
- **Marker file:** removed before R1 invocation per dispatch brief §2.1 step 1.
- **Codex thread:** `019e1d0b-ea46-7483-9aa6-2aa48fdabcd8` (preserved through R3).
- **Final HEAD:** `96d10a0` on `phase9-bundle-C-hypothesis-and-equity`.
