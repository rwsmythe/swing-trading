# Post-Session-2c Housekeeping Bundle — Implementer Dispatch Brief

**Audience:** Fresh Claude Code instance with no prior conversation context.
**Mission:** Five commits closing tracking and methodology drift accumulated across orchestrator sessions and Session 2c. No new feature work. Adversarial review on the harness-fix commits only (C0–C2 are docs-only).
**Expected duration:** 60–90 minutes.
**Prepared:** 2026-04-24 by orchestrator instance.

---

## 0. Read first

1. `CLAUDE.md` — project conventions, conventional-commits + no-Claude-co-author + no-amend rules, TDD discipline.
2. Session 2c's return report context — most recently committed work. Reference commits: `0b62844` (D0), `0e04079` (D1 pre-reg), `e5510a8` (D3 study run), `48320c8` (D4 evidence summary), `3767639` (D5 review fixes). Session 2c documented two harness-level deferrals (Open Issues §3 and §4) that this housekeeping addresses.
3. `research/harness/earnings_proximity/` — the full harness from Sessions 2b/2c. C3 and C4 modify `fetchers.py`.
4. `research/studies/earnings-proximity-exclusion.md` — has an existing `## Amendments` section (added 2026-04-24 with the survivorship-bias entry); C1 appends a second bullet.
5. `research/studies/earnings-proximity-exclusion-results.md` — Session 2c's evidence summary, for context on what the activation-rate lesson refers to.
6. `reference/Future Work/QuantEcon/` — four untracked files that C0 stages. Read at least the program doc + the trigger-purpose-three-branch companion to understand what's being committed.

**Skill posture.**
- Do NOT invoke `copowers:brainstorming` or `copowers:writing-plans`. This is execution.
- Invoke `superpowers:test-driven-development` for C3 and C4 (regression tests required for both harness fixes).
- Invoke `superpowers:verification-before-completion` before declaring done.
- After C3+C4 land, invoke `copowers:adversarial-critic` on the combined harness-fix diff per §5. C0/C1/C2 are docs-only and skip review.

---

## 1. Scope — 5 commits

| # | Commit | Kind |
|---|--------|------|
| C0 | Track untracked drift: `docs/Bugs.txt` (Bug 7 addition), 4 QuantEcon folder files, this brief itself | Docs |
| C1 | Append forward-looking study-design amendment: filter-rule activation-rate sanity check | Docs |
| C2 | Reconstruct + commit Session-2c session-internal scripts to `research/harness/earnings_proximity/scripts/` | Docs (scripts are reference, not run) |
| C3 | Harness fix: strip pre-IPO NaN rows in OHLCV fetcher | Code + regression test |
| C4 | Harness fix: `fetchers._covers()` handles future-dated `fetch_end` correctly | Code + regression test |

### Explicitly out of scope

- Pipeline-linkage bundle (separate operational session, dispatched after this lands).
- Candidate-sparsity diagnostic study (separate applied-research session, dispatched after this lands).
- Any new feature work, schema change, or migration.
- Any change to `swing/*` (consumed read-only).
- Any change to the Session 2c committed artifacts (raw outputs, evidence summary, decision are immutable per pre-registration discipline).

---

## 2. Binding conventions

- **Branch:** `main`.
- **Commits:** conventional-commits. **No Claude co-author footer. No `--no-verify`. No amending.**
- **TDD:** C3 and C4 each get a failing-test-first cycle.
- **Tests:** fast suite green after every commit. Baseline going in: 623 passing.
- **Ruff:** no new violations beyond baseline 81. New `research/` code may follow looser patterns than `swing/` per Session 2b precedent; narrow `# noqa` with reasons if needed.
- **Phase isolation:** N/A — only `research/` and `docs/` are touched.

---

## 3. Task specifications

### C0 — Track untracked drift

**Files to stage:**

- `docs/Bugs.txt` — modified (orchestrator added Bug 7 about today_decisions vs chart-scope mixed-anchors; uncommitted since orchestrator made the edit).
- `reference/Future Work/QuantEcon/2026-04-24-quant-econ-future-research-program.md` — untracked (developer-authored future-research program doc).
- `reference/Future Work/QuantEcon/2026-04-24-quant-econ-companion-trigger-purpose-three-branch.md` — untracked (orchestrator-authored Path A vs Path B + three-branch companion).
- `reference/Future Work/QuantEcon/2026-04-24-quant-econ-companion-ai-inference-benchmark.md` — untracked (orchestrator-authored AI-era crowding metric companion).
- `reference/Future Work/QuantEcon/external-references.md` — untracked (orchestrator-authored external-references pointer file).
- `docs/post-2c-housekeeping-brief.md` — untracked (this brief itself).

**Verify before staging** that no other untracked files have appeared:

```bash
git status
```

Expected output should match the file list above. If other untracked files appear, flag in the return report — do not silently stage. (One known exception: `research/harness/earnings_proximity/smoke-out/` and `full-run-out/` are gitignored and may show as untracked-in-stat-summary depending on git config; verify they're gitignored before worrying.)

**Stage and commit:**

```bash
git add docs/Bugs.txt \
        reference/Future\ Work/QuantEcon/2026-04-24-quant-econ-future-research-program.md \
        reference/Future\ Work/QuantEcon/2026-04-24-quant-econ-companion-trigger-purpose-three-branch.md \
        reference/Future\ Work/QuantEcon/2026-04-24-quant-econ-companion-ai-inference-benchmark.md \
        reference/Future\ Work/QuantEcon/external-references.md \
        docs/post-2c-housekeeping-brief.md
```

(Adjust path quoting per shell. PowerShell on Windows may need different escaping for the space in `Future Work`.)

**Commit message:**

```
docs: track post-Session-2c untracked drift

- docs/Bugs.txt: orchestrator-added Bug 7 (today_decisions vs chart-scope
  mixed-anchors; queued for pipeline-linkage bundle session).
- reference/Future Work/QuantEcon/: developer's future-research program doc
  + three orchestrator-authored companions (Path A/B + three-branch refinement,
  AI-inference benchmark with operator-drives framing, external references).
- docs/post-2c-housekeeping-brief.md: this dispatch brief.
```

### C1 — Forward-looking study-design amendment

**File to modify:** `research/studies/earnings-proximity-exclusion.md`

**Edit location:** the existing `## Amendments` section near the bottom. Currently has one bullet (the 2026-04-24 survivorship-bias protocol amendment). Append a second bullet immediately after, preserving the first:

```markdown
- **2026-04-24 — Forward-looking lesson from Session 2c (commits `0e04079` → `e5510a8` → `48320c8` → `3767639`): Filter-rule activation-rate sanity check.** Session 2c completed the study with `defer` outcome and discovered post-hoc that the variant filter was a structural no-op on the chosen universe — minimum signal-to-earnings gap was ~16 trading days, exceeding the widest blackout tested (X=10). The decision was correct under the pre-registered protocol (anti-rationalization clause held; defer reached via combined-rule default branch when gap metrics were non-estimable), but the study could not test what it was designed to test. Going forward, any filter-rule study (this one's future iterations or other filter-rule studies) should pre-register a rule-activation-rate sanity check: the most aggressive variant must filter ≥10% of signals for the variant comparison to be meaningful. If activation falls below threshold during a study run, the result is a study-design finding, not an efficacy finding, and the design should be re-evaluated before re-running. **This amendment captures a forward-looking lesson; it does not modify Session 2c's pre-registration or decision (both immutable per pre-registration discipline).**
```

Do not modify any other section of the file.

**Commit message:**

```
docs(research): forward-looking study-design amendment — filter-rule activation-rate sanity check

Captures lesson from Session 2c: the variant filter was a structural no-op
on the chosen universe (no signal had earnings within X=10 trading days).
Future filter-rule studies should pre-register a rule-activation-rate
sanity check (most aggressive variant must filter ≥10% of signals).
Forward-looking only; does not modify Session 2c's pre-registration or
decision.
```

### C2 — Reconstruct session-2c session-internal scripts

Session 2c used three unversioned scripts at the repo root, deleted at session close:

- `_warm_cache_session2c.py` — bulk yfinance fetch for SPX+NDX universe (~516 tickers) + SPY benchmark over the 2024-04-19 → 2026-04-23 window
- `_run_full_study_session2c.py` — calls `run_replay()` for the full study, applies the per-ticker `dropna(subset=["Open","High","Low","Close"])` preprocess (which C3 will move into the harness), runs all 5 variants {0, 3, 5, 7, 10}, computes metrics
- `_compute_cis_session2c.py` — computes confidence intervals from the metrics output (bootstrap with seed `20260424` per `analysis_summary.json`)

**Reconstruct these from documented artifacts** rather than from the deleted versions. Sources:

- `analysis_summary.json` (committed in `e5510a8`) — contains deterministic seed (`20260424`), bootstrap config, variant list, window dates.
- `outcomes.csv`, `variant_membership.csv` (committed in `e5510a8`) — output shape that the scripts produce.
- `research/harness/earnings_proximity/run.py` and the `run_replay()` API surface — behavioral interface.
- Session 2c return report's description of each script's role.

**Target location:** `research/harness/earnings_proximity/scripts/` with files renamed as historical session artifacts:

```
research/harness/earnings_proximity/scripts/
├── README.md
├── session2c_warm_cache.py
├── session2c_run_full_study.py
└── session2c_compute_cis.py
```

**README.md content** (suggested structure; adapt as needed):

```markdown
# Session-snapshot scripts

These scripts reproduce specific historical research-branch sessions. They are NOT the canonical interface for running the harness — that is `python -m research.harness.earnings_proximity.run` per the parent README. These exist for procedural reproducibility of committed evidence summaries.

## Sessions captured

- **session2c_*.py** — Session 2c (committed 2026-04-24, evidence summary at `../../studies/earnings-proximity-exclusion-results.md`). Reproduces the metrics in commit `e5510a8`'s `analysis_summary.json` against the cache state at `~/swing-data/research-cache/`. Note: `session2c_run_full_study.py` includes a per-ticker `dropna()` preprocess that was a session-level workaround for pre-IPO NaN padding from yfinance batch output. The permanent harness fix landed in commit `<C3 SHA>` so future runs do not need this preprocess.

## Reproducibility expectation

Running `session2c_*` scripts against the same cache state SHOULD reproduce the committed metrics byte-identically (deterministic seed; deterministic bootstrap; deterministic study run). If they do not, that is a finding worth investigating before trusting the script for any further use.
```

**Acceptance:**
- Scripts are readable and runnable; they import from `research.harness.earnings_proximity.run` rather than duplicating the harness logic.
- A note in each script's docstring identifies it as a session-snapshot, not the canonical interface.
- README is present and explains the scripts' role.
- **Reproducibility test:** running `session2c_run_full_study.py` against the current cache produces metrics that match `analysis_summary.json` byte-for-byte for deterministic fields (variant counts, signal counts, bootstrap-config-derived CI bounds). If reconstruction can't achieve byte-identical reproduction, document the gap in the README and flag in the return report — do not block the commit.
- The scripts' own correctness is NOT tested via pytest — they are reference artifacts, not production code.

**Commit message:**

```
feat(research): elevate Session 2c session-internal scripts to committed historical artifacts

Reconstructs three session-internal scripts (warm_cache, run_full_study,
compute_cis) from analysis_summary.json + raw artifacts + run_replay() API.
Lives at research/harness/earnings_proximity/scripts/ as historical
reference (not canonical interface). README disambiguates role and
documents reproducibility expectation against commit e5510a8 outputs.

Closes Session 2c return-report Q3 (whether to elevate session-internal
scripts to committed status).
```

### C3 — Harness fix: pre-IPO NaN dropna in OHLCV fetcher

**Background.** `yf.download(tickers=..., start=..., end=..., threads=False, group_by='ticker')` pads any ticker that didn't exist at `start` with NaN rows back to the window start. Session 2c hit this on 8 tickers and worked around it with a per-ticker `dropna(subset=["Open","High","Low","Close"])` preprocess in the D3 driver. Permanent fix is to do the dropna at the harness fetcher layer so all future studies inherit it.

**File to modify:** `research/harness/earnings_proximity/fetchers.py`

**Change:** in `load_ohlcv` (and `load_ohlcv_with_stats` if separate), after the `yf.download(...)` call returns and per-ticker DataFrames are sliced from the MultiIndex, apply `dropna(subset=["Open","High","Low","Close"])` per ticker before caching. Index column (date) is preserved; only rows with NaN in any of the 4 OHLC columns are dropped (Volume can be NaN legitimately for certain holidays/halts).

**Suggested implementation pattern** (adapt to existing structure):

```python
# After per-ticker slice from MultiIndex, before cache write:
df = df.dropna(subset=["Open", "High", "Low", "Close"])
if df.empty:
    # Ticker has no data in window; skip caching, log as missing
    ...
```

**Test:** add `test_load_ohlcv_drops_pre_ipo_nan_rows` (or similar) in the existing fetchers test file. Use a synthetic DataFrame with leading NaN rows + valid trailing rows; assert `load_ohlcv` returns the trailing rows only.

**Acceptance:**
- New regression test passes.
- All pre-existing fetchers tests still pass.
- Cache is NOT invalidated — existing cached parquets remain valid; the change applies only at fetch time.
- A second test verifies that an entirely-NaN frame (ticker with no data in window) is handled gracefully — return None or empty DataFrame, not a crash.

**Commit message:**

```
fix(research): strip pre-IPO NaN rows in harness OHLCV fetcher

yf.download(group_by='ticker') pads tickers that didn't exist at the
window start with NaN rows back to the window start. Session 2c hit this
on 8 tickers and worked around it in a session-internal D3 driver. This
moves the dropna(subset=["Open","High","Low","Close"]) preprocess into
the harness fetcher so all future studies inherit the fix.

Closes Session 2c Open Issues §4. Cache is not invalidated; change
applies at fetch time only.
```

### C4 — Harness fix: `fetchers._covers()` handles future-dated `fetch_end`

**Background.** Session 2c noted: "fetchers._covers() always reports 'not covered' when fetch_end is in the future (Open Issues §3 — wasted ~7 minutes per run; behavior-correct)." When the requested `fetch_end` is beyond yfinance's available data, the function fails the coverage check even though the cache covers everything that's available, triggering an unnecessary refetch.

**File to modify:** `research/harness/earnings_proximity/fetchers.py`

**Change:** in `_covers()` (and any sibling helpers), when comparing `fetch_end` against cached data range, treat the comparison as satisfied if cached data extends to at least the most recent business day before `min(fetch_end, today)`. Specifically: if `fetch_end > today`, clamp the effective comparison endpoint to `today` (or the most recent business day, depending on existing behavior).

**Test:** add `test_covers_returns_true_when_fetch_end_is_future_and_cache_covers_today` (or similar). Use a fixture cache that covers up through "today" (mock `date.today()` if needed), request `fetch_end = today + 30 days`; assert `_covers()` returns True.

**Acceptance:**
- New regression test passes.
- All pre-existing fetchers tests pass.
- No behavioral change for `fetch_end ≤ today`.
- Edge case: empty cache + future `fetch_end` should still return False (no coverage).

**Commit message:**

```
fix(research): fetchers._covers() handles future-dated fetch_end correctly

Previously _covers() returned False when fetch_end was beyond yfinance's
available data, triggering unnecessary refetches (~7 minutes wasted per
session-2c-equivalent run). Now treats the comparison as satisfied when
cached data covers up through min(fetch_end, today).

Closes Session 2c Open Issues §3.
```

---

## 4. Adversarial review (after C3 + C4 land)

Run on combined harness-fix diff:

```bash
git diff <C2-SHA>..HEAD -- research/harness/earnings_proximity/
```

Invoke `copowers:adversarial-critic` (or follow the Session 2/3/2b/2c precedent — Codex MCP review; iterate until `NO_NEW_CRITICAL_MAJOR`). Watch items the reviewer is likely to probe:

- Edge cases in NaN handling: all-NaN frame? Mixed-NaN frame (some rows NaN, others valid)? Volume-NaN-but-OHLC-valid (legitimate holiday/halt — should NOT drop)?
- Edge cases in `_covers()`: empty cache? Cache start after `fetch_end`? Cache covers partial window only?
- Interaction with caching layer: does the dropna-then-cache pattern leave caches inconsistent if a re-fetch occurs (e.g., new cache write strips NaN; old cache write didn't)?
- Test coverage: do the tests actually distinguish pre-fix from post-fix behavior? Per `memory/feedback_regression_test_arithmetic.md`, vacuous tests don't help.

Fix findings in a new commit (C5) per the no-amend rule. ACCEPTED-with-rationale findings are documented in the return report.

---

## 5. Done criteria

- C0 + C1 + C2 + C3 + C4 (+ C5 if needed) all shipped.
- Fast suite green after every commit. Final count: 623 + new regression tests.
- No new ruff violations.
- Adversarial review: `NO_NEW_CRITICAL_MAJOR` verdict.
- Return report produced.

---

## 6. Return report format

```
## Post-Session-2c housekeeping return report

### Commits landed
- <SHA> docs: track post-Session-2c untracked drift                                  (C0)
- <SHA> docs(research): forward-looking study-design amendment — activation-rate     (C1)
- <SHA> feat(research): elevate Session 2c session-internal scripts                  (C2)
- <SHA> fix(research): strip pre-IPO NaN rows in harness OHLCV fetcher               (C3)
- <SHA> fix(research): fetchers._covers() handles future-dated fetch_end correctly   (C4)
- <SHA> fix(research): address housekeeping adversarial-review findings              (C5 — if needed)

### Tests
- Before: 623 passing, 0 failing.
- After: <N> passing, 0 failing. New tests: <M> (C3: <X>; C4: <Y>; C5: <Z>).

### Ruff
- No new violations (baseline 81 unchanged), OR: <list of narrowly-scoped # noqa with reasons>.

### C2 reproducibility status
- session2c_run_full_study.py reproduces e5510a8's metrics: <byte-identical | within tolerance, deltas listed | could not reproduce, gap documented in README>.
- If not byte-identical, what diverged and why.

### Adversarial review — summary
- Rounds: <N>
- Base SHA reviewed: <C2 SHA>
- Thread ID: <Codex MCP>
- Findings: <N> critical / <N> major / <N> minor
- FIXED: <short summary>
- ACCEPTED-with-rationale: <short summary>
- Verdict: NO_NEW_CRITICAL_MAJOR at Round <N>

### Other untracked files discovered
<List anything orchestrator should know about. Empty if C0's pre-stage git status matched expectations.>

### Open questions for orchestrator
<Empty if none.>
```

---

## 7. If you get stuck

- If C2's reconstruction can't byte-identically reproduce `e5510a8`'s outputs, document the gap in the README and the return report; ship the reconstruction anyway. Procedural reproducibility (scripts that run, with documented caveats) is better than no scripts at all.
- If `_covers()` has a deeper structural issue (e.g., the cache-format vs query-shape mismatch that produced the wasted-7-min behavior is symptomatic of something else), flag in the return report rather than expanding scope. C4's fix is the minimum-viable patch; structural redesign is out of scope.
- If a test you write passes under both pre-change and post-change code, rewrite it (`memory/feedback_regression_test_arithmetic.md`).
- If the QuantEcon folder has more files than the four listed in C0 (the developer or orchestrator may have added something between brief drafting and dispatch), stage all of them and note in the return report rather than skipping them.
