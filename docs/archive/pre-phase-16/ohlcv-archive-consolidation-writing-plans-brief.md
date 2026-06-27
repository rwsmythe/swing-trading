# OHLCV Archive Consolidation — Writing-Plans Dispatch Brief

**Audience:** Fresh Claude Code instance with no prior conversation context.

**Mission:** Author an implementation plan for OHLCV archive consolidation (Phase 3 of the post-2026-04-28 operator sequence) via `copowers:writing-plans`. Brainstorm is EXPLICITLY SKIPPED — operator pre-locked all design decisions on 2026-04-28 (corporate-action policy) and 2026-04-29 (this brief; remaining decisions). This dispatch goes directly to writing-plans phase.

**Expected duration:** ~30-60 min plan-authoring + 3-5 Codex rounds via `copowers:writing-plans` wrapper = ~3-5 hours total.

**Dispatch type:** `copowers:writing-plans` (NOT brainstorming, NOT executing-plans).

---

## §0 Read first

Read these in order before invoking the writing-plans skill:

1. **`CLAUDE.md`** — project conventions, gotchas, invariants. Particularly:
   - **yfinance gotchas** — `threads=False` required on `yf.download`; `Ticker(t).history()` does NOT accept `threads=` kwarg; `yfinance group_by='column'` returns MultiIndex column requiring squeeze. All directly relevant to the wrapped fetch path.
   - **DB location invariant** — `%USERPROFILE%/swing-data/swing.db` is OUTSIDE the Drive directory; SQLite + Drive sync = corruption. The OHLCV archive lives at `~/swing-data/prices-cache/` and `~/swing-data/research-cache/ohlcv/` — also outside Drive; preserve this property.
   - **`os.replace` cross-device-link Windows gotcha** — relevant if migration script uses temp-file-then-rename pattern; create temp files in destination directory.

2. **`docs/orchestrator-context.md`** — read these sections:
   - §"Currently in-flight work" — current state at HEAD; this dispatch is Phase 3 of the post-2026-04-28 sequence (sector + hyp-recs trade-prep + hyp-recs success-path-fix all shipped + production-verified 2026-04-29).
   - §"Binding conventions" — 4-tier commit-message convention; observable-verification grep ERE form; ruff baseline 91; no-amend; no Claude footer.
   - §"Anti-patterns to avoid" — particularly mid-session scope expansion; brief drafting drift.
   - §"Lessons captured" — read entire section. Particularly relevant:
     - **Multi-path-ingestion** (2026-04-29) — applies to multi-fetch-path coverage (PriceFetcher + pipeline/ohlcv.py + OhlcvCache).
     - **Snapshot-semantic claims at spec/plan time should explicitly address transaction isolation** (2026-04-28) — applies to archive-coherence claims.
     - **Bug-class durability vs scope-of-closure** (just-captured 2026-04-29) — relevant to the multi-path-fetch landscape.
     - **JS-test-harness-weighting** (2026-04-29) — not directly applicable (this is server-side; no HTMX), but the operator-witnessed-verification discipline still applies for production-verification of any pipeline-runtime change.
     - **HTMX OOB-swap partial drift** — not directly applicable.

3. **`docs/phase3e-todo.md`** §"2026-04-28 OHLCV archive consolidation (QUEUED; Medium effort)" — **THE SCOPE-OF-WORK SOURCE OF TRUTH** for this dispatch. Operator-locked design decisions are in the "V1 scope" + "Open design questions" subsections; §2 below mirrors them.

4. **Precedent plans** (structural references for what a writing-plans output looks like):
   - `docs/superpowers/plans/2026-04-29-hyp-recs-success-path-fix-plan.md` — most-recent (2026-04-29; 5 tasks; clean R4 termination). Tight scope; good template for a small dispatch.
   - `docs/superpowers/plans/2026-04-28-sector-industry-capture-plan.md` — Phase 1 plan (10 tasks; 22 files). Larger scope; good template for migration + multi-file-modification structure.

5. **Source files to inspect:**
   - `swing/prices.py` (`PriceFetcher` class) — current per-as-of-date parquet caching. The PRIMARY refactor target.
   - `swing/pipeline/ohlcv.py` — pipeline-side OHLCV fetcher (chart-step). Currently NO disk cache; fresh `yf.Ticker.history()` per pipeline run. Wrap-target for V1 §2.
   - `swing/web/ohlcv_cache.py` (`OhlcvCache` class) — in-memory TTL cache for dashboard SMA advisories. V1 §3 (optional) backs this with the disk archive.
   - Existing research-branch precedent at `~/swing-data/research-cache/ohlcv/` (operator's machine; not in repo) — per-ticker parquet pattern. The structural model for V1 §1.
   - Call sites: `swing/cli.py` lines 127, 274 (PriceFetcher instantiations); `swing/pipeline/runner.py:146` (PriceFetcher instantiation); `swing/weather/runner.py:15` (PriceFetcher consumer). All consumers of PriceFetcher; all should continue to work post-refactor.

6. **`docs/phase3e-todo.md`** §"2026-04-26 chart-pattern flag-v1 brainstorm follow-ups → V2 capability extensions" — note "Slow-test live-fetch suite" deferred V2 item. NOT in scope for this dispatch but mentioned as related.

If any file path doesn't resolve, surface in return report — do NOT silently proceed against a stale path.

---

## §0 Skill posture

- **INVOKE** `copowers:writing-plans` — wraps `superpowers:writing-plans` with adversarial Codex review (3-5 rounds typical).
- **DO NOT INVOKE** `superpowers:brainstorming`, `copowers:brainstorming`, `superpowers:executing-plans`, or `copowers:executing-plans`. Design decisions are pre-locked (see §2). Re-litigation is out of scope. If a locked decision is impossible to implement as written, STOP and surface in return report via §10 escape hatch; do NOT silently re-design.
- **DO** invoke adversarial Codex review per `copowers:writing-plans` standard cycle. Iterate to `NO_NEW_CRITICAL_MAJOR`. **Per the chart-pattern flag-v1 Phase 7 induced-bug pattern + 2026-04-29 hyp-recs writing-plans MAX_ROUNDS lesson:** if the final round produces findings that resolve, run ONE additional verification round to confirm clean before terminating. Do NOT stop at MAX_ROUNDS with active findings.
- **Plan output target path:** `docs/superpowers/plans/2026-04-29-ohlcv-archive-consolidation-plan.md`. Commit the plan as part of the standard cycle.

---

## §1 Strategic context

**Why this work.** Operator question 2026-04-28: "are we archiving any of the yfinance data we are pulling down? One way to improve throughput would be to start creating a local history which could be queried for all historical data, only using yfinance to pull down the most recent OHLCV numbers." Investigation surfaced three caching paths with inconsistent semantics:

1. **`swing/prices.py PriceFetcher`** → `~/swing-data/prices-cache/`. On-disk parquet cache. **53 MB across 5,521 files.** Wasteful per-as-of-date keying produces redundant per-day snapshots of the same 120-day window for the same ticker (~200-300 unique tickers across 5,521 files).
2. **`swing/pipeline/ohlcv.py`** (chart-step OHLCV fetcher). NO disk cache. Fresh `yf.Ticker.history()` every pipeline run for chart-scope tickers (~5-15 per run).
3. **`swing/web/ohlcv_cache.py OhlcvCache`**. TTL-cached in-memory (3600s default), restart-flushed.
4. **`~/swing-data/research-cache/ohlcv/`** (research branch precedent; 92 MB across 2,603 ticker files; one file per ticker — proper incremental-archive pattern; production paths don't consume it).

**The architectural gap:** production paths (#1 + #2) re-fetch from yfinance every run for data that's already on disk in the research cache (#4). The proper incremental-archive pattern exists in the codebase — just not used by production. Migration to per-ticker incremental cache cuts per-run yfinance call volume by ~99% for established tickers.

**Sequencing context.** Phase 3 of the operator sequence (sector → hyp-recs trade-prep + success-path-fix → **OHLCV archive (this dispatch)** → noise queue → configuration page → Tier-3 design). Phase 2 closed 2026-04-29 production-verified.

**Real value isn't storage** — total archive size is ~100 MB for SPX+NDX+S&P 1500 × 5y. Real value is yfinance rate-limit relief + pipeline speed + research-branch parity + diagnostic capability.

---

## §2 Locked decisions (DO NOT re-litigate)

Operator-locked across 2026-04-28 (corporate-action policy) + 2026-04-29 (remaining decisions; per orchestrator-context discipline that mechanical questions resolve in writing-plans-phase). The plan implements these as written; no re-design.

1. **Corporate-action retroactive adjustment policy.** **Option (a) weekly full-refresh on active tickers** per operator-locked 2026-04-28. Implementation: detect "first archive read of the calendar week" per ticker; trigger a full-history yfinance pull that overwrites the per-ticker parquet. Subsequent reads in the same week consume the cached archive incrementally (read latest stored bar; pull yfinance for `latest+1` → today; append). "Active ticker" = ticker that the consumer code path actually requests this week (demand-driven; NO pre-emptive refresh of dormant tickers).

2. **Cache-coherence policy (per-call rule).** Read archive first; check `(latest_stored_bar_date, last_full_refresh_date)`. If `latest_stored_bar_date < last_completed_session`, pull yfinance for the gap and append. If `last_full_refresh_date < (today - 7 days)` AND ticker is being requested, trigger weekly full-refresh BEFORE incremental fetch. Net effect: archive is the source-of-truth for established tickers; yfinance is only consulted for incremental gaps + weekly corporate-action refresh.

3. **Schema location: per-ticker parquet** (matches `~/swing-data/research-cache/ohlcv/` precedent). One file per ticker: `{TICKER}.parquet` containing the full retained history. Date column is the index. Add a metadata sidecar OR a dedicated metadata column for `last_full_refresh_date` (writing-plans phase decides specific encoding — see §3.A below). NO SQLite table for OHLCV bars (decision rationale: parquet is more efficient for long-history scans; existing research-cache precedent works; SQLite would add migration cost without clear benefit at this scale).

4. **Migration strategy for the 5,521 redundant files.** One-time consolidation script invoked manually by the operator (NOT auto-run on first import). Script reads all per-as-of-date parquet files in `~/swing-data/prices-cache/`, groups by ticker, takes the union of per-day rows (keeping the highest as_of_date when duplicates exist), writes one consolidated `{TICKER}.parquet` per ticker, then deletes the old per-as-of-date files. Backup-first discipline: script writes consolidated files to a temp directory first, verifies integrity, then atomic-replaces. Old files are NOT deleted until atomic-replace succeeds.

5. **Retained history depth.** Default 5 years (1260 trading days) for new full-history pulls. Configurable via `Config.<area>.archive_history_days` with a sensible default. Picks itself up at archive-build time; no per-call gating. **Toml-shadowing audit applies** (per `aeb2084` lesson 2026-04-28 + multi-path-ingestion lesson 2026-04-29) — pre-flight `grep -rn "archive_history_days" .` on tracked config files BEFORE the implementation commits.

6. **OhlcvCache backing (V1 §3 optional).** **IN SCOPE** for this dispatch. The in-memory TTL cache backs to the disk archive on cache miss, eliminating the cold-start fetch storm after `swing web` restart. If the disk archive has a fresh-enough entry (per the cache-coherence policy in #2), the in-memory cache hydrates from disk; otherwise it falls back to the existing yfinance fetch path (which now ALSO writes through to disk archive).

7. **Atomicity of writes.** Disk archive writes use temp-file-then-atomic-replace (`tempfile.NamedTemporaryFile(dir=archive_dir, ...)` + `os.replace(tmp, final)`) per the CLAUDE.md `os.replace` cross-device-link gotcha. NEVER use `shutil.move` expecting overwrite on Windows.

---

## §3 Open design questions for writing-plans phase

Mechanical questions the writing-plans implementer resolves while drafting the plan.

### A. Metadata encoding for `last_full_refresh_date`

Per #3 above, per-ticker parquet needs a `last_full_refresh_date` field. Two options:
- **(a) Sidecar JSON.** `{TICKER}.parquet` + `{TICKER}.meta.json` with `{"last_full_refresh_date": "YYYY-MM-DD"}`. Pro: trivial to read/write; pro: parquet files unchanged structurally. Con: two files per ticker.
- **(b) Dedicated metadata column.** Single-row metadata in a parquet sidecar OR a special metadata-only row in the same parquet. More complex.
- **Recommendation: (a) sidecar JSON.** Simpler; no parquet schema mutation. Plan picks (a) unless concrete reason against.

### B. Archive directory location

Should the archive live at:
- `~/swing-data/prices-cache/` (existing PriceFetcher cache dir; consolidate in place; aligns with existing config field)?
- `~/swing-data/ohlcv-archive/` (new dedicated dir; clear naming distinct from research-cache/ohlcv/)?
- **Recommendation: `~/swing-data/prices-cache/` (consolidate in place).** Existing config + existing call sites; minimum-disruption to consumers. Naming is slightly imprecise (it's no longer just a "cache" — it's an archive); plan can document this in code comments or rename in V2 if operator wants.

### C. yfinance-fetch wrapper signature

The pipeline path (`swing/pipeline/ohlcv.py`) and the PriceFetcher path use different yfinance call shapes (`yf.Ticker.history()` vs `yf.download()`). The archive read+write logic should be ONE shared helper consumed by both. Plan defines the helper signature.

Suggested: `read_or_fetch_archive(ticker: str, end_date: date, lookback_days: int) -> pd.DataFrame`. Internally: read archive → check freshness → fetch yfinance gap if needed → append → return slice. Plan refines.

### D. Test surface

Discriminating tests needed for:
- Per-call archive read/write semantics (cache hit; cache stale; cache empty for new ticker).
- Weekly full-refresh trigger (last_full_refresh_date > 7 days ago → triggers full-pull; ≤ 7 days → incremental).
- Atomic-replace correctness (temp file → atomic replace → no torn writes).
- Migration script correctness (consolidation preserves all unique date rows; old files deleted only after atomic-replace).
- OhlcvCache backing (cold-start hydrates from disk archive; warm-cache stays in memory).
- yfinance integration safety (mocked yfinance for unit tests; live yfinance only in slow-marked tests).

Per the discriminating-test discipline + multi-path-ingestion lesson, tests must cover ALL fetch-path consumers (PriceFetcher, pipeline/ohlcv.py wrapped, OhlcvCache backed) — NOT just one.

### E. Test count baseline + projection

Plan should pin current fast-test count (`python -m pytest -m "not slow" -q`) at plan-authoring time and project per-task additions. Current baseline (post-2026-04-29 commits): 1314 fast tests (or whatever HEAD shows at plan-authoring; trust pytest output per CLAUDE.md drift gotcha).

---

## §4 V1 Scope (binding)

Per `docs/phase3e-todo.md` §"2026-04-28 OHLCV archive consolidation" + §2 + §3 above:

1. **Migration script** for one-time consolidation of `~/swing-data/prices-cache/` from per-as-of-date keying to per-ticker keying. Manual invocation only (not auto-run). Backup-first; atomic-replace; old files deleted last.

2. **`swing/prices.py PriceFetcher` refactor.** Switch from per-as-of-date parquet keying to per-ticker incremental archive. Public API stays compatible (`get(ticker, lookback_days, as_of_date=None)` continues to work); internal storage shape changes.

3. **`swing/pipeline/ohlcv.py` wrap.** Wrap the existing `yf.Ticker(t).history(...)` fetch in the same archive-aware helper used by PriceFetcher. Pipeline runs now consume the archive on cache hit; fetch yfinance only for the incremental gap.

4. **`swing/web/ohlcv_cache.py OhlcvCache` backing.** On cache miss, hydrate from disk archive (per the same archive-aware helper). Eliminates cold-start fetch storm after `swing web` restart.

5. **Config field for retained history depth.** New `Config.<area>.archive_history_days: int = 1260` (5y default). Toml-shadowing audit per locked decision §2.5.

6. **Tests.** Per §3.D test surface — discriminating tests for each consumer + the shared helper + the migration script. Mocked yfinance for unit tests; live yfinance reserved for slow-marked V2 follow-up.

---

## §5 V1 out-of-scope (DEFER)

- 1-min intraday bars (would multiply storage by ~390× — out of V1 scope; framework is daily-cycle).
- Cross-platform sync (Drive-synced archive would require careful WAL-mode handling — not applicable to parquet but principle stands; out of V1 scope).
- Automatic universe expansion (auto-archiving tickers operator hasn't asked about). V1 archives only what production paths request; demand-driven, NOT pre-emptive.
- Slow-marked live-fetch test suite (V2 deferred; mentioned in chart-pattern flag-v1 V2 capability extensions).
- Per-ticker corporate-action calendar lookup (would skip the weekly-refresh penalty for tickers without recent splits/dividends). V2 hardening.
- Migration of `research-cache/ohlcv/` to consume the same code path (research branch is independent of production paths; defer until research code paths actually need it).

---

## §6 Plan acceptance criteria

The plan output (at `docs/superpowers/plans/2026-04-29-ohlcv-archive-consolidation-plan.md`) MUST satisfy:

1. **Per-task TDD discipline.** Each task: failing test first → minimal implementation → passing test → commit. One red-green cycle per logical change.
2. **Discriminating-test discipline** per §3.D + the canonical compounding-confound failure modes. Each task with a discriminating test includes a "would this test fail if the implementation never actually called the new code?" sanity-check sentence in the task body.
3. **Multi-path-ingestion lesson application** (2026-04-29). Tests must cover ALL fetch-path consumers — PriceFetcher, pipeline/ohlcv.py, OhlcvCache. If a plan task tests one consumer, the corresponding tests for the others are explicit.
4. **Sequential single-subagent execution discipline.** Plan tasks are SEQUENTIAL; no parallel-subagent collision risk. Plan task IDs follow the convention (flat `Task N` per chart-scope-policy-v2 + sector-capture + hyp-recs precedents).
5. **Observable-verification subject-only grep pattern** per binding conventions: `git log -E --pretty='%s' --grep='^[a-z]+\([a-z]+\): Task <N>'` before each task implementation commit. ERE flag REQUIRED. Cross-plan grep aliasing is expected (per the sector dispatch + just-shipped hyp-recs precedents).
6. **4-tier commit-message convention.** Task implementations: `feat(<area>): Task N — <description>`. Codex review-fix: `fix(<area>): Codex R<round> Major <id> — <description>`. Internal-Codex: `(internal)` qualifier. Internal code-review: `code-review I<id>`. Format-only: no task ID.
7. **Migration script is the FIRST plan task.** Operator runs it manually before the consumer-refactor tasks land in production. Plan task body specifies operator-action: "Operator runs `python -m swing.tools.migrate_prices_cache` once before pulling the consumer-refactor commits."
8. **Toml-shadowing audit task body** per locked decision §2.5. Pre-flight `grep -rn "archive_history_days" .` on tracked config files; verify zero hits BEFORE commit.
9. **Atomic-replace correctness tested** per locked decision §2.7. Test must verify the temp-file-then-rename pattern handles partial-write scenarios (e.g., crash mid-write leaves no orphaned temp files in the archive directory; only complete writes survive).
10. **Test count baseline pinned** at plan-time (`python -m pytest -m "not slow" -q` output).
11. **Plan passes copowers:writing-plans Codex review cycle:** iterate to `NO_NEW_CRITICAL_MAJOR` with verification round if final round had findings.

---

## §7 Adversarial review watch items (for Codex during writing-plans cycle)

These are the high-likelihood failure modes Codex should specifically check. Pre-empt by self-checking BEFORE each plan-task draft:

1. **Multi-path coverage.** Per the multi-path-ingestion lesson (2026-04-29). PriceFetcher, pipeline/ohlcv.py, OhlcvCache all need the archive-aware helper. Plan task body must enumerate all three consumers; tests cover all three.

2. **Atomic-replace correctness.** Per locked decision §2.7. Test must construct a partial-write scenario AND verify recovery. Vacuous tests (e.g., "happy path completes") would miss the canonical atomic-replace failure mode (orphaned temp file after crash).

3. **Migration script idempotency.** Re-running the migration script (e.g., after operator interrupts mid-migration) must NOT corrupt the archive. Plan task body must specify the idempotency contract + test it.

4. **yfinance gotcha compliance.** Per CLAUDE.md gotchas: `threads=False` on `yf.download()`; `Ticker.history()` does NOT accept `threads=`; MultiIndex column squeeze. Plan task body for the wrapper helper must address all three.

5. **Cache-coherence semantic correctness.** Per locked decision §2.2. The "read archive; check freshness; fetch gap" rule must be discriminately tested for each branch (cache hit; stale; weekly-refresh-due; new ticker; partial-archive). Compounding-confound risk: a test that asserts "right answer returned" without exercising the freshness check would be vacuous.

6. **Backward-compat of PriceFetcher API.** Existing call sites (`swing/cli.py:127, 274`; `swing/pipeline/runner.py:146`; `swing/weather/runner.py:15`) consume `PriceFetcher.get(ticker, lookback_days, as_of_date=None)`. The refactor must preserve this signature. Plan task body specifies a compat-test asserting all existing call sites continue to work.

7. **Toml-shadowing audit.** Per locked decision §2.5. Codex will check whether the plan task body specifies the audit step.

8. **Discriminating-test discipline for the migration script.** Setup must use a fixture with KNOWN per-as-of-date files of varying contents; assertion verifies the consolidated per-ticker file contains the union of unique date rows AND old files are deleted. Vacuous test: "consolidated file exists" without content verification.

9. **Migration script's atomicity contract under interruption.** What happens if the script is killed mid-migration? Discriminating test: kill the script after 50% of tickers are migrated; restart; verify the half-migrated state is correctly reconciled (either resume from the partial state OR fresh-start safely — plan picks one).

10. **OhlcvCache hydration discriminating-test.** Cold-start scenario: empty in-memory cache + warm disk archive → hydration test. Warm-cache scenario: in-memory hit takes precedence over disk archive (no disk read). Vacuous test that doesn't distinguish these would miss the OhlcvCache backing's whole purpose.

---

## §8 Done criteria

- Plan committed to `docs/superpowers/plans/2026-04-29-ohlcv-archive-consolidation-plan.md`.
- Plan passes `copowers:writing-plans` Codex review cycle, terminating at `NO_NEW_CRITICAL_MAJOR` with verification round if final round had findings.
- All Major findings RESOLVED-by-fix; ACCEPTED-with-rationale only if genuinely out-of-scope.
- Test count baseline pinned in plan body.
- Per-task observable-verification step included in each task body.
- Per-task discriminating-test sanity-check sentence included where applicable.
- All 4 source files (per §4 + research-cache precedent) mapped to plan tasks; no orphaned files.
- Migration script is plan Task 1.

---

## §9 Return report format

Post as final message:

```
## OHLCV Archive Consolidation Plan — Writing-Plans Return Report

**Plan committed at:** docs/superpowers/plans/2026-04-29-ohlcv-archive-consolidation-plan.md (commit <SHA>)
**Codex rounds:** N rounds, terminating at NO_NEW_CRITICAL_MAJOR (with verification round if applicable)
**Test baseline pinned:** <count> fast tests at HEAD <SHA>
**Plan task count:** <N tasks>
**Files mapped:** <count> files / <count> tests

**Codex findings dispositioned:**
- R1: <count> Critical, <count> Major, <count> Minor — <breakdown>
- R2: ...
... (per round)

**Major design choices made (per §3 open design questions):**
- A. Metadata encoding: <answer>
- B. Archive directory location: <answer>
- C. yfinance-fetch wrapper signature: <answer>
- D. Test surface: <summary>
- E. Test baseline: <count> at HEAD <SHA>

**Open questions for orchestrator triage:**
- <any items the implementer flagged as needing operator/orchestrator decision before executing-plans dispatch>

**Recommended next dispatch:** copowers:executing-plans on this plan.
```

---

## §10 If you get stuck

- **If a locked decision (§2) appears impossible to plan as written:** STOP, surface in return report. Do NOT silently re-design.
- **If a precedent file path doesn't resolve:** Use `Glob` / `Grep` to find the actual current path. Pre-dispatch survey may have stale references.
- **If Codex round count exceeds 5 without convergence:** STOP, surface in return report with the unresolved finding. Do NOT iterate indefinitely.
- **If the final Codex round produces findings that resolve:** run ONE verification round to confirm clean before terminating.
- **If discriminating-test sanity check reveals vacuousness on a primary-key assertion:** STOP, restructure the test setup, then resume.
- **If migration-script design surfaces an unresolved corner case** (e.g., what to do with pre-existing `*.meta.json` files; what if the prices-cache contains files for tickers with renames/delistings): SURFACE in return report; operator decides. Do NOT silently choose for the operator.

---

## Appendix A: Research-cache precedent

`~/swing-data/research-cache/ohlcv/` contains 92 MB across 2,603 ticker files in the per-ticker parquet pattern. The research-branch harness uses this pattern; production paths don't consume it (yet). The architectural model for V1 §1.

If the writing-plans implementer wants to inspect the research-cache pattern in detail, they can read research-branch consumer code (e.g., `research/parity/run.py`'s `_CountingPriceFetcher` wrapper) — but the brief assumption is that the existing pattern is good enough to mirror without major modification. Plan can refine if specific aspects need adjustment.

---

## Appendix B: Cross-references

- **`docs/phase3e-todo.md`** §"2026-04-28 OHLCV archive consolidation" — backlog source.
- **CLAUDE.md** yfinance gotchas + `os.replace` Windows gotcha — load-bearing for the wrapper + migration script.
- **`docs/orchestrator-context.md`** "Lessons captured" — particularly multi-path-ingestion (2026-04-29); transactional snapshot semantics; bug-class durability vs scope-of-closure.
- **`~/swing-data/prices-cache/`** (operator's machine; not in repo) — current 5,521-file state; migration target.
- **`~/swing-data/research-cache/ohlcv/`** (operator's machine; not in repo) — per-ticker parquet precedent.
- **`swing/prices.py PriceFetcher`** — primary refactor target.
- **`swing/pipeline/ohlcv.py`** — wrap-target for V1 §2.
- **`swing/web/ohlcv_cache.py OhlcvCache`** — backing-target for V1 §3.
