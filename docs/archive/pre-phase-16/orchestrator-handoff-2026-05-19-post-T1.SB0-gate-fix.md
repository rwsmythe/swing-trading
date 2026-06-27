# Orchestrator handoff — 2026-05-19 (post-T1.SB0-gate-fix; S3 PASS; T2.SB1 ∥ T3.SB1 commissioning UNBLOCKED)

You are taking over as orchestrator for the Swing Trading project at the **post-Phase-13-T1.SB0-gate-fix + S3-PASS + T2.SB1/T3.SB1-commissioning-UNBLOCKED** breakpoint. Outgoing orchestrator handed off due to context-window pressure ahead of the remaining 9 Phase 13 sub-bundles (T2.SB1 + T3.SB1 + T2.SB2/SB3/SB4/SB5 + T3.SB2/SB3 + T2.SB6 + T4.SB).

**main HEAD AT HANDOFF**: `d772f23` (T1.SB0 gate-fix merge; S3 PASS post-merge via operator-paired session).

**WORKING DIRECTORY**: `c:\Users\rwsmy\swing-trading`

**CRITICAL FIRST TASK**: T1.SB0 gate-fix post-merge housekeeping (see §2 of this brief). NOT YET COMMITTED.

---

## §0 ⚠ Critical bootstrap framing

**Memory entries inherited (all BINDING; load-bearing across recent handoffs)**:
- `feedback_pause_means_pause.md` — when operator says pause, STOP all forward motion immediately.
- `feedback_worktree_cli_invocation.md` — `python -m swing.cli` from worktree cwd, NOT bare `swing`.
- `feedback_time_estimates_overstated.md` — orchestrator wall-clock estimates 3-5x too long; divide by 3-5x for operator-paced.
- `feedback_orchestrator_qa_implementer_product.md` — orchestrator MUST QA every implementer product before merge; verify against reality on disk; don't merely summarize self-report. **BINDING** (validated 12x cumulatively across Phase 12/12.5/13 arcs).
- `feedback_orchestrator_performs_merge.md` — merge + push + post-merge housekeeping = orchestrator action; do NOT ask "shall I merge".
- `feedback_orchestrator_vs_implementer_execution.md` — default to implementer-dispatch for context budget; QA can also be subagent-dispatched.
- `feedback_always_provide_inline_dispatch_prompt.md` — every brief gets an inline dispatch prompt as fenced code block.
- `feedback_commit_brief_before_inline_prompt.md` — commit the brief BEFORE providing inline prompt.
- `feedback_regression_test_arithmetic.md` — when specifying tests in orchestrator briefs, compute values under both pre-fix and post-fix paths to confirm the test distinguishes.

**Operator dispatches implementers themselves** (durable). Orchestrator drafts brief + provides inline dispatch prompt as fenced code block.

**NO Claude co-author footer.** Cumulative streak **~211+ commits ZERO trailer drift** across Phase 11/12/12.5/13 chains. Pattern is DURABLE. DO NOT regress. Explicit citation in commit messages required:

> Per fresh forward-binding lesson #7 (Phase 12 Sub-sub-bundle C.B 2026-05-15): do NOT add `Co-Authored-By: Claude Opus 4.7 (1M context) <noreply@anthropic.com>` (or any other Co-Authored-By footer attributing the AI assistant) to ANY commit message.

**Pre-Codex orchestrator-side review (C.C lesson #6) — BINDING.** Before invoking `copowers:adversarial-critic` in any executing-plans/writing-plans/brainstorm dispatch, dispatch a focused reviewer subagent with binding contracts as anchors; ask for deviation list ≤300 words. **Validated 12x cumulatively** as of 2026-05-18 (Phase 12 brainstorm/writing-plans + Phase 12.5 #1/#2/#3 brainstorms + Phase 13 brainstorm/writing-plans + Phase 13 T1.SB0 + Phase 13 T1.SB0 gate-fix).

**Size-check trigger discipline** at `docs/orchestrator-context.md` §"Maintenance: retention discipline" §"Size-check trigger at housekeeping-commit time" (added 2026-05-18 PM via CLAUDE.md evaluator pass Option B2 restructure). Soft thresholds:
- CLAUDE.md line 3: >2,000 chars → trim back.
- orchestrator-context.md "Prior state" sub-sections: >10 retained → archive oldest.
- orchestrator-context.md "Lessons captured": >40 entries → migrate oldest 5-10.
- phase3e-todo.md SHIPPED entries: >25 retained → archive-split.

---

## §1 Read these in order

1. **This brief end-to-end** — captures T1.SB0 gate-fix closure outcome + Phase 13 forward dispatch readiness state.

2. **`docs/phase13-t1-sb0-gate-fix-recon.md`** (232 lines) — implementer's empirical T-GF1 recon. Especially §1 (side-by-side DataFrame inspection of operator's real CVGI archive) + §2 (root cause file:line evidence: Schwab `price_history` minute-default footgun at `_bars_hook` → `fetch_window_via_ladder` → `get_price_history` → `client.price_history(symbol)` with NO kwargs → API defaults to (day, 10, minute, 1) = 10 days of 1-minute bars) + §3 (why T1.SB0 + Phase 11 Sub-bundle C R1 M#5 deferral comment missed this; CLI verify path was already explicit) + §4 (fix shape D: additive backward-compatible kwargs).

3. **`docs/phase13-t1-sb0-gate-fix-return-report.md`** (168 lines) — gate-fix return report. 3 Codex rounds; ZERO Critical + ZERO Major entire chain; 6 minors (4 resolved + 2 banked V2-F).

4. **`docs/phase3e-todo.md`** top entries — current SHIPPED ledger; will need new entry for T1.SB0 gate-fix SHIPPED at the housekeeping commit YOU draft.

5. **`docs/orchestrator-context.md`** §"Currently in-flight work" + §"Lessons captured" + §"Maintenance: retention discipline" (especially §"Size-check trigger at housekeeping-commit time").

6. **`CLAUDE.md`** — project conventions + gotchas. **Especially the 2 new gotchas added 2026-05-18 PM at `dc0cfea`**:
   - Session-anchor inequality discipline (forward-looking `>=` vs backward-looking `>` strict).
   - Hook fallback window-completeness (return full archive; consumers slice).

7. **`docs/phase13-t2-sb1-executing-plans-dispatch-brief.md`** (267 lines; already COMMITTED at `4a52f3a`) — ready-to-commission for T2.SB1.

8. **`docs/phase13-t3-sb1-executing-plans-dispatch-brief.md`** (258 lines; already COMMITTED at `4a52f3a`) — ready-to-commission for T3.SB1 (branches off T2.SB1's T-A.1.1 first-commit SHA per OQ-12 Option E).

9. **`docs/superpowers/plans/2026-05-18-phase13-charts-patterns-autofill-usability-plan.md`** (2810 lines) — Phase 13 plan. Especially §G.1 + §G.2 for T2.SB1 + T3.SB1 per-task structure.

10. **`docs/superpowers/specs/2026-05-18-phase13-charts-patterns-autofill-usability-design.md`** (1483 lines) — Phase 13 brainstorm spec. Reference; consumed by plan.

---

## §2 ⚠ FIRST TASK — T1.SB0 gate-fix post-merge housekeeping (NOT YET COMMITTED)

The gate-fix merge `d772f23` is live; the post-merge housekeeping commit is your FIRST task. Operator approved 2 deferred CLAUDE.md gotcha additions to land in this housekeeping commit per operator decision 2026-05-18 PM (originally deferred pending S3 PASS; S3 has now PASSED).

### §2.1 Housekeeping deliverables

**A. CLAUDE.md line 3 refresh** (size-checked under 2,000 chars per discipline):
- Update HEAD reference from `d772f23` (CURRENT correct).
- Mention T1.SB0 gate-fix SHIPPED + S3 PASS.
- Mention T2.SB1 ∥ T3.SB1 concurrent dispatch UNBLOCKED.
- Mention 2 new CLAUDE.md gotchas added (Schwab minute-default footgun + byte-parity-test insufficiency).

**B. CLAUDE.md gotchas section: ADD 2 new entries**:

**Gotcha #1 — Schwab `price_history` minute-default footgun**:
> **Schwab `price_history` API defaults to `(periodType=day, period=10, frequencyType=minute, frequency=1)` when called without explicit kwargs — returning 10 DAYS OF 1-MINUTE INTRADAY BARS (~2730-3900 candles), NOT daily bars.** Lesson surfaced 2026-05-19 at Phase 13 T1.SB0 gate-fix T-GF1 recon. Pre-Phase-13, `_bars_hook` did not invoke the ladder; T1.SB0 wired `_step_charts` through OhlcvCache.get_or_fetch → ladder → `get_price_history` → `client.price_history(symbol)` WITHOUT kwargs. The Schwab API server-side defaults silently delivered minute bars. The mapper at `swing/integrations/schwab/mappers.py:817-828` converts each minute candle to OhlcvBar with date-only `asof_date`; `write_window`'s `drop_duplicates(subset=['asof_date'], keep='last')` silently overwrote daily Shape A archive content with the last-minute-of-day intraday bar. Operator's CVGI.schwab_api.parquet had 2780 rows across only 10 unique dates (~278 minute-bars per date) instead of expected ~1260 daily bars. Chart rendered 2780 candles compressed into 10 x-positions with "00:00" time-of-day labels + raw-shares volume scale. **The CLI verify path at `swing/cli_schwab.py:1100-1111` ALREADY passes `period_type='month', period=1, frequency_type='daily', frequency=1` explicitly — proving architectural intent IS daily bars.** Fix: any Schwab Market Data API consumer that wants DAILY bars MUST explicitly pass `(year, N, daily, 1)` or `(month, N, daily, 1)` kwargs. **Pre-empt in any new Schwab API consumer** (T3.SB1 + T3.SB2 entry/exit auto-fill paths inherit this discipline; writing-plans §5 watch item): enumerate the period_type + period + frequency_type + frequency kwargs explicitly in every `client.price_history(...)` invocation; discriminating test pattern — assert kwargs are passed via `inspect.signature` or mock-verification.

**Gotcha #2 — Byte-parity-test-as-algorithmic-substitute insufficiency**:
> **Byte-parity test as algorithmic substitute for operator-visual gate is INSUFFICIENT when test fixtures bypass production data-derivation paths.** Lesson surfaced 2026-05-19 at Phase 13 T1.SB0 gate-fix post-mortem. The chart-bytes byte-parity test `tests/pipeline/test_chart_bytes_parity_through_ohlcv_cache.py::test_chart_bytes_match_between_ohlcv_cache_and_legacy_price_fetcher` was cited as "STRONG algorithmic substitute" for the S3 visual gate during T1.SB0 pre-merge orchestrator-side QA. The test passed but missed the Schwab minute-default footgun regression because BOTH test paths consume IDENTICAL stub fixtures via `monkeypatch.setattr("swing.web.ohlcv_cache.read_or_fetch_archive", _stub_read)` — exercising the bare `read_or_fetch_archive` branch ONLY. The ladder path is never invoked. Both paths trivially produce byte-identical PNGs from the same fixture data. **The test asserts "given identical inputs, identical outputs" — but the regression is in HOW INPUTS ARE DERIVED.** Same gotcha family as synthetic-fixture-vs-production-emitter shape drift (Phase 12 C.D + Phase 12.5 #2 + Phase 12.5 Q2) — except the failure mode here is FETCH SEMANTICS drift, not envelope shape drift. **Pre-empt in any new wiring change that touches production data-derivation**: production-path regression tests that exercise the actual wiring (NOT fixture-seeded equality between two paths); discriminating-test pattern — plant production-shape state that triggers the wiring's divergence + assert the new behavior + assert this test FAILS pre-fix when reverting the wiring locally. **NEVER characterize an algorithmic substitute as "STRONG" for visual gates without verifying the algorithmic test exercises the production data-derivation path.**

**C. phase3e-todo.md** — new top entry for T1.SB0 gate-fix SHIPPED at `d772f23` (~80-100 lines covering Codex chain shape + ZERO ACCEPT preserved + actual root cause + auto-recovery posture + 2 gotcha additions + V2-F + PL fallback diagnostic V2 candidates).

**D. orchestrator-context.md §"Currently in-flight work"** — current-state pointer refresh:
- New current state: Phase 13 T1.SB0 gate-fix SHIPPED + S3 PASS + housekeeping complete + T2.SB1 ∥ T3.SB1 commissioning UNBLOCKED.
- Demote previous current state (Phase 13 T1.SB0 SHIPPED) to "Prior state" sub-section.
- **Size-check triggers**: Prior state count was 10 AT cap PRE-this-housekeeping; new demote brings to 11 → archive oldest (whichever was at line 142 region) to `docs/orchestrator-context-archive.md`.

**E. phase3e-todo.md V2 candidates banked** (2 new):
- **V2-F Shape A archive cleanup helper** (from gate-fix return report) — operator-paced; explicit cleanup utility for contaminated Shape A archives beyond the conditional auto-recovery.
- **PL fallback diagnostic logging** (NEW; surfaced 2026-05-19 at S2 post-gate-fix) — `fetch_window_via_ladder: unexpected error from T-C.1 wrapper for PL; falling back to yfinance` is generic; needs Schwab response code + body excerpt for diagnosability. Operator-paced; could fold into Theme 4 usability triage at T4.SB.

### §2.2 Size-check pre-flight (per discipline)

Current counts (before YOUR housekeeping):
- CLAUDE.md line 3: 1,878 chars (will tip toward threshold with adds + line 3 refresh; trim discipline applies).
- orchestrator-context.md Prior state: 10 (AT cap; YOUR housekeeping demote brings to 11 → archive trigger fires).
- Lessons captured: 17 (well under 40 threshold).
- phase3e-todo.md SHIPPED entries: ~10 (well under 25 threshold).

### §2.3 Sample structure for the housekeeping commit message

Per recent precedent (`bf8d214` Phase 13 writing-plans housekeeping + `dc0cfea` T1.SB0 housekeeping):
- Heading: `docs(housekeeping): Phase 13 T1.SB0 gate-fix SHIPPED post-merge + 2 NEW CLAUDE.md gotchas + orchestrator-context.md archive-split per size-check trigger`
- Body covers: gate-fix sub-summary + new gotchas description + housekeeping deliverables enumerated + size-check post-flight stats + streaks preserved.

---

## §3 Phase 13 dispatch readiness (post-housekeeping)

### §3.1 T2.SB1 + T3.SB1 concurrent dispatch UNBLOCKED

Both dispatch briefs are ALREADY committed at `4a52f3a`:
- `docs/phase13-t2-sb1-executing-plans-dispatch-brief.md` (267 lines)
- `docs/phase13-t3-sb1-executing-plans-dispatch-brief.md` (258 lines)

**Inline implementer-dispatch prompts** for both were provided in the prior session (search the conversation transcript at the operator's discretion OR regenerate per `feedback_always_provide_inline_dispatch_prompt.md`). Standard prompt format:
- Brief path + plan path
- Worktree branch + branch base (T2.SB1 from main HEAD; T3.SB1 from T2.SB1's T-A.1.1 first-commit SHA per OQ-12 Option E)
- Standard convention citations (NO Co-Authored-By footer; ~211+ streak; `python -m swing.cli` worktree-side; ASCII-only; pre-Codex BINDING; etc.)
- Read-first list
- Steps + Do NOT items

### §3.2 OQ-12 Option E concurrency mechanic (CRITICAL)

T2.SB1's T-A.1.1 is **MIGRATION-ONLY commit** (v20 atomic landing per spec §3 + plan §B.4). T-A.1.1b lands NEW repo CRUD SEPARATELY.

**T3.SB1's worktree branches FROM T2.SB1's T-A.1.1 first-commit SHA** (NOT from main HEAD). Operator records the SHA when T2.SB1 implementer reports T-A.1.1 landed; relays to T3.SB1 implementer at dispatch time.

Merge ordering: T2.SB1 merges first; T3.SB1 second.

### §3.3 Pre-Codex orchestrator-side review expected validations

- T2.SB1: **13th** cumulative C.C lesson #6 validation expected.
- T3.SB1: **14th** cumulative C.C lesson #6 validation expected (or 13th if dispatched before T2.SB1 closes).

### §3.4 Remaining sub-bundles post-T2.SB1+T3.SB1

Per plan §H.1 dispatch sequence (8 more sub-bundles after T2.SB1+T3.SB1):
- T2.SB2 (6 tasks; foundation primitives)
- T2.SB3 (9 tasks; detectors batch 1: VCP + flat base + cup-with-handle)
- T3.SB2 (5 tasks; exit auto-fill; sequenced after T2.SB3)
- T2.SB4 (7 tasks; detectors batch 2: HTF + DBW)
- T2.SB5 (6 tasks; template matching DTW + 120s benchmark gate)
- T3.SB3 (5 tasks; review auto-fill; consumes OhlcvCache patterns)
- T2.SB6 (7 tasks; closed-loop surface + Theme 1 annotated charts)
- T4.SB (7 tasks; usability triage + Q4 close-tracking flag closer)

Phase 13 close projection: ~5500-5940 fast tests; +4 slow E2E.

---

## §4 Cumulative streaks to preserve

- **ZERO Co-Authored-By footer trailer drift**: ~211+ commits cumulative. ABSOLUTELY DO NOT regress. Explicit citation in dispatch prompts is the discipline.
- **ZERO ACCEPT-WITH-RATIONALE in Phase 13 arc except T1.SB0's 2 TECHNICALLY SOUND banks** (R1 M#1 OHLCV scope-clarification + R1 M#2 V2-A breaker non-participation). Both sound per QA review.
- **Schema v19 UNCHANGED**. v20 lands at T2.SB1 task T-A.1.1 (migration-only commit per OQ-12 Option E).
- **Baseline 4924 → 4939 fast** (+15 cumulative across T1.SB0 + gate-fix) / 0 ruff E501 / production ZERO open discrepancies.
- **12x cumulative C.C lesson #6 validation**: pattern is durably effective. CONTINUE applying.
- **Pre-Codex orchestrator-side review BINDING**: 13th + 14th validations expected for T2.SB1 + T3.SB1.

---

## §5 Operator-pending items (NOT orchestrator-blocking)

- Worktree husks pending operator's `cleanup-locked-scratch-dirs.ps1 -DeregisterFirst` pass (phase13-brainstorm + phase13-writing-plans + phase13-t1-sb0-ohlcv-charts-wiring + phase13-t1-sb0-gate-fix).
- Untracked `scripts/convert_books_pdf_to_md.py` (carried since session start; operator-decision-pending; not blocking).
- Schwab refresh-token clock — operator runs `swing schwab status --environment production` to check; renew via `/schwab/setup` web if expired (~7-day rolling clock).
- Auto-recovery of operator's contaminated `CVGI.schwab_api.parquet` happened automatically on the post-gate-fix pipeline run (verify if needed via `python -c "import pandas as pd; df = pd.read_parquet('C:/Users/rwsmy/swing-data/prices-cache/CVGI.schwab_api.parquet'); print(f'Rows: {len(df)}; Unique dates: {df[\"asof_date\"].nunique()}')"` — target: matches `cfg.archive.archive_history_days = 1260`).

---

## §6 Suggested first session flow

1. Read this brief + recon + return report + orchestrator-context current-state + Phase 13 plan §G.1+§G.2 + 2 dispatch briefs end-to-end.

2. **Execute the housekeeping commit** (§2 of this brief). This is your first deliverable. Single commit covering 4 files (CLAUDE.md + orchestrator-context.md + orchestrator-context-archive.md + phase3e-todo.md) + push to main.

3. **Run bootstrap verification post-housekeeping**:
   ```powershell
   git log --oneline -10                        # expect post-housekeeping HEAD
   git status                                   # expect clean
   python -m pytest -m "not slow" -q -n auto | tail -5   # expect 4939 fast + 0 fail
   ruff check swing/ --statistics | tail -3     # expect 0 errors
   python -c "from swing.data.db import EXPECTED_SCHEMA_VERSION; print(EXPECTED_SCHEMA_VERSION)"   # expect 19
   ```

4. **Commission T2.SB1**: regenerate or pull from conversation transcript the inline implementer-dispatch prompt for T2.SB1 (worktree branch `phase13-t2-sb1-dev-time-labeling-infra` from main HEAD post-housekeeping). Operator triggers dispatch.

5. **Await T2.SB1 implementer's report of T-A.1.1 first-commit SHA** — relay to T3.SB1 dispatch when T3.SB1 commissions.

6. **Commission T3.SB1** (after T-A.1.1 SHA recorded): inline prompt with T-A.1.1 SHA filled in (worktree branches off SHA, NOT main HEAD per OQ-12 Option E).

7. **Concurrent QA reviews** as both implementers return. Standard QA discipline per `feedback_orchestrator_qa_implementer_product.md`.

8. **Sequential merges**: T2.SB1 merges first; T3.SB1 merges second. Post-merge housekeeping after EACH merge (size-check pre-flight; rolling archive-split as Prior state count tips).

9. **Loop through 8 remaining sub-bundles** per plan §H.1 sequence.

---

## §7 Do NOT

- Re-litigate Phase 13 brainstorm + writing-plans + T1.SB0 + T1.SB0 gate-fix outcomes (ALL SHIPPED + merged + verified).
- Re-litigate T1.SB0's 2 banked ACCEPT-WITH-RATIONALE designs (R1 M#1 + R1 M#2 SOUND; preserved by gate-fix; do NOT touch).
- Add Co-Authored-By footer to ANY commit (CLAUDE.md binding convention; ~211+ streak).
- Skip pre-Codex orchestrator-side review at any dispatch (C.C lesson #6 BINDING; 13th+14th validations expected).
- Run new production-write actions without explicit operator pre-authorization.
- Commission T3.SB1 before T2.SB1's T-A.1.1 first-commit SHA is recorded (OQ-12 Option E branch-base discipline).
- Bundle T-A.1.1 with T-A.1.1b in T2.SB1 (migration-only commit boundary BINDING per OQ-12 Option E + Codex R1 M#1 + R2 M#2 closure from writing-plans).

---

## §8 Forward-binding lessons surfaced this session (1 NEW orchestrator-side)

1. **Hypotheses framed at brief-drafting time should be EXPLICITLY MARKED as hypotheses requiring verification, not prescriptions** (orchestrator-side; surfaced at T1.SB0 gate-fix). My brief §1.2 said "implementer VERIFIES + may revise" — that discipline worked; the implementer correctly treated brief §1.2 as a hypothesis to falsify, not a prescription. My pre-T-GF1 hypothesis (weekly-refresh + archive_history_days semantic divergence) was FALSIFIED by empirical T-GF1 recon. The actual defect was at a completely different code surface (Schwab API ladder minute-default kwargs). Pattern for future briefs: when framing a hypothesis based on abstract precedent (like the Phase 11 deferral comment), explicitly flag it as orchestrator-best-guess + require empirical verification BEFORE fix-shape commitment.

---

*End of handoff brief. Post-T1.SB0-gate-fix orchestrator transition. T2.SB1 + T3.SB1 concurrent dispatch UNBLOCKED post-housekeeping. ~211+ cumulative ZERO Co-Authored-By footer drift streak preserved. Production state clean (ZERO open discrepancies; baseline 4939 fast / 0 ruff E501 / schema v19). Operator-paced.*
