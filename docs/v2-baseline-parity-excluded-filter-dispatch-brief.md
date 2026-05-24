# V2 OHLCV Baseline-Parity Excluded-Filter Fix — Dispatch Brief

**Audience:** Fresh Claude Code instance dispatched as the V2 baseline-parity excluded-filter implementer. No prior conversation context.

**Mission:** Implement the **Option A fix LOCKED** by the DHC/UCO/VSAT × 60-64 CRITERION DRIFT investigation: filter persisted `bucket='excluded'` (+ defensively `bucket='error'`) candidates from V2's `_compute_baseline_parity` apples-to-apples comparison; optionally filter from per-variable drill-down. Then re-run V2 smoke to verify Tier-1 FULL PASS (DK:62 already resolved by D.1 Shape A refresh; this fix resolves the 15 DHC/UCO/VSAT × 60-64 false positives).

**Workflow:** `superpowers:test-driven-development` skill (TDD; test-first → impl → commit per TDD slice). Optionally invoke `copowers:executing-plans` for Codex MCP adversarial review given gotcha #25 is BINDING for 34th cumulative C.C lesson #6 validation; operator-paired choice — invoke Codex if the bucket='error' extension OR drill-down filter scope expands beyond the literal 1-line locked fix.

**Branch:** `applied-research-v2-baseline-parity-excluded-filter` — branches from main HEAD `8330e50` (or later).

**Worktree:** `git worktree add .worktrees/applied-research-v2-baseline-parity-excluded-filter applied-research-v2-baseline-parity-excluded-filter`. Work from that cwd; invoke `python -m swing.cli` (NOT bare `swing`).

**Expected duration:** ~1-3 hours operator-paced (small fix; TDD slice discipline; small Codex chain if invoked).

---

## §0 Read first

1. **`docs/v2-dhc-uco-vsat-drift-investigation-2026-05-24.md`** (post-merge at `d7cdd51`) — PRIMARY SUBSTRATE. Especially §0 TL;DR + §1.5 H5 root cause + §5 remediation Option A. The investigation is the source-of-truth for what to fix + why + the discriminating-test pattern.

2. **`docs/v2-dhc-uco-vsat-drift-investigation-return-report.md`** — return report; V2 candidates banked at §"V2 candidates banked": (1) Option A filter for `'excluded'` (THIS FIX); (2) extend to `bucket='error'`; (3) optionally filter excluded candidates from per-variable drill-down; (4) NEW CLAUDE.md gotcha #25 already banked at housekeeping `8330e50`.

3. **`research/harness/aplus_v2_ohlcv_evaluator/sweep.py`** lines 540-605 — `_compute_baseline_parity` function (the target).

4. **`swing/pipeline/runner.py`** lines 1105-1141 — V1's short-circuit reference (writes `Candidate(bucket='excluded', criteria=(), notes='open position'|'ETF/fund blocklist', ...)` directly; what V2 needs to match).

5. **`swing/evaluation/scoring.py`** (`bucket_for`) — returns ONLY `{aplus, watch, skip}` (NEVER `'excluded'` or `'error'`); confirms why V2 naive recompute will never match V1 persisted sentinel buckets.

6. **CLAUDE.md gotcha #25** (sentinel-bucket parity-comparison discipline; appended at housekeeping `8330e50`) — BINDING. The discriminating-test pattern in gotcha #25 directly informs THIS fix's test design.

7. **`exports/diagnostics/aplus-sensitivity-v2-20260524T162641Z.md`** — pre-fix smoke artifact showing the 15 false-positive tier-1 drift entries (DHC/UCO/VSAT × 60-64).

8. **CLAUDE.md** gotchas #1-#25 — cumulative discipline (24 prior + #25 from yesterday's housekeeping).

---

## §1 Scope (3 fixes + 1 verification re-run)

### §1.1 Fix #1 (CORE; LOCKED): filter `bucket='excluded'` from baseline-parity comparison

Location: `research/harness/aplus_v2_ohlcv_evaluator/sweep.py:540-605` (`_compute_baseline_parity`).

Change: 1-line filter at the per-candidate iteration boundary:
```python
if cand_row.persisted_bucket == "excluded":
    continue
```

Place BEFORE the V2 `evaluate_one(ctx)` invocation so V2 doesn't waste cycles computing buckets for candidates V1 pre-empted.

### §1.2 Fix #2 (DEFENSIVE; same scope as Fix #1): extend filter to `bucket='error'`

Same location. Same pattern. Reason: `bucket='error'` is another sentinel V1 may write (evaluation-failure path); same parity-comparison-discipline failure mode. Defense-in-depth — if V1 ever writes `bucket='error'`, V2 won't drift on those either.

Implementation: change Fix #1 condition to `if cand_row.persisted_bucket in {"excluded", "error"}:`. ~Same 1-line change.

### §1.3 Fix #3 (DEFENSIVE; optional): filter excluded candidates from per-variable drill-down

If per-variable drill-down (the `_record_flip` path or equivalent) is currently invoked on excluded candidates, exclude them there too. Investigation §5 banked this as optional; verify whether the drill-down currently records flips for excluded candidates (would produce noise; same parity gap). If so, mirror the filter.

### §1.4 Verification (POST-FIX): re-run V2 smoke + confirm Tier-1 FULL PASS

```
python -m swing.cli diagnose aplus-sensitivity-v2 \
  --db "$USERPROFILE/swing-data/swing.db" \
  --eval-runs 5 \
  --max-runtime-seconds 120
```

Expected outcome:
- CRITERION DRIFT DETECTED section DISAPPEARS (no entries) OR reports "Tier-1 match: PASS"
- 15 DHC/UCO/VSAT × 60-64 entries no longer present
- DK:62 already resolved by D.1 (verified in `exports/diagnostics/aplus-sensitivity-v2-20260524T162641Z.md` baseline)
- Tier-2 should remain at clean 10/0 (unchanged by this fix)
- Smoke artifact written to `exports/diagnostics/aplus-sensitivity-v2-<NEW-timestamp>.{csv,md}`

Commit the post-fix smoke artifact alongside the test commits for traceability per pre-D.1 + post-D.1 smoke artifact precedents.

---

## §2 Discriminating tests (per gotcha #25 BINDING pattern)

At least 3 tests required:

1. **Synthetic excluded candidate plant**: plant a synthetic `candidate_criteria` row with `persisted_bucket='excluded'`; invoke `_compute_baseline_parity`; assert the candidate is NOT counted in `tier1_mismatch_keys` (Fix #1 verification).

2. **Synthetic error candidate plant**: plant a synthetic `candidate_criteria` row with `persisted_bucket='error'`; invoke `_compute_baseline_parity`; assert NOT counted in `tier1_mismatch_keys` (Fix #2 verification).

3. **Negative control**: plant a synthetic `candidate_criteria` row with `persisted_bucket='skip'` that genuinely should be tier-1 (e.g., real per-criterion divergence); assert IS counted in `tier1_mismatch_keys`. Discriminates the filter from "always skip" semantics.

If Fix #3 lands, add a 4th test for the drill-down filter (synthetic excluded candidate → drill-down does NOT record a flip for it).

---

## §3 Watch items + cumulative discipline (BINDING)

### §3.1 Cumulative discipline (25 gotchas; pre-Codex 7-expansion + 5 NEW refinements + 2 NEW sub-refinements + 3 NEW sub-promotions)

If Codex MCP review invoked, ALL 25 gotchas BINDING for 34th cumulative C.C lesson #6 validation. **ESPECIALLY relevant to this fix**:
- **#25** — sentinel-bucket parity-comparison discipline (just banked; THIS fix is its first implementation; discriminating-test pattern verbatim from gotcha)
- **#21** — Expansion #13 cumulative regression cascade audit; the filter is in `_compute_baseline_parity` which the Codex R1.M2 + R3.M1 + R4.M1 cascade already restructured; apply "imagined Codex next-round" audit before merging
- **#22** — per-counter-accumulation audit; verify the filter doesn't break any counters (tier1_count, tier2_count, mismatch counts must still accumulate correctly)
- **#23** — dataclass attribution metadata audit; verify FlippedCandidate field consumption stays clean (no orphan attribution from skipped candidates)
- **#11** — template-rendering surface audit (smoke artifact CSV + markdown emitters); verify the filter doesn't drop downstream visibility into excluded candidates if useful (banked V2 candidate from investigation §5: "optionally surface excluded candidates in a separate 'pre-empted candidates' diagnostic" — not required for this fix but flag if implementer thinks it's worth a sub-task)

### §3.2 Process discipline

- **NO Co-Authored-By footer** — ~499+ cumulative streak through housekeeping `8330e50`. Cite per fresh forward-binding lesson #7 (Phase 12 Sub-sub-bundle C.B 2026-05-15) in every commit message.
- **`python -m swing.cli` from worktree cwd**, NOT bare `swing`
- **ASCII-only on runtime CLI paths** + markdown narrative text (Windows cp1252 stdout safety)
- **TDD per task** (each TDD slice = ONE commit per `superpowers:test-driven-development`)
- **Edit tool for per-file edits**

### §3.3 Schema discipline (LOCK)

Schema v21 LOCKED. ZERO migration writes. `git diff main -- swing/data/migrations/` MUST stay empty.

### §3.4 L2 LOCK preservation (BINDING)

ZERO new Schwab API calls. ZERO reads of `{T}.schwab_api.parquet` from V2 code. V2's 5 BINDING L2 LOCK discriminating tests at `tests/research/test_aplus_v2_ohlcv_reader.py` MUST remain green.

### §3.5 Production read-only invariant

`git diff main -- swing/ --stat` MUST remain EMPTY. ALL changes are in `research/harness/aplus_v2_ohlcv_evaluator/sweep.py` + `tests/research/test_aplus_v2_ohlcv_sweep.py` (or equivalent test file). Production swing/ is UNTOUCHED.

---

## §4 Deliverables

1. **3 fix commits** (CORE Fix #1 + DEFENSIVE Fix #2 + OPTIONAL Fix #3) on `applied-research-v2-baseline-parity-excluded-filter` branch. Each per-test TDD slice as ONE commit per `superpowers:test-driven-development` discipline.

2. **3-4 discriminating tests** in `tests/research/test_aplus_v2_ohlcv_sweep.py` (or equivalent) per §2 above.

3. **1 V2 smoke re-run artifact** at `exports/diagnostics/aplus-sensitivity-v2-<NEW-timestamp>.{csv,md}` verifying Tier-1 FULL PASS.

4. **1 return report** at `docs/v2-baseline-parity-excluded-filter-return-report.md` covering: commit chain shape; Codex chain shape if invoked; per-expansion verdict if Codex invoked (34th cumulative validation expected); forward-binding lessons banked (likely none new; this fix is a clean implementation of gotcha #25 BINDING); V2 candidates updated.

---

## §5 NON-scope

- Phase 14 commissioning (DEFERRED per Path B)
- V2 method-record v0.2.1 amendment (D.3 from Option D; SEPARATE follow-up — small inline doc edit OR mini dispatch post-Option-A-fix)
- V2 candidate banking documentation in method-record (D.4 from Option D; SAME as D.3 follow-up)
- Full 63-eval-run operator reproduction (UNBLOCKED by THIS fix but is a SEPARATE operator-paired execution step)
- V2 reader "prefer-fresher mtime tiebreaker" (V2.5/V3 candidate; DEFERRED per OQ-18 + investigation D.4)
- V1 production code changes (production READ-ONLY beyond existing OQ-17 CLI carve-out)
- Schwab API integration changes (L2 LOCK preserved)

---

## §6 Post-fix handback

When fix shipped + Tier-1 FULL PASS verified:

1. Write return report at `docs/v2-baseline-parity-excluded-filter-return-report.md`
2. Inline self-verification: ruff check `research/harness/aplus_v2_ohlcv_evaluator/`; schema unchanged; baseline tests + 3-4 NEW discriminating tests all GREEN; V2 smoke Tier-1 FULL PASS; `git diff main -- swing/` empty; ZERO new Schwab API calls; ZERO Co-Authored-By footer
3. Hand back to operator with: fix summary + Tier-1 PASS confirmation + new smoke artifact path + V2 candidates banked (likely none new).

Orchestrator-side next steps post-fix:
- QA implementer product per `feedback_orchestrator_qa_implementer_product`
- Merge `--no-ff` to main; push
- Post-merge housekeeping (sub-event scale; in-place amendments; no new gotchas expected since gotcha #25 is the canonical lesson this fix implements)
- Operator-paired decision on D.3 (method-record v0.2.1) + D.4 (V2 candidate banking) — small inline OR mini dispatch
- Operator-paired execution of full 63-eval-run reproduction (Tier-1 PASS unblocks this)
- Research → shadow promotion gate per OQ-8 ladder fires post-full-reproduction + binding-threshold identification

---

*End of V2 OHLCV baseline-parity excluded-filter fix dispatch brief. Small fix scope (1-line + 3-6 tests + smoke re-run). Implements CLAUDE.md gotcha #25 (sentinel-bucket parity-comparison discipline) as its first canonical application. ~499+ ZERO Co-Authored-By footer streak preserved through this brief commit. Post-fix unblocks research→shadow promotion gate + full 63-eval-run operator reproduction.*
