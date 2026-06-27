# OHLCV Archive Consolidation — Executing-Plans Dispatch Brief

**Audience:** Fresh Claude Code instance with no prior conversation context.

**Mission:** Execute the implementation plan at `docs/superpowers/plans/2026-04-29-ohlcv-archive-consolidation-plan.md` (commit `00aa6f4`; 5 Codex rounds + R5 verification round → clean NO_NEW_CRITICAL_MAJOR). Ship Phase 3 of the post-2026-04-28 operator sequence via 7 sequential tasks. The plan IS the spec; this dispatch is plan-faithful execution with **one binding mid-dispatch operator-action gate** between Task 3 and Task 4.

**Expected duration:** 7 tasks + 2-4 Codex rounds via `copowers:executing-plans` wrapper = ~6-10 hours of work, paced to operator pacing AND to the mid-dispatch operator-action gate.

**Dispatch type:** `copowers:executing-plans` (wraps `superpowers:subagent-driven-development` with adversarial Codex review post-execution). Single-subagent dispatch.

**Pre-vetted depth:** plan went through 5 writing-plans Codex rounds + 1 verification round (R5 clean). Plan-rigor compounded — executing-plans Codex rounds should be modest (2-4 typical).

---

## §0 Read first

Read these in order before starting Task 1:

1. **The plan:** `docs/superpowers/plans/2026-04-29-ohlcv-archive-consolidation-plan.md` — THE CANONICAL SCOPE. Read all of it before invoking the executing-plans skill. The plan was authored via `copowers:writing-plans` (5 Codex rounds + R5 verification round, terminating clean `NO_NEW_CRITICAL_MAJOR`); it supersedes the writing-plans brief in case of any divergence.

2. **`docs/ohlcv-archive-consolidation-writing-plans-brief.md`** — historical reference for plan-authoring decision context. Plan §"Goal" + per-task bodies supersede where they differ.

3. **`CLAUDE.md`** — particularly:
   - **yfinance gotchas** — `threads=False` on `yf.download()`; `Ticker(t).history()` does NOT accept `threads=`; `group_by='column'` returns MultiIndex column requiring squeeze. ALL load-bearing for the wrapper.
   - **DB location invariant** — `~/swing-data/` is OUTSIDE Drive. Archive lives at `~/swing-data/prices-cache/`; preserve this location.
   - **`os.replace` cross-device-link Windows gotcha** — atomic-replace uses `tempfile.NamedTemporaryFile(dir=archive_dir, ...)` + `os.replace(tmp, final)`. NEVER use `shutil.move`.

4. **`docs/orchestrator-context.md`** — read these sections:
   - §"Currently in-flight work" — current state at HEAD (Phase 3 starting; Phase 2 closed 2026-04-29).
   - §"Binding conventions" — 4-tier commit-message convention; observable-verification grep ERE form; ruff baseline 91; no-amend; no Claude footer.
   - §"Anti-patterns" — particularly mid-session scope expansion; vacuous regression tests; bug-fix investigation that tests plausible mechanisms.
   - §"Lessons captured" — read entire section. Particularly relevant:
     - **Multi-path-ingestion** (2026-04-29) — applies to the multi-fetch-path coverage (PriceFetcher + pipeline/ohlcv.py + OhlcvCache).
     - **Snapshot-semantic claims should explicitly address transaction isolation** (2026-04-28) — atomicity claims for archive writes are the same class.
     - **Bug-class durability vs scope-of-closure** (2026-04-29) — relevant to the multi-fetch-path landscape.
     - **MAX_ROUNDS-vs-NO_NEW_CRITICAL_MAJOR** (2026-04-29) — verification round if final round had findings.

5. **`docs/phase3e-todo.md`** §"2026-04-28 OHLCV archive consolidation" — backlog context.

6. **Precedent executing-plans briefs:**
   - `docs/sector-industry-capture-executing-plans-brief.md` (Phase 1; structural template).
   - `docs/hyp-recs-trade-prep-expansion-executing-plans-brief.md` (Phase 2 main; 22-file scope template).
   - `docs/hyp-recs-success-path-fix-executing-plans-brief.md` (Phase 2 cleanup; small-scope template).

If any file path doesn't resolve, surface in return report — do NOT silently proceed against a stale path.

---

## §0 Skill posture

- **INVOKE** `copowers:executing-plans` — wraps `superpowers:subagent-driven-development` with adversarial Codex review post-execution.
- **DO NOT INVOKE** `superpowers:brainstorming`, `copowers:brainstorming`, `superpowers:writing-plans`, or `copowers:writing-plans`. The plan is locked. Re-litigation is out of scope. If a plan task appears impossible to implement as written, STOP and surface in return report via §8 escape hatch; do NOT silently re-design.
- **DO** invoke adversarial Codex review per `copowers:executing-plans` standard cycle. Iterate to `NO_NEW_CRITICAL_MAJOR`. Round budget: ~2-4 typical (plan went through 5 writing-plans rounds + R5 verification; structural issues already caught). **Per the chart-pattern flag-v1 Phase 7 induced-bug pattern + 2026-04-29 hyp-recs writing-plans MAX_ROUNDS lesson:** if the final round produces findings that resolve, run ONE additional verification round to confirm clean before terminating. Do NOT stop at MAX_ROUNDS with active findings.
- **Single-subagent dispatch** per the 11-phase ZERO-rogue track record. NO parallel-subagent dispatch at the task level. Subagent role-partitioning WITHIN a task is collision-safe.

---

## §1 Strategic context

**This dispatch ships OHLCV archive consolidation** — Phase 3 of the post-2026-04-28 operator sequence. Production paths (PriceFetcher + pipeline/ohlcv.py + OhlcvCache) currently re-fetch from yfinance every run for data that's already on disk in the research-cache. Migration to per-ticker incremental archive cuts per-run yfinance call volume by ~99% for established tickers.

**Real value:** yfinance rate-limit relief + pipeline speed + research-branch parity + diagnostic capability. Storage is essentially free.

**Sequencing.** Phase 3 of the 6-phase post-2026-04-28 sequence. Phase 4 (cleanup-remainder = Bug 7 mixed-anchor family) follows Phase 3 per operator's 2026-04-29 sequencing decision.

---

## §2 V1 Scope (per plan; LOCKED)

The plan IS the canonical scope source-of-truth. Plan §"V1 Scope" + §"Tasks" enumerate the work. Execute as written.

**7 plan tasks per plan:**
1. **Task 1:** Migration script `swing/tools/migrate_prices_cache.py` for one-time consolidation of `~/swing-data/prices-cache/` from per-as-of-date keying to per-ticker keying. Backup-first; atomic-replace; idempotent; interruption-safe.
2. **Task 2:** Helper module `swing/data/ohlcv_archive.py` with `read_or_fetch_archive(ticker, *, end_date, cache_dir, archive_history_days) -> pd.DataFrame | None`. Per the plan §3.C: keyword-only signature; returns archive ≤ end_date OR None for delisted/invalid; handles cache-empty/fresh/stale-incremental/weekly-refresh branches.
3. **Task 3:** Config field `archive_history_days: int = 1260` in `swing/config.py`. **Toml-shadowing audit (NARROWED scope per Codex R3 M1):** `grep -rn "archive_history_days" --include="*.toml" --include="*.yaml" --include="*.yml" --include="*.json" --include="*.cfg" --include="*.ini" .` (NOT whole-repo). Verify zero hits in tracked config-shaped files BEFORE commit.
4. **Task 4:** `swing/prices.py PriceFetcher` refactor to consume the archive helper. Backward-compat API (`get(ticker, lookback_days, as_of_date=None)`); existing call sites continue to work.
5. **Task 5:** `swing/pipeline/ohlcv.py` wrap to consume the archive helper. Pipeline runs hit archive on cache hit; fetch yfinance only for incremental gap.
6. **Task 6:** `swing/web/ohlcv_cache.py OhlcvCache` backing — cold-start hydrates from disk archive on cache miss. **FIXED_TODAY monkeypatch** required for time-stable cold-start tests (Codex R1 M4 fix).
7. **Task 7:** Final verification gate. Operator-action runbook included at Step 7f per implementer.

---

## §3 BINDING mid-dispatch operator-action gate (between Task 3 and Task 4)

**This is the unusual piece of this dispatch.** After Task 3 commits, BEFORE proceeding to Task 4:

1. **Surface a "MID-DISPATCH PAUSE: operator-action required" message** in the dispatch chat. Specifically state:
   > Task 3 has landed (config field + audit clean). Tasks 4-6 are the consumer refactors that consume the archive. Before Task 4 commits, please run:
   >
   > `python -m swing.tools.migrate_prices_cache`
   >
   > This consolidates the existing 5,521 per-as-of-date files in `~/swing-data/prices-cache/` into ~200-300 per-ticker parquets. Idempotent + interruption-safe; can be re-run if needed.
   >
   > Without the migration, Tasks 4-6 still work, but PriceFetcher pays the yfinance cost of re-fetching ~200-300 tickers' worth of full history on first archive read. With the migration, immediate archive cache hits.
   >
   > Reply when migration completes (or skipped-with-rationale), and I'll proceed with Tasks 4-7.

2. **WAIT for operator's reply** before proceeding to Task 4. Do NOT silently proceed; do NOT auto-run the migration on the operator's behalf.

3. **If operator skips the migration** (e.g., operator wants to verify Tasks 4-6 work end-to-end without the migration first), proceed with Task 4-6 as planned. The migration can be run later. Note in return report.

4. **If migration fails** (e.g., disk full, permission denied, parquet read error), operator surfaces the failure; you investigate via Task 1's idempotency contract (re-run-safe; rollback-if-incomplete). Do NOT proceed to Task 4 until migration is resolved OR operator explicitly skips.

---

## §4 Binding conventions (excerpts; full per orchestrator-context.md)

NON-NEGOTIABLE across all task implementations:

1. **Branch:** `main`. No feature branches. No `--no-verify`. No amending; new commits to fix.
2. **No Claude co-author footer.** Plain conventional-commits messages only.
3. **4-tier commit-message convention:**
   - Task implementation: `feat(<area>): Task N — <description>` (flat numbering per chart-scope-policy-v2 + sector + hyp-recs precedents).
   - Codex review-fix: `fix(<area>): Codex R<round> Major <id> — <description>`.
   - Internal-Codex within-task: append `(internal)` qualifier.
   - Internal code-review: `fix(<area>): code-review I<id> — <description>`.
   - Format-only cleanup: no task ID required.
4. **Observable-verification subject-only grep BEFORE each task commit:**
   ```
   git log -E --pretty='%s' --grep='^[a-z]+\([a-z]+\): Task <N>'
   ```
   ERE flag REQUIRED. Cross-plan grep aliasing is expected (per the sector + hyp-recs precedents). Disambiguate within THIS dispatch's chain by commit subject.
5. **TDD discipline:** failing test first → minimal implementation → passing test → commit. One red-green cycle per logical change.
6. **Discriminating-test discipline (HARD requirement per plan task bodies + §3.D):**
   - **Cache-coherence branches:** test setups must use distinct `(latest_stored_bar_date, last_full_refresh_date)` states that EXERCISE EACH BRANCH SEPARATELY. Vacuous tests that pass under any branch resolution would mask bugs.
   - **Atomic-replace correctness:** test must construct a partial-write/crash scenario AND verify recovery. Vacuous "happy-path completes" tests miss the orphan-temp-file failure mode.
   - **Migration idempotency:** re-run after partial completion; verify state correctness.
   - **Cross-file atomicity skew:** test setups must construct parquet/meta skew (e.g., parquet exists, meta missing) and verify recovery via full-refresh-on-corrupted-meta.
   - **Multi-path coverage:** PriceFetcher + pipeline/ohlcv.py + OhlcvCache all need consumer-adapter tests. Tests for one consumer don't substitute for the others.
   - **Trading-day vs calendar-day window semantics:** test the formula `ceil(n * 365.25 / 252) + 30` with at least one fixture that exercises the buffer (e.g., quarter spanning a holiday-heavy month).
7. **Ruff baseline 91 errors** unchanged. Tasks must NOT introduce new violations; do NOT incidentally fix the baseline.
8. **Test discipline:** `python -m pytest -m "not slow" -q` is the fast suite; must stay green throughout.

---

## §5 Adversarial review watch items (for Codex during executing-plans cycle)

These are the high-likelihood failure modes Codex should specifically check post-execution. Pre-empt by self-checking BEFORE each task commit:

1. **Trading-day vs calendar-day formula correctness** per Codex R1 C1 + R2 C1 history. The formula is `ceil(n * 365.25 / 252) + 30`. The defensive `.tail(archive_history_days)` post-fetch truncation is the second clamp. Both must be present.

2. **Atomic-replace correctness** per locked decision §2.7. `tempfile.NamedTemporaryFile(dir=archive_dir, ...)` + `os.replace(tmp, final)`; NEVER `shutil.move`. Test must construct a partial-write scenario AND verify recovery.

3. **Cross-file atomicity contract** per Codex R1 M1 history. Per-file `os.replace` is benign because readers handle parquet/meta skew via full-refresh-on-missing-or-corrupted-meta path. Test setups must include skew states; recovery must be verified.

4. **Toml-shadowing audit scope narrowed** per Codex R3 M1 history. `grep` includes `*.toml`/`*.yaml`/`*.yml`/`*.json`/`*.cfg`/`*.ini` ONLY (NOT whole-repo). Plan task body must specify the narrowed scope; Codex will check.

5. **Migration script idempotency + interruption-safety** per locked decision §2.4 + Codex R1 M1 cross-file atomicity. Re-run after kill mid-migration; verify state.

6. **Multi-path coverage** per the multi-path-ingestion lesson (2026-04-29). PriceFetcher + pipeline/ohlcv.py + OhlcvCache all need consumer-adapter tests. Tests for one consumer don't substitute for the others.

7. **yfinance gotcha compliance** per CLAUDE.md gotchas: `threads=False` on `yf.download()`; `Ticker.history()` does NOT accept `threads=`; MultiIndex column squeeze. Plan task body for the wrapper helper must address all three.

8. **FIXED_TODAY monkeypatch for cold-start tests** per Codex R1 M4 history. Cold-start (cache-empty / weekly-refresh-due) is time-dependent; tests must monkeypatch the date function to a known value.

9. **Backward-compat of PriceFetcher API** per plan + writing-plans phase. Existing call sites at `swing/cli.py:127, 274` + `swing/pipeline/runner.py:146` + `swing/weather/runner.py:15` consume `PriceFetcher.get(ticker, lookback_days, as_of_date=None)`. The refactor must preserve this signature. Codex will check.

10. **Operator-action gate respected** per §3 above. Codex may not directly verify this, but the dispatch implementer must surface the pause message between Task 3 and Task 4 commits AND wait for operator confirmation. Note in return report.

---

## §6 Done criteria

- All 7 plan tasks complete.
- Each task implementation commit follows the 4-tier convention with observable-verification grep output in commit body.
- Operator-action gate respected between Task 3 and Task 4 (PAUSE + WAIT FOR OPERATOR; resume only after operator reply).
- Final fast-test count documented and reconciled against plan's projection (test baseline pinned at HEAD `a4811f4` was 1314 fast tests; plan §"Test Count Projection" gives the expected post-dispatch number).
- Adversarial Codex review reaches `NO_NEW_CRITICAL_MAJOR` with verification round if final round had findings.
- All commits pushed to `origin/main`.
- Operator-runnable: `swing pipeline run` produces archive cache hits (verifiable via reduced yfinance call count in logs); `swing web` cold-start hydrates from disk archive (no fetch storm).
- Return report posted per §7.

---

## §7 Return report format

Post as final message:

```
## OHLCV Archive Consolidation — Executing-Plans Return Report

**Plan executed:** docs/superpowers/plans/2026-04-29-ohlcv-archive-consolidation-plan.md (commit 00aa6f4)
**Commit chain:** <first SHA> → <last SHA> on origin/main
**Total commits:** N (M task implementations + K Codex review-fixes + L cleanup)
**Codex rounds:** N rounds, terminating at NO_NEW_CRITICAL_MAJOR (with verification round if applicable)
**Fast-test count:** <count> at HEAD <SHA> (delta: +N from baseline 1314)

**Tasks completed:**
1. Task 1 — Migration script (commit <SHA>)
2. Task 2 — Helper module ohlcv_archive (commit <SHA>)
3. Task 3 — Config field + toml-shadowing audit (commit <SHA>)

**[MID-DISPATCH OPERATOR-ACTION GATE]**
Operator confirmed migration on <date>: <success / skipped-with-rationale / failed-and-resolved>.
Migration outcome: <consolidated <N> per-as-of-date files into <M> per-ticker parquets / skipped per operator>.

4. Task 4 — PriceFetcher refactor (commit <SHA>)
5. Task 5 — pipeline/ohlcv.py wrap (commit <SHA>)
6. Task 6 — OhlcvCache backing (commit <SHA>)
7. Task 7 — Verification gate (commit <SHA>)

**Codex findings dispositioned:**
- R1: <count> Critical, <count> Major, <count> Minor — <breakdown>
- R2: ...
... (per round)

**Operator-action items (post-dispatch):**
- (Optional) Run `swing pipeline run`; observe yfinance call count in logs (expect ~99% reduction for established tickers).
- (Optional) Restart `swing web`; observe no cold-start fetch storm (cache hydrates from disk archive).
- Verify archive disk usage: `du -sh ~/swing-data/prices-cache/` should show ~50-100 MB (down from 53 MB across 5,521 files; consolidated to ~200-300 per-ticker files).

**Open questions for orchestrator triage:**
- <any items the implementer flagged as needing operator/orchestrator decision>

**Recommended next step:** Phase 4 of operator sequence — cleanup-remainder dispatch (Bug 7 mixed-anchor family + test gaps + multi-rebuild drift). Bundles the deferred items from the Phase 2 closure.
```

---

## §8 If you get stuck

- **If a plan task appears impossible to implement as written:** STOP, surface in return report. Do NOT silently re-design.
- **If a precedent file path doesn't resolve:** Use `Glob` / `Grep` to find the actual current path. Plan was authored at HEAD `a4811f4`; should be stable.
- **If Codex round count exceeds 5 without convergence:** STOP, surface in return report with the unresolved finding. Do NOT iterate indefinitely.
- **If the final Codex round produces findings that resolve:** run ONE verification round to confirm clean before terminating.
- **If discriminating-test sanity check reveals vacuousness:** STOP, restructure the test setup, then resume.
- **If you find a scope-deviation opportunity:** SURFACE in return report as a follow-up; do NOT in-line-implement.
- **If migration fails on operator's machine** (disk full, permission denied, parquet read error): surface in dispatch chat; operator decides whether to fix the environment issue + re-run, OR skip migration (Tasks 4-6 can proceed without). Do NOT proceed to Task 4 silently.
- **If yfinance is unreachable** during a test that requires live fetch: tests should mock yfinance for unit tests; if a live-yfinance test fails because of upstream unavailability, mark as `@pytest.mark.slow` skipped + surface in return report.

---

## Appendix A: Plan-history awareness

The plan went through 5 writing-plans Codex rounds + R5 verification round before this dispatch. Major findings already addressed:

- R1: 1 Critical (1260 trading-vs-calendar mismatch) + 4 Majors + 1 Minor — all RESOLVED.
- R2: 1 Critical (formula tightness `n*7/5+14`; switched to `ceil(n*365.25/252)+30`) + 0 Majors + 2 Minors — all RESOLVED.
- R3: 0 Critical + 1 Major (audit scope narrowed) + 2 Minors — all RESOLVED.
- R4: 0 Critical + 0 Major + 1 Minor (stale prose) — RESOLVED.
- R5 verification: 0/0/0 — clean termination.

Plan-history is durable in `docs/superpowers/plans/2026-04-29-ohlcv-archive-consolidation-plan.md` commit chain (`dbcc913 → e765aea → c476287 → 6a43566 → 00aa6f4`). Implementer should NOT re-iterate on resolved findings; if a Codex round in THIS dispatch raises a finding that already has a plan-history fix, cite the plan + the fix commit, then proceed.

---

## Appendix B: Cross-references

- **Plan:** `docs/superpowers/plans/2026-04-29-ohlcv-archive-consolidation-plan.md` (commit `00aa6f4`).
- **Writing-plans brief:** `docs/ohlcv-archive-consolidation-writing-plans-brief.md`.
- **Backlog:** `docs/phase3e-todo.md` §"2026-04-28 OHLCV archive consolidation".
- **CLAUDE.md gotchas:** yfinance + `os.replace` cross-device — both load-bearing.
- **Multi-path-ingestion lesson** (orchestrator-context 2026-04-29).
- **Bug-class durability vs scope-of-closure lesson** (orchestrator-context 2026-04-29).
- **Snapshot-semantic transactional isolation lesson** (orchestrator-context 2026-04-28).
- **Research-cache precedent** at `~/swing-data/research-cache/ohlcv/` (operator's machine; per-ticker parquet pattern).
