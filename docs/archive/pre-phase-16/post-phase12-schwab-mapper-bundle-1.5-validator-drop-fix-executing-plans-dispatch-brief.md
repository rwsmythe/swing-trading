# Post-Phase-12 Sub-bundle 1.5 — Schwab mapper validator-drop fix (production-shape diagnostic + targeted fix) — Executing-plans Dispatch Brief

**Audience:** Fresh Claude Code instance with no prior conversation context.

**Mission:** Diagnose + fix the Sub-bundle 1 validator-drop defect that prevented V2 mapper execution-grain widening from firing on production data. Sub-bundle 1 shipped 2026-05-17 at `120c992` PASS-WITH-FINDING: 6 E2E tests passed (3 cassette + 3 hand-rolled), but at S3 production gate ALL 18 production orders had `orderActivityCollection[0].executionLegs[0]` uniformly rejected by `SchwabExecutionLeg.__post_init__` (mapper drop+warn). Architectural fix HELD in negative sense (zero false-positives; reconciliation_run #13 clean) but positive lift NEVER FIRED. Root cause unknown without raw Schwab response shape — `schwab_api_calls` does NOT capture `response_body_json`.

**Expected duration (calibrated 3-5x per `feedback_time_estimates_overstated.md`):** ~3-5 hr implementation + ~1-2 hr Codex convergence + ~30 min operator-paired gate. Total **~1-1.5 days operator-paced**. Focused defect fix; smaller scope than Sub-bundle 1's architectural arc.

**Skill posture:**
- Invoke `copowers:executing-plans` against THIS brief as the plan (no separate spec/plan; brief is self-contained per handoff §3.2 + post-Phase-12 Sub-bundle 1 precedent of compact follow-up dispatches).
- Adversarial review runs after all tasks land. Expected **2-4 Codex rounds** (focused defect fix; matches Phase 12 Sub-sub-bundle C.A 2 rounds + C.C 3 rounds for similar tightly-scoped surfaces).

---

## §0 Inputs

### §0.1 Defect summary

**Failure mode** (from Sub-bundle 1 S3 gate 2026-05-17):
- Production `python -m swing.cli schwab fetch --orders` invoked from worktree (per `feedback_worktree_cli_invocation.md`).
- Emitted reconciliation_run #13 (state=completed; discrepancies_emitted=2; tier1_applied_count=0; tier2_pending_count=2).
- All 18 production orders logged the warning at `swing/integrations/schwab/mappers.py:392-397`:
  ```
  map_orders_to_fill_candidates: order <id> activity[0].executionLegs[0] failed validator (ValueError); dropping leg
  ```
- ZERO false-positive `entry_price_mismatch` / `close_price_mismatch` (architectural fix holds in negative sense).
- `executions=None` collapse fell through to comparator Path B → `unmatched_open_fill` with `execution_unavailable=true` sentinel → classifier emitted tier-2 `unsupported`.

**Root-cause hypothesis space** (unknown without raw shape):
- **(H1)** Schwab production responses omit one of `price` / `quantity` (mapper at `mappers.py:336-337` defaults to `0` via `.get("X", 0)` → validator rejects on `> 0` check).
- **(H2)** Schwab production responses emit `price` / `quantity` as `None` rather than absent (mapper coerces via `float(None)` → `TypeError` → caught by mapper's `except (ValueError, TypeError)` → drop+warn).
- **(H3)** Schwab production uses a different field name (e.g., `executionPrice` / `legPrice` / `executionQuantity`) on real-world orders vs the cassette + reference docs.
- **(H4)** Schwab production omits `time` on some leg shapes (pre-checked at `mappers.py:364` → drop+warn).
- **(H5)** Schwab production wraps leg values in nested objects (e.g., `{"value": 10.5, "currency": "USD"}`) — coercion via `float()` raises TypeError.
- **(H6)** Some other shape divergence not anticipated by current hypothesis space.

**Why hypothesis space matters:** the fix STRATEGY depends on which family is the actual cause:
- H1/H4 → mapper field-name alias OR explicit None-handling at extraction time.
- H2 → mapper pre-coercion None-check pre-empting validator coercion path.
- H3 → mapper extraction widening to consider field-name aliases.
- H5 → mapper nested-object unwrap at extraction time.
- H6 → unknown; STOP-and-recover (operator-architectural-pushback discipline).

**Reference data**:
- Cassette field shape (planted by Sub-bundle 1 T-1.0; verified 2026-05-17): `['instrumentId', 'legId', 'mismarkedQuantity', 'price', 'quantity', 'time']` per `tests/integrations/cassettes/schwab/test_e2e_limit_buy.yaml`.
- Mapper extraction field names: `legId` / `price` / `quantity` / `mismarkedQuantity` / `instrumentId` / `time` per `swing/integrations/schwab/mappers.py:335-340`.
- Validator constraint summary: `leg_id >= 0`; `price > 0` + finite + non-bool; `quantity > 0` + finite + non-bool; `mismarked_quantity >= 0` + finite OR None; `instrument_id >= 0` OR None; `time` non-empty str.

### §0.2 Sub-bundle 1.5 scope (4 tasks)

| Task | Title | Files (illustrative) |
|---|---|---|
| **T-1.5.1** | Diagnostic capture — write a one-shot Python script that authenticates against operator's production Schwab account, fetches orders via `Client.account_orders(...)`, captures **2-3 representative raw JSON order shapes** (specifically containing `orderActivityCollection[].executionLegs[]`) to a local-only temp file, and surfaces field-name + value-shape divergences from cassette. Token redaction MUST follow Sub-bundle 1 T-1.0 cassette sanitization discipline (scrub `accountHash` from URL paths; scrub `access_token` / `refresh_token` / `client_id` / `client_secret` from output). Script lives at `scripts/diagnose_schwab_executionlegs.py` (mirrors `scripts/record_schwab_cassettes.py` precedent). | NEW `scripts/diagnose_schwab_executionlegs.py` + NEW `tests/integrations/test_diagnose_executionlegs_script.py` |
| **T-1.5.2** | Fix — based on T-1.5.1 findings, amend the appropriate surface: mapper extraction at `_extract_executions_from_order_raw` (most likely candidate) OR `SchwabExecutionLeg.__post_init__` validator (least likely; preserve dataclass contract). Implementer picks based on diagnostic findings; document the fix-location choice in commit message + return report. If diagnostic surfaces a need for schema extension (H6 family), STOP + escalate to orchestrator BEFORE adding inline (per §0.5 #1 + post-Phase-12 Sub-bundle 1 lessons inheritance). | MODIFY `swing/integrations/schwab/mappers.py` OR `swing/integrations/schwab/models.py` (implementer picks 1 of 2; NOT both unless diagnostic surfaces multi-surface fix) |
| **T-1.5.3** | Regression test — synthetic fixture cassette OR hand-rolled `pytest`-driven test planting production-shape leg JSON byte-for-byte from T-1.5.1 diagnostic findings (sanitized for sensitive fields). Discriminating test: cassette under FIX produces `SchwabExecutionLeg` instance with correct field values; cassette under PRE-FIX produces validator-drop warning + `executions=None`. | NEW `tests/integrations/test_schwab_mapper_production_shape_regression.py` + OPTIONAL new cassette at `tests/integrations/cassettes/schwab/test_production_shape_*.yaml` (sanitized) |
| **T-1.5.4** | Re-verification — re-run `python -m swing.cli schwab fetch --orders` from worktree against operator's production DB; verify ZERO validator-drop warnings in stderr/log + reconciliation_run completes cleanly. **Acceptance criterion:** at MINIMUM no validator-drop warnings logged; IDEALLY `executions` field populated on at least 1 production order (positive-lift verification per orchestrator-context.md `Sub-bundle architectural fix can hold in negative sense...` lesson 2026-05-17). | No file changes; gate surface S3 evidence |

**Cross-bundle dependencies:** Sub-bundle 1.5 CONSUMES Sub-bundle 1's `SchwabExecutionLeg` dataclass + `_extract_executions_from_order_raw` mapper helper + `_compute_execution_price` / `_resolve_match_quantity` / `_is_execution_bearing_candidate` comparator helpers + Sub-bundle 1 T-1.0 cassette sanitization filter at `tests/conftest.py:vcr_config`. NO new helper functions; NO new dataclasses.

**Module boundaries (BINDING — preserve discipline)**:
- `swing/integrations/schwab/mappers.py`: defensive parsing extension at `_extract_executions_from_order_raw` only. NEVER raises on malformed leg; preserves coherence-check fallback. Fix MAY ADD field-name aliases OR None-handling OR nested-object unwrapping — implementer picks based on T-1.5.1 findings.
- `swing/integrations/schwab/models.py`: dataclass validator change ONLY if T-1.5.1 surfaces a Schwab-emitted shape that the V1 validator should now accept (e.g., zero-price legs documented by Schwab as legitimate). Preserve REAL-field discipline at `__post_init__`.
- `scripts/diagnose_schwab_executionlegs.py`: standalone diagnostic script (NEW). `argparse` CLI; `apply_overrides(cfg)` + `resolve_credentials_env_or_prompt(cfg, environment, allow_prompt=False)` + `construct_authenticated_client` 4-arg signature discipline preserved (writing-plans forward-binding lesson #1).
- `swing/trades/schwab_reconciliation.py`: **NOT TOUCHED** (Sub-bundle 1 shipped; comparator stays unchanged).
- `swing/trades/reconciliation_classifier.py`: **NOT TOUCHED** (Sub-bundle 1 shipped; classifier stays unchanged).

### §0.3 Project state at dispatch time

- **HEAD on `main`:** `78b45b9` (post-Sub-bundle-1 housekeeping + handoff brief; Sub-bundle 1 merged at `120c992`). Brief commit lands at HEAD+1 pre-dispatch.
- **Test count:** **~4479 fast passing on main** + 3 pre-existing phase8 walkthrough failures (unchanged since Phase 8) + 1 skipped. Verified inline at brief drafting time.
- **Ruff baseline:** **18** (E501 only; unchanged across Phase 11 + Phase 12 + Sub-bundle 1).
- **Schema version:** **v19** (LOCKED). **Sub-bundle 1.5 MUST NOT widen schema** (matches Sub-bundle 1 §0.5 #1 + §C.5 escalation rule; bank-after-write costs 2-3 cascade-cleanup rounds). If diagnostic surfaces a need for `response_body_json` audit capture, BANK as Sub-bundle 1.6 V2 candidate; do NOT add inline.
- **Production discrepancy state:** ZERO unresolved-material; banner count=0. 4 dispositioned correction chains preserved (correction_ids 11+12+13+14 — DHC+VSAT acknowledge entries).
- **Production refresh-token clock:** expires ~2026-05-22T17:05:00+00:00. **~5 days remaining at brief-draft time.** Operator may need to re-auth via `/schwab/setup` web form OR `swing schwab setup` CLI before T-1.5.1 diagnostic run if expired.
- **Production-write classifier soft-block awareness:** T-1.5.1 diagnostic + T-1.5.4 re-verification are production-API READS (audit-row writes count as production writes from classifier perspective). Operator pre-authorizes via gate-path AskUserQuestion OR plain-chat "yes" per invocation if classifier soft-blocks (Sub-bundle 1 brief §0.3 C.D-arc lesson #2 inheritance).
- **Worktree husks:** `.worktrees/schwab-mapper-bundle-1/` pending operator's `cleanup-locked-scratch-dirs.ps1 -DeregisterFirst` pass. NOT blocking.

### §0.4 Diagnostic phase strategy options (T-1.5.1)

Implementer chooses 1 of 3 paths for T-1.5.1; recommendation follows.

**Option A — RECOMMENDED — Standalone Python diagnostic script (`scripts/diagnose_schwab_executionlegs.py`).**

- Pattern mirror: `scripts/record_schwab_cassettes.py` (Sub-bundle 1 T-1.0 precedent at `e7c0e8d` family; check git log on `120c992` for exact SHA).
- Authenticates against production Schwab using Sub-bundle 1 T-1.0 + Sub-bundle B `apply_overrides(cfg)` + `resolve_credentials_env_or_prompt(cfg, 'production', allow_prompt=False)` + `construct_authenticated_client` 4-arg signature.
- Calls `Client.account_orders(...)` with same query window as `_step_schwab_orders` (last 30 days; `status='FILLED'`).
- Iterates response; for each order WITH `orderActivityCollection[].executionLegs[]`:
  - Pretty-print the FIRST leg's JSON shape (keys + value types + sample values).
  - Compare keys against `_EXPECTED_LEG_KEYS = frozenset({'legId', 'price', 'quantity', 'mismarkedQuantity', 'instrumentId', 'time'})`.
  - For each expected key: report present/missing/None/wrong-type.
  - For each unexpected key: report it.
- Writes redacted output to `~/swing-data/diagnose-schwab-executionlegs-<timestamp>.txt` (operator-local; never committed; `.gitignore` covers `swing-data/`).
- Token + accountHash redaction follows T-1.0 sentinel-leak audit discipline (3 NEW C.D-arc lessons family).
- **Pros:** zero schema change; reproducible; preserves Sub-bundle 1's audit-row discipline; commits are infrastructure-only (script + test); validator changes deferred until findings surface.
- **Cons:** requires Schwab API call (cost: 1 token-refresh + 1 orders call; no domain mutations).

**Option B — ALTERNATIVE — Temporary debug logging at mapper drop-point.**

- Extend `swing/integrations/schwab/mappers.py:392-397` drop-warn block to additionally log `_log.warning("activity[%d].executionLegs[%d] raw shape: %r", ai, li, leg_raw)`.
- Re-run `python -m swing.cli schwab fetch --orders` with `--verbose` flag OR set `SCHWAB_LOG_LEVEL=DEBUG` env var (per existing Sub-bundle A T-A.10 redaction discipline — `setLogRecordFactory` will scrub schwabdev-namespaced records but leg_raw is in `swing.integrations.schwab.mappers` namespace → NOT covered by the schwabdev redactor; verify leg dict carries no token-shaped values before committing the change).
- **Pros:** lightweight; reuses existing observability.
- **Cons:** requires running production fetch (more side-effecting than Option A); commits temporary debug code that must be removed in same dispatch (clean-up risk); leg_raw inspection requires re-running production fetch with debug enabled (less controlled than Option A).

**Option C — DEFERRED — Schema extension to capture `response_body_json`.**

- Add `schwab_api_calls.response_body_json TEXT NULL` column via migration `0020_*.sql`.
- Capture redacted response body at `record_call_finish` time.
- **Pros:** persistent observability for future Schwab API debugging.
- **Cons:** v19→v20 schema migration; backup-gate fire; multi-bundle architectural impact; orchestration of redaction discipline cost (~3-5 Codex rounds for full coverage). DEFERRED as Sub-bundle 1.6 V2 candidate; **DO NOT pursue in Sub-bundle 1.5**.

**Orchestrator recommendation:** **Option A.** Standalone script preserves Sub-bundle 1's infrastructure-only pattern; one-shot inspection cost is minimal; no schema change; no temporary debug code to clean up; reproducible for future Schwab API shape investigations. Implementer MAY choose Option B if pre-Codex review surfaces a strong rationale; document choice in T-1.5.1 commit message.

### §0.5 BINDING contracts (DO NOT re-litigate)

1. **Schema MUST stay at v19** (matches Sub-bundle 1 §0.5 #1). If T-1.5.1 surfaces a need for schema element, STOP + escalate to orchestrator BEFORE adding inline. Bank as Sub-bundle 1.6 V2 candidate (`response_body_json` audit-row capture).
2. **Sub-bundle 1 architectural surfaces UNCHANGED.** Comparator (`schwab_reconciliation.py`) + classifier (`reconciliation_classifier.py`) + helper functions (`_compute_execution_price` / `_resolve_match_quantity` / `_is_execution_bearing_candidate`) + Shape C predicate — all SHIPPED. T-1.5.2 fix is LOCALIZED to the mapper extraction surface (most likely) OR the dataclass validator (least likely). NEVER touch comparator/classifier within Sub-bundle 1.5 scope.
3. **Cassette + hand-rolled E2E tests UNCHANGED.** The 6 Sub-bundle 1 E2E tests at `tests/integration/test_phase12_post_schwab_mapper_widening_e2e.py` MUST still pass post-Sub-bundle-1.5 (regression suite preserves coverage). The T-1.5.3 regression test PLANTS the production shape; it is ADDITIVE.
4. **`stop_mismatch` path UNCHANGED** (Sub-bundle 1 §0.5 #14 inheritance; `_find_working_stop_for_ticker` untouched).
5. **Token redaction discipline (Sub-bundle 1 T-1.0 + Phase 11 Sub-bundle A T-A.10 inheritance).** T-1.5.1 diagnostic script's output to `~/swing-data/diagnose-schwab-executionlegs-*.txt` MUST scrub `accountHash` + `access_token` + `refresh_token` + `client_id` + `client_secret`. T-1.5.3 regression test fixture MUST also be sanitized if drawn from raw production response. Diagnostic script output file is NEVER committed (gitignored).
6. **`construct_authenticated_client` 4-arg signature BINDING** (Sub-bundle 1 §0.5 #12 inheritance). T-1.5.1 diagnostic script follows: `apply_overrides(cfg)` → `resolve_credentials_env_or_prompt(cfg, environment, allow_prompt=False)` → `construct_authenticated_client(...)`.
7. **NO Pass-2 LIFT widening** (Sub-bundle 1 §0.5 #2 + spec §1.5 + §6.6 OQ-F V2 LOCK inheritance). Sub-bundle 1.5 is a defect-fix dispatch; it does NOT extend classifier Pass-2 behavior beyond Path B sentinel recognition that Sub-bundle 1 already shipped.
8. **NO behavioral changes to non-touched surfaces** (matches Sub-bundle 1 §0.5 #14). Especially: Sub-bundle C.A schema UNCHANGED; Sub-bundle C.B Shape A + Shape B predicates UNCHANGED; Sub-bundle C.D banner predicate UNCHANGED; Sub-bundle 1 Shape C predicate UNCHANGED.
9. **`_extract_executions_from_order_raw` defensive-parsing contract preserved.** NEVER raise on malformed leg; preserve drop+warn + collapse-to-None fallback; preserve coherence-check (`sum(legs.quantity) == filledQuantity`). T-1.5.2 fix extends extraction permissiveness (field-name aliases, None-handling, nested-object unwrap) but MUST NOT remove the defensive fallback discipline.

### §0.6 Forward-binding lessons inherited (BINDING for Sub-bundle 1.5)

Per orchestrator-context.md §"Lessons captured" (4 NEW 2026-05-17 PM banked entries):

1. **Operator's "pause" means STOP all forward motion immediately.** If operator pauses Sub-bundle 1.5 mid-dispatch (e.g., during T-1.5.1 diagnostic findings review or T-1.5.4 re-verification), halt ALL forward action — even items appearing independently confirmed. Note any commits that landed pre-pause; offer revert; leave decision to operator.
2. **`python -m swing.cli` at worktree-side gates, NOT `swing`.** T-1.5.4 re-verification MUST use `python -m swing.cli schwab fetch --orders` from `cd .worktrees/schwab-mapper-bundle-1.5` cwd. `swing` console-script routes to editable-install path (main repo), NOT worktree code. Pytest works fine without prefix.
3. **Wall-clock duration estimates 3-5x too long.** Brief's "~1-1.5 days operator-paced" reflects calibration; do NOT pad further.
4. **Sub-bundle architectural fix can hold in negative sense while positive lift fails to fire.** T-1.5.4 acceptance MUST include explicit positive-lift verification (ideally `executions` populated on at least 1 production order). Without positive-lift verification, Sub-bundle 1.5 could ship without actually fixing the defect.

Plus Sub-bundle 1 + Phase 12 arc forward-binding lessons (BINDING):
- **Pre-Codex orchestrator-side review (C.C lesson #6).** Before invoking `copowers:adversarial-critic`, dispatch a focused reviewer subagent with brief §0.5 BINDING contracts as anchors; ask for a deviation list ≤300 words. Saved 1-2 Codex rounds on C.C + C.D + Sub-bundle 1.
- **Synthetic-fixture-vs-production-emitter shape drift family (C.D-arc lesson #2 + #4; Sub-bundle 1 finding).** Sub-bundle 1.5 IS the canonical example of this lesson family — cassette + hand-rolled fixtures planted by implementer didn't match production emitter shape. T-1.5.3 regression test MUST plant production-derived shape from T-1.5.1 findings byte-for-byte (sanitized for sensitive fields).
- **NO Co-Authored-By footer.** Phase 12 C.B precedent + post-Phase-12 brainstorm/writing-plans/Sub-bundle-1 chains ALL held the line via explicit citation in dispatch prompts. Pattern is durable. **DO NOT regress.**
- **Schwabdev silent-failure-mode discipline (Phase 11 Sub-bundle A T-A.0.b inheritance).** `Client.__init__()` + `Tokens.update_tokens()` print-and-return-silently on auth failure. T-1.5.1 diagnostic script MUST verify post-call state (`client.tokens.access_token` populated) before invoking API.

---

## §1 Worktree + binding conventions

### §1.1 Worktree

- **Branch:** `schwab-mapper-bundle-1.5` (matches cleanup-script regex `schwab(?:-\w+)?-bundle-` at `cleanup-locked-scratch-dirs.ps1:156`; verified post-merge cleanup will pick this up).
- **Worktree directory:** `.worktrees/schwab-mapper-bundle-1.5/`
- **BASELINE_SHA:** main HEAD at brief-commit time (resolve via `git rev-parse main` after this brief lands; expect `~78b45b9 + 1` for brief commit).

### §1.2 Marker-file workflow

- After worktree creation: `New-Item -ItemType File c:\Users\rwsmy\swing-trading\.copowers-subagent-active`
- After all 4 tasks land + tests GREEN + before invoking adversarial-critic: `Remove-Item c:\Users\rwsmy\swing-trading\.copowers-subagent-active`

### §1.3 Commits

- Conventional prefixes:
  - `feat(schwab-bundle-1.5-T-1.5.1): <description>` for diagnostic script + tests
  - `fix(schwab-bundle-1.5-T-1.5.2): <description>` for mapper or validator amendment
  - `test(schwab-bundle-1.5-T-1.5.3): <description>` for production-shape regression test
  - `fix(schwab-bundle-1.5): Codex RN <severity> #N — <description>` for Codex-driven fixes
- **NO Claude co-author footer.** This is a CLAUDE.md binding convention. Per Sub-bundle 1 + Phase 12 C.B precedent — do NOT add `Co-Authored-By: Claude Opus 4.7 (1M context) <noreply@anthropic.com>` (or any other Co-Authored-By footer attributing the AI assistant) to ANY commit message. C.C + C.D + post-Phase-12 brainstorm + writing-plans + Sub-bundle-1 chains' explicit citation produced ZERO footer drift across 23 + 33 + 6 + 2 + ~24 commits respectively — pattern is DURABLE. **This dispatch MUST NOT regress.**
- **NO `--no-verify`**, **NO `--amend`** (per CLAUDE.md binding conventions: prefer `git add <specific-files>` over `git add -A`).
- **TDD:** failing test first, minimal implementation, pass, commit (where applicable; T-1.5.1 is diagnostic-first so test follows script per script-precedent at `scripts/record_schwab_cassettes.py`).

### §1.4 Branch isolation + ownership

- Commits on branch only; no push to origin from worktree until Sub-bundle 1.5 integration commit.
- **Implementer (you) owns:** TDD commits → operator-paired diagnostic session for T-1.5.1 (script run; findings review) → T-1.5.2 fix decision + commit → T-1.5.3 regression test → pre-Codex review (C.C lesson #6) → adversarial-critic → return report.
- **Operator owns:** diagnostic-script run against production (T-1.5.1) + witnessed verification gate (§3 surfaces below — 5 surfaces).
- **Orchestrator owns:** integration merge to main + post-merge housekeeping + Sub-bundle 2 dispatch commissioning (per `feedback_orchestrator_performs_merge.md`).

### §1.5 Verify command

PowerShell from inside worktree:

```powershell
git log --oneline HEAD~10..HEAD
python -m pytest -m "not slow" -q
python -m pytest tests/integrations/test_schwab_mapper_production_shape_regression.py -v
python -m pytest tests/integrations/test_diagnose_executionlegs_script.py -v
ruff check swing/ --statistics
python -c "from swing.integrations.schwab.models import SchwabExecutionLeg, SchwabOrderResponse; print('models OK')"
python -c "from swing.integrations.schwab.mappers import _extract_executions_from_order_raw; print('mapper helper OK')"
python scripts/diagnose_schwab_executionlegs.py --help
```

---

## §2 Adversarial review (Codex)

Invoked automatically by `copowers:executing-plans` after all 4 tasks land + tests GREEN + after the pre-Codex orchestrator-side review (C.C lesson #6 — implementer MUST do an explicit dispatched-reviewer-subagent pass BEFORE invoking adversarial-critic).

**Expected chain shape:** 2-4 substantive Codex rounds (focused defect fix; matches Phase 12 Sub-sub-bundle C.A 2 rounds + Sub-bundle B reconciliation depth's tightly-scoped follow-ups).

**Adversarial review watch items (Sub-bundle 1.5-specific):**

1. **T-1.5.2 fix is LOCALIZED.** Comparator + classifier + helper functions UNCHANGED (§0.5 #2). Codex verifies no behavioral drift in `swing/trades/schwab_reconciliation.py` + `swing/trades/reconciliation_classifier.py`.
2. **Sub-bundle 1 E2E tests still PASS** (§0.5 #3). The 6 tests at `tests/integration/test_phase12_post_schwab_mapper_widening_e2e.py` must remain GREEN — Sub-bundle 1.5 is ADDITIVE coverage, not REPLACEMENT.
3. **Defensive-parsing contract preserved** (§0.5 #9). `_extract_executions_from_order_raw` NEVER raises on malformed leg; preserves drop+warn + collapse-to-None fallback; preserves coherence-check. Discriminating test: planted MALFORMED leg shape → mapper drops + warns + returns `executions=None` (NOT raises).
4. **Token redaction at T-1.5.1 script output** (§0.5 #5). Sentinel-leak audit pattern: plant non-token-shaped sentinels at all 5 long-lived slots in a mock client; run script; grep output file; assert ZERO matches.
5. **`construct_authenticated_client` 4-arg signature at T-1.5.1** (§0.5 #6). T-1.5.1 script MUST follow: `apply_overrides(cfg)` → `resolve_credentials_env_or_prompt(...)` → `construct_authenticated_client(...)`. Discriminating test asserting cascade-resolved values threaded through.
6. **Schwabdev silent-failure check at T-1.5.1** (§0.6 inheritance). Script verifies `client.tokens.access_token` populated post-`update_tokens()` call before invoking `account_orders(...)`.
7. **Regression-test arithmetic distinguishes pre-fix from post-fix** (per `feedback_regression_test_arithmetic.md`). T-1.5.3 regression test MUST fail under PRE-FIX mapper code AND pass under POST-FIX mapper code. Verify by running test against the BASELINE_SHA mapper version (Codex round can request a temporary git-stash + checkout to confirm).
8. **Schema additions during executing-plans cycle (C.A return report lesson #7 + Sub-bundle 1 inheritance).** If diagnostic surfaces a need for schema element NOT in plan, implementer MUST STOP + escalate to orchestrator BEFORE adding inline. Cost of bank-after-write: 2-3 cascade-cleanup rounds.
9. **Synthetic-fixture-vs-production-emitter shape drift pre-emption (C.D + Sub-bundle 1 lesson family).** T-1.5.3 regression test plants production-derived shape byte-for-byte from T-1.5.1 findings (sanitized). NOT hand-rolled from spec.
10. **Windows cp1252 stdout encoder pre-emption (C.D gate-fix #1+#3 family).** T-1.5.1 script + diagnostic output MUST NOT contain non-ASCII glyphs (`§`/`→`/etc.). Use ASCII-only output OR rely on `swing/cli.py` entry's UTF-8 stdout reconfigure as defense-in-depth (which the diagnostic script also inherits when invoked via `python -m`).

---

## §3 Operator-witnessed verification gate (Sub-bundle 1.5 integration — 5 surfaces)

| Surface | Type | Acceptance |
|---|---|---|
| **S1** | Inline `pytest -m "not slow" -q -n auto` | GREEN at ~4490-4510 fast tests (worktree-side; +10-30 net from 4479 baseline). 3 pre-existing phase8 walkthrough failures unchanged; 1 skipped. |
| **S2** | T-1.5.3 production-shape regression test PASS | `pytest tests/integrations/test_schwab_mapper_production_shape_regression.py -v` confirms the discriminating test fires correctly — fixture under FIX produces `SchwabExecutionLeg` instance; fixture under PRE-FIX produces validator-drop warning + `executions=None`. |
| **S3** | `python -m swing.cli schwab fetch --orders` (worktree-side) against operator's production DB | **PRODUCTION RE-VERIFICATION** (operator pre-authorizes per C.D-arc lesson #2 if classifier soft-blocks). Expected: ZERO validator-drop warnings in stderr/log. **POSITIVE-LIFT criterion (per orchestrator-context.md `Sub-bundle architectural fix can hold in negative sense...` lesson 2026-05-17):** at MINIMUM no validator-drop warnings; IDEALLY `executions` field populated on at least 1 production order (verify via post-run SELECT against `schwab_api_calls` or via inline Python REPL inspection of mapper output). |
| **S4** | Phase 10 dashboard banner count=0 | `python -m swing.cli web --port 8081` worktree-side OR production state inspection. Banner count UNCHANGED at 0 (production state remains clean). |
| **S5** | `ruff check swing/ --statistics` | Reports 18 E501 unchanged. |

**Gate session budget:** 5 surfaces. Short-haul operator-paired session. Operator-paired-gate driving — ONE COMMAND AT A TIME on production writes; inline-batched OK on reads/tests (per durable preference).

**Production-write classifier soft-block awareness at S3:** the production fetch is a production-write from Claude Code's classifier perspective (audit-row writes count). Operator pre-authorizes via gate-path AskUserQuestion OR plain-chat "yes" per invocation if classifier soft-blocks. **EXPECT BLOCKS PER-INVOCATION** per C.D-arc lesson #2.

**Production state post-gate:** ZERO unresolved-material discrepancies preserved; banner count=0 preserved. **Production state CLEAN.** Positive lift fires on at least 1 production order (acceptance criterion).

**S3 fallback if positive lift does NOT fire:** if T-1.5.4 re-verification surfaces ZERO validator-drop warnings BUT also ZERO orders with `executions` populated (e.g., no FILLED multi-leg orders in the 30-day window), the gate STILL PASSES on the negative-sense criterion. Banked as Sub-bundle 1.5 follow-up V2 candidate: extend verification to test against a synthetic order corpus OR wait for operator's next live trade to surface production-shape execution legs in `schwab_api_calls`.

---

## §4 OUT OF SCOPE (do not do)

- **Schema additions or migrations** — §0.5 #1. If T-1.5.1 surfaces a need for `response_body_json` audit-row capture, STOP + escalate to orchestrator; BANK as Sub-bundle 1.6 V2 candidate. Do NOT add inline.
- **Comparator changes** (`swing/trades/schwab_reconciliation.py`) — §0.5 #2. Sub-bundle 1 shipped. Touch zero.
- **Classifier changes** (`swing/trades/reconciliation_classifier.py`) — §0.5 #2. Sub-bundle 1 shipped. Touch zero.
- **`_compute_execution_price` / `_resolve_match_quantity` / `_is_execution_bearing_candidate` helper changes** — §0.5 #2. Sub-bundle 1 shipped. Touch zero.
- **Pass-2 LIFT** — §0.5 #7. Sub-bundle 1.5 is a defect fix; does NOT extend classifier Pass-2 behavior beyond Path B sentinel recognition shipped in Sub-bundle 1.
- **OQ-F multi-leg tier-1 auto-redirect** — Phase 12.5 #1 scope.
- **Per-row `engine_version` metadata column** — Sub-bundle 1 §4 V2 candidate.
- **Web Tier-2 discrepancy-resolution surface** — Phase 12.5 #2 scope.
- **Removal of Sub-bundle 1 cassettes** — §0.5 #3. Sub-bundle 1 cassettes remain in test corpus; T-1.5.3 fixture is ADDITIVE.
- **Sub-bundle 2 work** — `/schwab/status` web counterpart is Sub-bundle 2 scope; separate executing-plans dispatch after Sub-bundle 1.5 ships.
- **Behavioral changes to non-touched surfaces** — §0.5 #8. Especially: `stop_mismatch` UNCHANGED; Sub-bundle C.A schema UNCHANGED; Sub-bundle C.B Shape A + Shape B predicates UNCHANGED; Sub-bundle C.D banner predicate UNCHANGED; Sub-bundle 1 Shape C predicate UNCHANGED.
- **Re-litigating Sub-bundle 1 binding contracts** — accepted as given. Operator-locked at `120c992`.
- **Touching the `~/swing-data/diagnose-schwab-executionlegs-*.txt` operator-local file from any committed code path** — local-only artifact; never committed; never read by application code.

---

## §5 Return report shape

After all 4 tasks land + Codex chain converges + before final return-report commit, draft a return report at `docs/post-phase12-schwab-mapper-bundle-1.5-return-report.md` (mirroring `docs/post-phase12-schwab-mapper-bundle-1-return-report.md` shape):

1. Final HEAD on branch + commit count breakdown (4 task-impl + N Codex-fix + 1 return-report).
2. Codex round chain (R1-RN summary table + convergent shape; finding-count taper).
3. Test count delta + ruff baseline delta + schema version delta (v19 unchanged).
4. Operator-witnessed verification surfaces (PENDING orchestrator-driven gate; 5 surfaces).
5. **Diagnostic findings (T-1.5.1 summary)** — which hypothesis from §0.1 H1-H6 surfaced; raw field-name + value-shape divergence; redacted leg sample (NEVER raw `accountHash` / tokens).
6. **Fix-location choice (T-1.5.2)** — mapper extraction widening OR validator amendment; rationale.
7. Per-task deviations from brief (if any) with rationale.
8. Codex Major findings ACCEPTED with rationale (if any). Brief expectation: ZERO ACCEPT-WITH-RATIONALE (matches Sub-bundle 1 + Phase 12 C.B + C.C + C.D + post-Phase-12 brainstorm/writing-plans precedent).
9. Watch items for orchestrator (V2 candidates surfaced; particularly: `response_body_json` audit-row capture banked as Sub-bundle 1.6 candidate if diagnostic phase surfaced strong rationale for persistent observability).
10. Worktree teardown status.
11. Forward-binding lessons for future Sub-bundle 2 dispatch + Phase 12.5 #1 OQ-F auto-redirect dispatch.
12. CLAUDE.md status-line refresh draft text for orchestrator paste-in at integration-merge time.
13. Composition-surface verification: `^def ` grep on `swing/integrations/schwab/mappers.py` + `swing/integrations/schwab/models.py` confirming public surface UNCHANGED except for T-1.5.2 amendment scope.
14. **Positive-lift verification evidence** — at S3 gate, confirm `executions` populated on at least 1 production order (or document why no eligible inputs available in 30-day window + banked as follow-up V2 candidate).
15. Pre-existing test count delta (3 phase8 walkthrough + 1 skipped should remain unchanged).
16. Sub-bundle 1 architectural-surface non-regression evidence (no changes to `_compute_execution_price` / `_resolve_match_quantity` / `_is_execution_bearing_candidate` / Shape C predicate / Path B sentinel recognition).

---

## §6 Dispatch metadata

- **Subagent type:** `general-purpose` (full tool surface needed).
- **Foreground vs background:** foreground (default).
- **Worktree:** YES — per §1.1.
- **Model:** defer to harness default.
- **Expected duration:** ~3-5 hr implementation + ~1-2 hr Codex + 5-surface operator-witnessed gate. Total **~1-1.5 days operator-paced** per calibrated estimate.

---

## §7 If you get stuck

- If T-1.5.1 diagnostic findings reveal hypothesis H6 (unanticipated shape divergence beyond H1-H5), **STOP + escalate to orchestrator** per operator-architectural-pushback STOP-and-recover discipline (C.D-arc lesson #1; validated again at Sub-bundle 1 S3 gate).
- If T-1.5.1 surfaces a need for schema element (e.g., `response_body_json` capture), **STOP + escalate** (§0.5 #1; bank as Sub-bundle 1.6 V2 candidate).
- If T-1.5.1 production Schwab API call returns an empty `executionLegs[]` for ALL FILLED orders in the 30-day window (e.g., operator's last 30 days had no leg-bearing executions), **EXTEND window to 60-90 days** OR **propose mocking the shape** as a fallback (mock-only fallback was NOT-elected at spec §6.5 OQ-E LOCK, but defect-fix dispatch may justify deviation — escalate to orchestrator first).
- If Codex pushes back on the diagnostic-script standalone-scope LOCK (e.g., "in-test debug logging is simpler..."), HOLD THE LINE — the LOCK is §0.4 Option A recommendation; standalone script preserves Sub-bundle 1 T-1.0 precedent + avoids temporary debug code to clean up.
- If Codex pushes back on the regression-test production-shape pin (e.g., "spec-derived shape is sufficient..."), HOLD THE LINE — synthetic-fixture-vs-production-emitter shape drift IS the canonical defect-family Sub-bundle 1.5 closes; spec-derived shape is exactly what FAILED at Sub-bundle 1 S3 gate.
- If Codex pushes back on the schema-extension OUT-OF-SCOPE LOCK at T-1.5.1 (e.g., "persistent observability is operationally important..."), HOLD THE LINE — bank as Sub-bundle 1.6 V2 candidate; do NOT pursue inline in Sub-bundle 1.5.
- If you encounter a Phase 11/12/Sub-bundle-1 lesson that conflicts with a Sub-bundle 1.5 implementation proposal, the prior-phase lesson wins (validated by ship-experience). Surface the conflict as a constraint.
- If the production refresh-token clock has expired (`~2026-05-22T17:05`), operator re-auths via `/schwab/setup` web form OR `swing schwab setup` CLI; Sub-bundle B T-A.2 self-healing means recovery is one CLI/web invocation.
- DO NOT propose new classifier sub-classifiers within Sub-bundle 1.5 scope (§4 lock).
- DO NOT propose web surface within Sub-bundle 1.5 scope (§4 lock; Phase 12.5 #2 V2 candidate).
- DO NOT propose schema additions within Sub-bundle 1.5 scope (§4 lock; lesson #7 family).
- DO NOT add `Co-Authored-By` footer to any commit message (per §1.3 + Sub-bundle 1 + Phase 12 C.B precedent of ZERO drift across ~80+ commits; do NOT regress).
- **Pre-Codex orchestrator-side review (C.C lesson #6)**: before invoking `copowers:adversarial-critic`, dispatch a focused reviewer subagent with brief §0.5 BINDING contracts as anchors; ask for a deviation list ≤300 words. Cheap; absorbed LOCK divergences pre-Codex; saved 1-2 Codex rounds on C.C + C.D + Sub-bundle 1. Apply explicitly here.

---

## §8 Operator-paired gate notes

Sub-bundle 1.5's 5-surface gate is small (smaller than Sub-bundle 1's 9-surface arc; matches Phase 12 Sub-sub-bundle C.A's tightly-scoped sub-bundle gates). Plan for a brief operator-paired session:

- **No mid-dispatch operator pause expected** (unlike Sub-bundle 1's cassette session). T-1.5.1 diagnostic script CAN be run by operator independently after T-1.5.1 commit + commit-ready commit-hash sent to operator; OR by implementer if operator is paired and authorizes the production-API call inline.
- **Production refresh-token clock** — expires ~2026-05-22; verify TTL > 1hr at T-1.5.1 + T-1.5.4 production-call pre-checks; operator re-auths via `/schwab/setup` web form OR `swing schwab setup` CLI if needed.
- **Production-write classifier soft-block** — T-1.5.1 + T-1.5.4 are production-API reads + audit-row writes; operator pre-authorizes via gate-path AskUserQuestion OR plain-chat "yes" PER INVOCATION (C.D-arc lesson #2).
- **One command at a time** — per operator preference (handoff brief §0 LOCK + durable preference); orchestrator/implementer sends ONE command per turn, waits for output, verifies, sends next.
- **Worktree-side CLI invocation** — S3 + S4 + diagnostic-script call MUST use `python -m swing.cli ...` form (NOT `swing ...`) per `feedback_worktree_cli_invocation.md`. Pytest works fine without prefix.
- **Operator-architectural-pushback STOP-and-recover** — if T-1.5.1 surfaces architectural divergences (H6 family) OR T-1.5.4 re-verification still emits validator-drop warnings, STOP, investigate, recover (C.D-arc lesson #1). NOT push-through.
- **Pause-means-pause discipline** — if operator pauses mid-dispatch for any reason, halt ALL forward action (`feedback_pause_means_pause.md`).

---

*End of brief. Sub-bundle 1.5 executing-plans dispatch — focused validator-drop defect fix. Branch `schwab-mapper-bundle-1.5` matches cleanup-script regex. Schema unchanged (v19); architectural surfaces from Sub-bundle 1 untouched; 4 tasks T-1.5.1..T-1.5.4 with diagnostic-first sequencing; CLAUDE.md `Pass-2-tier-1-FORBIDDEN` gotcha unchanged (Sub-bundle 1 amendment preserved as-shipped). Expected duration ~1-1.5 days operator-paced including 5-surface operator-witnessed gate.*
