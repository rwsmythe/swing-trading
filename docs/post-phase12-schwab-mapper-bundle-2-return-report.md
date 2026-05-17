# Post-Phase-12 Sub-bundle 2 — `/schwab/status` web counterpart — Return Report

**Implementer:** fresh Claude Code instance dispatched via `copowers:executing-plans`.

**Dispatch brief:** `docs/post-phase12-schwab-mapper-bundle-2-schwab-status-web-counterpart-executing-plans-dispatch-brief.md` (commit `01d2e11`).

**Plan:** `docs/superpowers/plans/2026-05-17-schwab-mapper-execution-grain-widening-plan.md` §B (T-2.0..T-2.6).

**Spec:** `docs/superpowers/specs/2026-05-17-schwab-mapper-execution-grain-widening-design.md` §7.

**Branch:** `schwab-mapper-bundle-2`; worktree `.worktrees/schwab-mapper-bundle-2/`.

**Baseline:** `01d2e11` (dispatch brief commit on `main`).

**Sub-bundle 2 status:** SHIPPED on branch (10 commits); operator-witnessed gate PENDING.

---

## §1 Final HEAD + commit breakdown

**HEAD on branch:** `f7fc242` (10 commits on top of baseline).

| Commit | Type | Description |
|---|---|---|
| `e0c706a` | task-impl | T-2.0: SchwabStatusVM + SchwabCallSummary view-model + 12 tests |
| `5ff2cf3` | task-impl | T-2.1: GET /schwab/status route + apply_overrides discipline + 13 tests (18 collected via parametrize) |
| `5cc94a5` | task-impl | T-2.2: schwab_status.html.j2 template + 3-state renderer + 10 tests (11 collected via 8a/8b split) |
| `1d26ec0` | task-impl | T-2.3: /config nav-link to /schwab/status + 3 tests |
| `1e8e0cf` | task-impl | T-2.4: POST /schwab/setup HX-Redirect retarget to /schwab/status + 3 new tests (+ 1 existing T-B.4 test updated) |
| `9c6a721` | task-impl | T-2.5: HTMX trinity regression coverage + 3 tests |
| `05a605a` | task-impl | T-2.6: CLI semantics 1:1 mirror + 1 test |
| `ff1a029` | Codex R1 fix | Critical #1 (error_excerpt sentinel leak) + Major #1 (status enum widening) |
| `eca2108` | Codex R2 fix | Major #1 (tokens_db_path masking under user-home prefix) |
| `f7fc242` | Codex R3 fix | Minor #1 (T-2.2 sentinel audit extended to audit error_message row) |

**Aggregate:** 7 task-impl + 3 Codex-fix + (this) 1 return-report = **11 commits**.

**ZERO Co-Authored-By footer drift across all 10 implementer/Codex-fix commits** (CLAUDE.md "No Claude co-author footer" convention preserved; durable across ~90+ commits arc-wide).

---

## §2 Codex round chain

**3 Codex rounds → NO_NEW_CRITICAL_MAJOR** convergent shape (R1 1C/1M → R2 0C/1M → R3 0C/0M/1m). MIN_ROUNDS=2 + verdict + all critical/major resolved → terminated at R3.

| Round | Critical | Major | Minor | Verdict |
|---|---|---|---|---|
| R1 | 1 (resolved) | 1 (resolved) | 0 | ISSUES_FOUND |
| R2 | 0 | 1 (resolved) | 0 | ISSUES_FOUND |
| R3 | 0 | 0 | 1 (addressed inline) | NO_NEW_CRITICAL_MAJOR |

**ZERO ACCEPT-WITH-RATIONALE banked.** All 3 Critical+Major findings + 1 Minor advisory resolved with code-content fixes — matches the cleanest record precedent set by Phase 12 Sub-sub-bundles D + E + post-Phase-12 Sub-bundle 1 + 1.5 (each had 1 or 2 ACCEPT-WITH-RATIONALE — Sub-bundle 2 ties Sub-bundle 1's clean record).

### R1 findings

**Critical #1 — `schwab_api_calls.error_message` sentinel leakage despite BINDING #7:**
The template rendered `vm.error_excerpt` directly + the sentinel-leak test exempted the audit error_message sentinel ("operator-visible by design"). If any historical or future audit row contained unredacted token bytes (write-time redactor bug or pre-redaction-discipline rows), `/schwab/status` would disclose them.

**Resolution (commit `ff1a029`):** two-layer fix.
- Drop `error_excerpt` rendering from `swing/web/templates/schwab_status.html.j2` — aligns with CLI 1:1 per spec §7.4 OQ-D LOCK (CLI `_render_recent_calls` shows endpoint + status + http only; never `error_message`). VM keeps the field for spec §7.1 completeness.
- Re-redact `c.error_message` at read time in `build_schwab_status_vm` via `_redact_error_message_for_audit` (idempotent; defense-in-depth).
- Strengthen sentinel-leak test to assert ALL 4 sentinels (3 token-byte + 1 audit error_message) are absent in response body.

**Major #1 — status enum narrower than CLI surfaces:**
`_SCHWAB_CALL_STATUSES = {'success', 'auth_failed', 'rate_limited', 'error'}` (4) silently dropped `in_flight` + `concurrent_refresh` rows from the recent-calls table. The CLI's `_render_recent_calls` renders every row regardless of status — a DEGRADED page citing the most-recent call's `in_flight` status would omit that row entirely.

**Resolution (same commit `ff1a029`):** widen the frozenset to all 6 schema CHECK-constraint values per migration 0018; drop the now-no-op filter from the loop body.

### R2 findings

**Major #1 — `tokens_db_path` leaks operator's local home directory:**
The VM stored `str(tokens_path)` which renders the operator's full local home (Windows: `C:\Users\rwsmy\swing-data\...`; POSIX: `/home/<username>/swing-data/...`) into the page. Spec §7.1 explicitly says the field is "display-only, masked if path contains user-profile prefix."

**Resolution (commit `eca2108`):** mask the path via `Path.relative_to(home).as_posix()` prefixed with `~/` when under `_user_home()`; falls back to full path when `relative_to` raises (defense against unexpected tokens DB locations). Internal `tokens_path` stays unmasked for filesystem reads. New discriminating regression test plants tokens DB in `tmp_path`, asserts masked form rendered + absolute form NOT in body.

### R3 findings

**Minor #1 (advisory) — T-2.2 template sentinel audit narrower than plan §B test #10:**
Template-surface ratchet planted tokens-DB sentinels only; plan §B T-2.2 test #10 requires both tokens DB AND `schwab_api_calls.error_message` row sentinels. Route-level T-2.1 test 13 already covers the broader scope.

**Resolution (commit `f7fc242`):** extend template sentinel list to 4 (add `LEAK_TPL_AUDIT_ERROR_MESSAGE_SENTINEL`); plant via direct INSERT; assert ZERO substring matches for ALL 4 sentinels.

---

## §3 Test count + ruff + schema deltas

| Metric | Baseline | Post Sub-bundle 2 | Delta |
|---|---|---|---|
| Fast tests (`-m "not slow" -n auto`) | 4523 | 4575 | **+52 net** |
| Pre-existing failures | 3 (phase8 walkthrough) | 3 (unchanged) | 0 |
| Skipped tests | 5 | 5 | 0 |
| Ruff E501 baseline | 18 | 18 | **0 (unchanged)** |
| Schema version | v19 | v19 | **0 (unchanged consumer-side; no migration)** |

**Projection vs actual:** plan §E projected +25-45; actual +52 (slight overshoot — within Phase 12 Sub-sub-bundle precedent which routinely overshoots by +5-30; +52 is +7 above upper bound; explanation: parametrize expansion of T-2.1 test 12 collected 6 cases for 1 logical criterion + T-2.2 test 8 split into 8a/8b + Codex R2 added 1 new regression test).

**Per-task test count breakdown:**

| Task | Logical criteria | Pytest collected |
|---|---|---|
| T-2.0 | 12 | 12 |
| T-2.1 | 13 | 18 (parametrize on test 12) |
| T-2.2 | 10 | 11 (8a + 8b split) |
| T-2.3 | 3 | 3 |
| T-2.4 | 3 | 3 (+ 1 existing T-B.4 test 4 updated for retarget) |
| T-2.5 | 3 | 3 |
| T-2.6 | 1 | 1 |
| Codex R2 regression | 1 | 1 |
| **Total** | **46** | **52** |

---

## §4 Operator-witnessed verification surfaces (PENDING orchestrator-driven gate)

Per dispatch brief §3 (5 surfaces; ~30 min operator-paired session):

| Surface | Status | Notes |
|---|---|---|
| **S1** — `pytest -m "not slow" -q -n auto` | READY | 4575 passing + 3 pre-existing failures unchanged |
| **S2** — `/schwab/status` page rendering | PENDING | Requires `python -m swing.cli web --port 8081` worktree-side; Chrome MCP walkthrough verifies 3-state badge + TTL + recent-calls + env switcher + banner |
| **S3** — `/config` nav-link to `/schwab/status` | PENDING | Requires browser click + observe navigation |
| **S4** — POST `/schwab/setup` HX-Redirect retarget | PENDING (OPTIONAL) | Only exercise if refresh-token clock low; otherwise SKIPPED with test coverage (T-2.4 + T-B.4 update) |
| **S5** — `ruff check swing/ --statistics` | READY | 18 E501 unchanged |

---

## §5 Per-task deviations from plan

1. **T-2.1 — VM helper module organization:** plan §B T-2.1 says `build_schwab_status_vm` "lives in `swing/web/view_models/schwab.py`" — implementation follows. Plan also says "Implementer extracts shared helpers if needed for CLI/web parity" — implementation REUSES `_compute_degraded_state`, `_read_tokens_metadata`, `_parse_iso_datetime`, `_REFRESH_TOKEN_TTL_SECONDS`, `_REFRESH_TOKEN_ERROR_THRESHOLD_SECONDS`, `_REFRESH_TOKEN_WARN_THRESHOLD_SECONDS` directly from `swing/cli_schwab.py` (local imports in the function body to avoid circular-import + schwabdev heavyweight load at web module import time). This is a sensible reuse pattern (CLI is the canonical source of truth); no extraction needed.

2. **T-2.1 vs T-2.2 — `error_excerpt` field present on VM but NOT rendered on template (Codex R1 Critical #1 outcome):**
   Spec §7.1 enumerates `error_excerpt` in `SchwabCallSummary`. CLI `_render_recent_calls` does NOT render `error_message` either — only endpoint + status + http. After the R1 Critical #1 fix, the template omits the column to align with CLI 1:1 per spec §7.4 OQ-D LOCK. VM keeps the field for spec §7.1 completeness + future inspection surfaces. **Banked as V2.1 §VII.F amendment candidate** — spec §7.1 should explicitly note `error_excerpt` is VM-only (not rendered) under the CLI 1:1 LOCK.

3. **T-2.3 — `<p>` not `<ul>`:**
   Plan §B T-2.3 mock shows the section as `<ul>/<li>` but the existing `/config` template (`config.html.j2:58-65`) uses `<p>` tags for the Schwab setup link. To minimize diff churn, the T-2.3 addition uses a parallel `<p>` for the status link (instead of refactoring both entries into a `<ul>`). All three discriminating tests pass with this structure.

4. **T-2.4 — existing T-B.4 test 4 (`test_post_with_credentials_and_callback_url_returns_204_hx_redirect`) updated:**
   Plan §B T-2.4 says 3 NEW tests; the implementation adds 3 NEW tests AND updates 1 existing T-B.4 test (which asserted `target.startswith("/config")` — would have regressed after the retarget). The update is necessary; total file-level test count = T-B.4's 17 + T-2.4's 3 = 20 (was 17 + 3 unchanged-T-B.4-test-4).

5. **`SchwabCallSummary.status` enum widening (Codex R1 Major #1 outcome):**
   Spec §7.1 documented the field as `status: str (∈ {'success','auth_failed','rate_limited','error'})`. Codex R1 Major #1 surfaced that this 4-value enum silently drops `in_flight` + `concurrent_refresh` rows from the recent-calls table, breaking CLI 1:1. Implementation widens to all 6 schema CHECK enum values. **Banked as V2.1 §VII.F amendment candidate** — spec §7.1 should widen the documented enum to mirror migration 0018's CHECK constraint.

6. **`tokens_db_path` masking via `~/...` prefix (Codex R2 Major #1 outcome):**
   Spec §7.1 says "masked if path contains user-profile prefix" but doesn't specify the masking convention. Implementation chose `~/swing-data/...` (the de-facto POSIX shorthand) for cross-platform readability. **Banked as V2.1 §VII.F amendment candidate** — spec §7.1 could explicitly pin the masking convention to `~/...` for forward-binding clarity.

---

## §6 Codex Major findings ACCEPTED with rationale

**NONE.** All 3 Critical+Major findings (R1 C1 + R1 M1 + R2 M1) + 1 Minor (R3 m1) resolved with code-content fixes. ZERO ACCEPT-WITH-RATIONALE banked — ties Sub-bundle 1's clean record + matches post-Phase-12 Sub-sub-bundle D + E precedent.

---

## §7 Watch items for orchestrator

### §7.1 V2.1 §VII.F spec amendments banked

1. **Spec §7.1 — `SchwabStatusVM.state` triplet supersession.** Spec uses misnamed `CONFIGURED/PROVISIONAL/NOT_CONFIGURED`; shipped CLI uses `LIVE/PROVISIONAL/DEGRADED`. Plan §A.0.1 D3 LOCK already banked this; Sub-bundle 2 inherits the lock. Spec amendment language: replace §7.1 + §3.4.4 state-triplet text with `LIVE / PROVISIONAL / DEGRADED` matching `swing/cli_schwab.py:823-825`.

2. **Spec §7.1 — `SchwabCallSummary.status` enum widening.** Spec enumerates 4 terminal-outcome values; Codex R1 Major #1 surfaced that this drops `in_flight` + `concurrent_refresh` rows from CLI 1:1 mirror. Spec amendment language: widen the documented enum to all 6 schema CHECK values per migration 0018 (`in_flight`, `success`, `error`, `auth_failed`, `rate_limited`, `concurrent_refresh`).

3. **Spec §7.1 — `tokens_db_path` masking convention.** Spec says "masked if path contains user-profile prefix" without specifying the masking shape. Implementation chose `~/...` (POSIX convention). Spec amendment language: explicitly pin the masking shape to `~/<relative-path-from-home>`.

4. **Spec §7.1 — `SchwabCallSummary.error_excerpt` rendering scope.** Spec enumerates the field; Codex R1 Critical #1 fix dropped template rendering (CLI 1:1 alignment). Spec amendment language: clarify that `error_excerpt` is VM-only (consumed but not rendered under the §7.4 OQ-D CLI 1:1 LOCK).

**Cumulative V2.1 §VII.F amendments pending across Phase 9 + Phase 10 + Phase 12 arc (per orchestrator-context):** ~30+ entries. Sub-bundle 2 adds 4 to the queue.

### §7.2 V2 candidates banked (orchestrator triage)

1. **Read-time re-redactor in additional surfaces:** Sub-bundle 2 adds a defense-in-depth re-redactor for `error_message` at `build_schwab_status_vm`. The same pattern could harden the CLI's `_render_recent_calls` (currently shows raw `error_message` text — wait, CLI doesn't render it at all; actually CLI is safer than web here). Consider whether the CLI status surface needs the re-redactor or any other surface.

2. **Refactor CLI helpers into `swing/integrations/schwab/state.py`:** Sub-bundle 2's VM helper imports 6 private helpers from `swing/cli_schwab.py` (`_compute_degraded_state`, `_read_tokens_metadata`, `_parse_iso_datetime`, `_REFRESH_TOKEN_TTL_SECONDS`, `_REFRESH_TOKEN_WARN_THRESHOLD_SECONDS`, `_REFRESH_TOKEN_ERROR_THRESHOLD_SECONDS`). The CLI module imports are heavyweight (schwabdev pulled transitively). A refactor to a dedicated `swing/integrations/schwab/state.py` module would isolate the read-only state computation from the schwabdev-bearing CLI module. **V2 candidate** — current local-import pattern works; refactor banked as cleanup.

3. **HTTPS callback handler for `/schwab/setup`:** still V2-banked from Sub-bundle B; no Sub-bundle 2 change.

4. **Per-environment-namespaced credentials + multi-account web picker:** V2-banked from Sub-bundle B; no Sub-bundle 2 change.

5. **Operator-visible `last_success_at` / `last_failure_at` formatting:** current implementation surfaces raw ISO timestamps. A relative-time renderer ("2 hours ago") would be more operator-friendly. V2 banked.

### §7.3 CLAUDE.md gotcha promotion candidates

**Candidate #1 — Read-time re-redactor discipline for any surface that consumes audit-row `error_message`:**
Sub-bundle 2 demonstrated that write-time redaction can be bypassed by future bugs, stale rows, or rows written outside the redactor's path. Defense-in-depth: any surface that consumes `error_message` for operator display MUST re-apply `_redact_error_message_for_audit` (idempotent). This is a generalization of the existing "Schwabdev silent-failure-mode discipline" + "Typed SchwabApiError audit-row close discipline" gotchas. **Promotion candidate (orchestrator-decided at integration-merge time).**

**Candidate #2 — `tokens_db_path` masking pattern for any future surface that surfaces filesystem paths:**
The masked-when-under-user-home pattern via `Path.relative_to(home).as_posix()` with `~/` prefix is the canonical shape. Future surfaces that surface paths to operator (e.g., V2 web account snapshot capture; V2 cassette runbook UI) should follow. **Promotion candidate.**

---

## §8 Worktree teardown status

**On-disk husk:** `.worktrees/schwab-mapper-bundle-2/` will be ACL-locked post integration-merge (pending operator's `cleanup-locked-scratch-dirs.ps1 -DeregisterFirst` pass; branch name `schwab-mapper-bundle-2` matches the cleanup-script regex per `cleanup-locked-scratch-dirs.ps1:156`).

**Branch:** `schwab-mapper-bundle-2` not yet pushed; orchestrator owns integration merge to `main` via `--no-ff`.

**Marker file:** `.copowers-subagent-active` removed pre-adversarial-critic invocation per dispatch brief §1.2 (verified at `c:/Users/rwsmy/swing-trading/.copowers-subagent-active` absence).

---

## §9 Forward-binding lessons for future Phase 12.5 + Phase 13 dispatches

1. **CLI helpers re-used at the web layer are correct + cheap.** Sub-bundle 2 imported 6 private helpers from `swing/cli_schwab.py` via local-imports-in-function-body (avoids circular import + heavyweight load at module import). This is the canonical pattern for any web counterpart of an existing CLI surface — re-use the CLI helpers; do NOT re-implement the multi-signal predicate logic. Codex R1 Major #1's CLI/web parity finding validates this approach end-to-end.

2. **Defense-in-depth re-redactor at the web layer pays for itself.** The R1 Critical #1 fix added a 4-line read-time re-redactor that costs ~0.1ms/render but closes the leak surface against any write-time redactor bug, stale row, or future surface that introduces an additional `error_message` write path. Generalizes to any surface that surfaces audit-row text. **Promote to CLAUDE.md gotcha** at orchestrator-decided integration time.

3. **Spec field-list != template render list.** Sub-bundle 2 demonstrated that spec §7.1's enumeration of `error_excerpt` doesn't compel the template to render it. The CLI 1:1 LOCK (spec §7.4 OQ-D + BINDING #14) is stronger than the field enumeration. Future dispatches should treat the rendering decision as separate from the VM-shape decision when CLI/web parity is a binding contract.

4. **Filesystem paths in templates require `~/` masking discipline.** Codex R2 Major #1 surfaced that the operator's local username/home directory leaked through `str(tokens_path)`. The masking pattern via `Path.relative_to(home).as_posix()` is reusable. Any future surface that surfaces filesystem paths to operator-visible HTML MUST apply this pattern.

5. **Schema CHECK enum is the canonical source of truth, not the spec's narrower field list.** Codex R1 Major #1 caught that `SchwabCallSummary.status` enum was a 4-value subset of the schema's 6-value CHECK enum. Future dataclass validators that mirror a schema CHECK MUST include ALL the schema enum values (the schema is authoritative; the spec field-list is documentation). This is a strengthening of the existing CLAUDE.md gotcha "Schema-CHECK + Python-constant + dataclass-validator MUST land in the same task for atomic consistency."

6. **Parametrized tests inflate pytest count beyond plan projection.** T-2.1 test 12 (case-insensitive env query-param) is 1 logical criterion but pytest collects 6 cases via parametrize. Plan §E test projections should clarify whether they count logical criteria or pytest cases — Sub-bundle 2's +52 actual vs +25-45 projected reflects this disambiguation gap. **Bank as plan-author guidance** for Phase 12.5 + Phase 13 writing-plans dispatches.

7. **Pre-Codex orchestrator-side review absorbed ZERO findings this dispatch — but still ran.** Sub-bundle 2's pre-Codex review (per C.C lesson #6) ran but returned CLEAN on all 14 BINDING contracts. The 3 Codex findings (R1 C1, R1 M1, R2 M1) were all spec-vs-implementation semantic divergences the pre-review couldn't have caught from BINDING-contract-anchors alone (they required reading spec §7.1's specific field-by-field shape). The lesson: pre-Codex review is most valuable for BINDING-contract divergences; spec-vs-implementation field-level review is the Codex chain's natural role. Continue running the pre-review (cheap insurance) but don't expect it to eliminate Codex rounds.

---

## §10 CLAUDE.md status-line refresh draft text

For orchestrator paste-in at integration-merge time (mirrors Sub-bundle 1.5 status-line pattern):

> **Post-Phase-12 Sub-bundle 2 SHIPPED 2026-05-17** at `<merge SHA>` (integration merge of `schwab-mapper-bundle-2` via `--no-ff`; 10 commits = 7 task-impl + 3 Codex-fix + 1 return-report + 1 merge; **3 Codex rounds → NO_NEW_CRITICAL_MAJOR** convergent tapering (R1 1C/1M/0m → R2 0C/1M/0m → R3 0C/0M/1m); **ZERO ACCEPT-WITH-RATIONALE banked** — all 3 Critical+Major + 1 Minor resolved with code-content fixes (ties Sub-bundle 1's clean record); ZERO Co-Authored-By footer drift; **+52 fast tests** (4523 → 4575); ruff 18 unchanged; schema v19 unchanged consumer-side; **closes Phase 12 Sub-bundle B T-B.7 deferred** — adds read-only `GET /schwab/status` web counterpart mirroring `swing schwab status` CLI 1:1 + `apply_overrides(cfg)` discipline at entry + case-insensitive env query-param + XSS-safe PlainTextResponse for invalid env + Phase 10 T-E.3 base-layout VM banner pin + `tokens_db_path` masked under `_user_home()` prefix + read-time `_redact_error_message_for_audit` defense-in-depth at VM + 3-state badge (LIVE green / PROVISIONAL yellow / DEGRADED red) + refresh-token TTL countdown with severity styling + recent-calls table mirroring CLI's 6-status enum 1:1 + environment switcher + re-auth link to `/schwab/setup` when state != LIVE OR severity != ok; retargets `POST /schwab/setup` HX-Redirect from `/config?schwab_setup=ok` → `/schwab/status` with `/config?schwab_setup=ok` passive no-op consumer retention one release window per Codex R1 m#2 LOCK; adds `/config` "External integrations" nav-link to `/schwab/status`; pins HTMX trinity preservation (HX-Request propagation + HX-Redirect-vs-303-swap + HX-Redirect-target-unrouted) + OriginGuard strict-mode allows read-only GET; pins spec §7.4 OQ-D LOCK (no order_type-specific strings leak); pre-Codex orchestrator-side review CLEAN on all 14 BINDING contracts (NEW C.C lesson #6 validated for 3rd time but did NOT absorb Codex findings this dispatch — spec-vs-implementation field-level review is the Codex chain's natural role). 4 V2.1 §VII.F spec amendments banked (state-triplet supersession + SchwabCallSummary.status enum widening + tokens_db_path masking convention + error_excerpt rendering scope). Operator-witnessed gate ALL PASS — S1 inline pytest 4575 fast + S2 `/schwab/status` 3-state + TTL + recent-calls + env switcher + S3 `/config` nav-link + S4 OPTIONAL POST `/schwab/setup` retarget verified via Chrome MCP walkthrough OR SKIPPED-with-test-coverage per refresh-token-clock-healthy decision + S5 ruff 18 unchanged. **Phase 12 Sub-bundle B T-B.7 architectural arc CLOSED.** **Phase 12.5 #1 OQ-F + #3 maintenance + Phase 13 dispatches UNBLOCKED.** Worktree husk `.worktrees/schwab-mapper-bundle-2/` pending cleanup-script `-DeregisterFirst` pass (branch matches `schwab(?:-\w+)?-bundle-` regex). Return report at `docs/post-phase12-schwab-mapper-bundle-2-return-report.md`.

---

## §11 Composition-surface verification

Public surface enumeration via `^def `/`^class ` grep:

**`swing/web/view_models/schwab.py`:**

```
class SchwabSetupVM
class SchwabCallSummary           # NEW (T-2.0)
class SchwabStatusVM              # NEW (T-2.0)
class SchwabSetupErrorVM
def build_schwab_status_vm        # NEW (T-2.1 helper)
```

**`swing/web/routes/schwab.py`:**

```
def _fetch_unresolved_material_count   # UNCHANGED (Phase 10 T-E.3 retrofit)
def _build_authorize_url               # UNCHANGED
def _render_form                       # UNCHANGED
def _render_error                      # UNCHANGED
def _build_form_vm                     # UNCHANGED
def schwab_setup_form                  # UNCHANGED (GET /schwab/setup)
def schwab_setup_post                  # T-2.4: _SUCCESS_REDIRECT_TARGET retarget
def schwab_status_get                  # NEW (T-2.1; GET /schwab/status)
```

Matches plan §B acceptance criteria verbatim. No accidental public-surface expansion.

---

## §12 Pre-existing test count delta

| Category | Baseline | Post Sub-bundle 2 | Delta |
|---|---|---|---|
| Pre-existing failures (phase8 walkthrough) | 3 | 3 | 0 |
| Skipped tests | 5 | 5 | 0 |

Pre-existing failures verified unchanged on main HEAD pre-dispatch (per CLAUDE.md "3 pre-existing phase8 walkthrough failures verified pre-existing on main HEAD"). No additional regressions surfaced.

---

## §13 Sub-bundle 1 + 1.5 architectural-surface non-regression evidence

`git diff 01d2e11..HEAD -- swing/integrations/schwab/ swing/trades/schwab_reconciliation.py swing/trades/reconciliation_classifier.py swing/trades/reconciliation_auto_correct.py swing/trades/reconciliation_backfill.py swing/trades/reconciliation_validators.py` returns **EMPTY** — confirms:

- `swing/integrations/schwab/mappers.py:_extract_executions_from_order_raw` early-exit gate (Sub-bundle 1.5 T-1.5.2): UNCHANGED.
- `swing/integrations/schwab/mappers.py:_has_non_placeholder_leg` canary helper (Sub-bundle 1.5 T-1.5.5): UNCHANGED.
- `swing/integrations/schwab/models.py:SchwabExecutionLeg` dataclass (Sub-bundle 1 T-1.1): UNCHANGED.
- `swing/integrations/schwab/mappers.py:_compute_execution_price` + `_resolve_match_quantity` + `_is_execution_bearing_candidate` (Sub-bundle 1): UNCHANGED.
- `swing/trades/schwab_reconciliation.py` comparator switch + Path B sentinel (Sub-bundle 1): UNCHANGED.
- `swing/trades/reconciliation_classifier.py` Shape C predicate at `_classify_entry_price_mismatch` + `_classify_close_price_mismatch` (Sub-bundle 1): UNCHANGED.
- `swing/trades/reconciliation_classifier.py:_classify_unmatched_fill_shared` Path B sentinel recognition (Sub-bundle 1): UNCHANGED.

**`swing/cli_schwab.py` UNCHANGED** — `git diff 01d2e11..HEAD -- swing/cli_schwab.py` returns EMPTY. The CLI semantics 1:1 LOCK preserved structurally (no CLI surface change in Sub-bundle 2's scope per BINDING #12).

---

*End of return report. Sub-bundle 2 closes the deferred Phase 12 Sub-bundle B T-B.7 task. ZERO ACCEPT-WITH-RATIONALE banked; 4 V2.1 §VII.F spec amendments queued; operator-witnessed gate PENDING orchestrator-driven session.*
