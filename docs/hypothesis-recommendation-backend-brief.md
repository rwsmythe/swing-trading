# Hypothesis Recommendation Engine — Backend (Session 1) Brief

**Audience:** Fresh Claude Code instance with no prior conversation context.
**Mission:** Build the backend for an active hypothesis-investigation recommendation engine. Per pre-registered hypothesis investigation plan v0.1: maintain a `hypothesis_registry` table; classify candidates against active hypotheses (matcher); rank candidates by hypothesis-investigation value (prioritizer); compute per-hypothesis tripwire status; extend `swing journal review` to show per-hypothesis progress. **No UI work in this session** — that's Session 2 (parallel brief, dispatched after this returns). Phase 2 carve-out scoped to specific files.
**Expected duration:** ~1 session (3-4 hours).
**Prepared:** 2026-04-25 by orchestrator instance.

---

## 0. Read first

1. `CLAUDE.md` — project conventions.
2. `docs/orchestrator-context.md` — particularly §"Recent decisions and framings" 2026-04-25 entries on operational-branch as evidence-generation, A+-vs-trades discipline, identification-rate recalibration, sub-A+ trading is operator's actual practice. **Critical context** — this brief implements the active hypothesis-investigation engine that those framings imply.
3. `research/studies/finviz-pool-binding-constraints.md` — Finviz study findings; doctrine-defensible miss set frozen at D1 is `(TT8_rs_rank, risk_feasibility, proximity_20ma)`. Reuse this set in the matcher.
4. `swing/data/migrations/` — read all migrations 0001-0007 to understand schema evolution. New migration 0008 adds `hypothesis_registry`.
5. `swing/data/repos/trades.py` — existing repo with `hypothesis_label` column (added in migration 0007). Per-hypothesis sample counts come from joining trades on `hypothesis_label`.
6. `swing/journal/stats.py` — existing aggregation module (extended by hypothesis-label work to add `compute_hypothesis_breakdown`). You'll extend further with per-hypothesis progress vs target.
7. `swing/evaluation/` (read-only) — to understand bucket logic + criterion structure.

**Skill posture.**
- DO invoke `superpowers:verification-before-completion` before declaring done.
- DO invoke `copowers:adversarial-critic` after task commits land. Watch items in §6.
- Do NOT invoke `copowers:brainstorming` or `copowers:writing-plans`.

---

## 1. Strategic context (compressed)

Per orchestrator-context.md 2026-04-25, the operator has committed to evidence-generation via hypothesis-tagged trades. The hypothesis-label infrastructure (migration 0007 + entry CLI flag + journal review aggregation) shipped earlier today, but the operator's framing today went further: **don't just suggest free-text labels; ACTIVELY recommend trades against a frozen hypothesis investigation plan, with tripwire safeguards.**

This brief implements the backend for that engine: registry table + matcher + prioritizer + tripwire compute + journal extension. Session 2 (separate brief) implements the UI surface (dashboard recommendations + CLI entry pre-fill). Both are needed before Monday market opening for hypothesis-driven trade recommendations to be ready.

**Pre-registered hypothesis investigation plan v0.1 (frozen at this brief):**

| ID | Name | Statement | Target sample | Decision criteria |
|---|---|---|---|---|
| 1 | A+ baseline | Production A+ candidates produce positive expectancy | 20 closed | Mean R-multiple > 0; lower-bound Wilson CI on win rate > 30% |
| 2 | Near-A+ defensible: extension test | Watch-bucket candidates failing ONLY `proximity_20ma` produce edge within 25% of A+ baseline | 10 closed | Mean R-multiple within 25% of A+ baseline mean |
| 3 | Sub-A+ VCP-not-formed | Watch-bucket candidates failing `tightness` OR `vcp_volume_contraction` (base-not-formed) produce reliable losses validating framework discipline. VIR is sample 1. | 5 closed | Confirm negative mean R-multiple |
| 4 | Capital-blocked: smaller-position test | Candidates A+ except `risk_feasibility`, taken with smaller-than-standard position size | 5-10 closed | Mean R-multiple positive; defensibility of smaller-position approach |

**Tripwire conditions (frozen — pre-registered):**

For each hypothesis, two tripwire conditions; either firing triggers operator evaluation (NOT auto-replacement):

1. **Consecutive max-loss tripwire** — N consecutive trades exit at ≤ -1R:
   - Target ≤ 5 samples: 3 consecutive -1R
   - Target 6-10 samples: 4 consecutive -1R
   - Target 11-20 samples: 5 consecutive -1R
2. **Absolute-loss tripwire** — cumulative realized loss across hypothesis trades exceeds 5% of starting equity ($375 at $7,500 capital).

When either fires, the hypothesis status surfaces as `tripwire_fired` in journal review and (in Session 2) on the dashboard. Operator can mark the hypothesis as `paused` or `closed-escaped` via a dedicated CLI command (added in this brief).

---

## 2. Scope

### In scope (Phase 2 carve-out granted to these files)

- **Migration 0008:** new `hypothesis_registry` table per §3.1.
- **`swing/data/models.py`:** new `HypothesisRegistryEntry` dataclass.
- **`swing/data/repos/hypothesis.py`:** new repo module with `seed_initial_hypotheses`, `list_hypotheses(status_filter=None)`, `get_hypothesis(id)`, `update_hypothesis_status(id, new_status, reason)`, `compute_hypothesis_progress(id, conn)` returning `HypothesisProgress` dataclass.
- **`swing/recommendations/hypothesis.py`:** new compute module with: `match_candidate_to_hypotheses(candidate, all_criteria_results, doctrine_defensible_set, registry) -> list[HypothesisMatch]`, `prioritize_recommendations(matches, registry) -> list[CandidateRecommendation]`, `compute_tripwire_status(hypothesis_id, conn) -> TripwireStatus`.
- **`swing/journal/stats.py`:** extend with `compute_hypothesis_progress_breakdown` — per-hypothesis n/N, mean R, win rate, tripwire status. Renders in `swing journal review` output as a new section AFTER existing hypothesis breakdown.
- **`swing/cli.py`:** new commands `swing hypothesis list`, `swing hypothesis status <id>`, `swing hypothesis update <id> --status <paused|closed-escaped|active> --reason "..."`. Status mutation requires `--reason`; recorded to a notes column on the registry row.
- **Tests:** across all the above.

### Out of scope (Session 2 territory)

- Dashboard VM extension or templates (Session 2 brief).
- `swing trade entry --hypothesis` pre-fill from suggested label (Session 2 brief).
- Watch-staging UI surface (Session 2 brief).
- Modification of the doctrine-defensible miss set (frozen at Finviz-pool study D1).
- Modification of the hypothesis investigation plan v0.1 (frozen at THIS brief).

---

## 3. Binding conventions

- **Branch:** `main`.
- **Commits:** conventional. **No Claude co-author footer. No `--no-verify`. No amending.**
- **TDD throughout.**
- **Tests:** trust pytest output. Baseline 822 at session start; may shift from parallel work.
- **Phase 2 carve-out:** GRANTED for migration 0008, models.py extension, repos/hypothesis.py (new), recommendations/hypothesis.py (new), journal/stats.py extension, cli.py extension.
- **Pre-registration:** the hypothesis investigation plan v0.1 in §1 is FROZEN. The migration's seed-data inserts these 4 hypotheses. Tripwire values frozen. Anti-rationalization applies — these are not negotiable post-data without an explicit operator-decision-recorded amendment process (which is itself out of scope for this brief).

---

## 4. Task specifications

### 4.1 Migration 0008 + model + repo + seed

`swing/data/migrations/0008_hypothesis_registry.sql`:

```sql
CREATE TABLE hypothesis_registry (
  id INTEGER PRIMARY KEY,
  name TEXT NOT NULL UNIQUE,
  statement TEXT NOT NULL,
  target_sample_size INTEGER NOT NULL CHECK (target_sample_size > 0),
  decision_criteria TEXT NOT NULL,
  status TEXT NOT NULL DEFAULT 'active'
    CHECK (status IN ('active', 'paused', 'closed-escaped', 'closed-target-met')),
  consecutive_loss_tripwire INTEGER NOT NULL CHECK (consecutive_loss_tripwire > 0),
  absolute_loss_tripwire_pct REAL NOT NULL CHECK (absolute_loss_tripwire_pct > 0),
  created_at TEXT NOT NULL,
  status_changed_at TEXT,
  status_change_reason TEXT,
  notes TEXT
);
CREATE INDEX ix_hypothesis_status ON hypothesis_registry(status);
```

**Seed data** inserted by the migration:

```sql
INSERT INTO hypothesis_registry
  (name, statement, target_sample_size, decision_criteria,
   consecutive_loss_tripwire, absolute_loss_tripwire_pct, created_at)
VALUES
  ('A+ baseline',
   'Production A+ candidates produce positive expectancy',
   20,
   'Mean R-multiple > 0; lower-bound Wilson CI on win rate > 30%',
   5, 5.0, '2026-04-25'),
  ('Near-A+ defensible: extension test',
   'Watch-bucket candidates failing ONLY proximity_20ma produce edge within 25% of A+ baseline',
   10,
   'Mean R-multiple within 25% of A+ baseline mean',
   4, 5.0, '2026-04-25'),
  ('Sub-A+ VCP-not-formed',
   'Watch-bucket candidates failing tightness OR vcp_volume_contraction produce reliable losses validating framework discipline',
   5,
   'Confirm negative mean R-multiple',
   3, 5.0, '2026-04-25'),
  ('Capital-blocked: smaller-position test',
   'Candidates A+ except risk_feasibility, taken with smaller-than-standard position size, produce positive expectancy',
   10,
   'Mean R-multiple positive; defensibility of smaller-position approach',
   4, 5.0, '2026-04-25');
```

`swing/data/models.py` adds `HypothesisRegistryEntry` dataclass mirroring the schema. `swing/data/repos/hypothesis.py` adds the repo functions.

TDD per repo function. Verify migration creates table + seeds 4 rows.

Commit: `feat(data): migration 0008 — hypothesis registry + initial v0.1 seed`.

### 4.2 Matcher compute

`swing/recommendations/hypothesis.py` — `match_candidate_to_hypotheses(candidate, criteria_results, doctrine_defensible_set, registry)`:

For each ACTIVE hypothesis in the registry, determine if the candidate matches:
- **A+ baseline:** candidate.bucket == 'aplus'
- **Near-A+ defensible: extension test:** candidate.bucket == 'watch' AND non-pass criteria == {'proximity_20ma'} AND nothing else
- **Sub-A+ VCP-not-formed:** candidate.bucket == 'watch' AND ('tightness' in non-pass OR 'vcp_volume_contraction' in non-pass) AND nothing in non-pass that's outside `(doctrine_defensible_set | {'tightness', 'vcp_volume_contraction'})`
- **Capital-blocked: smaller-position test:** candidate.bucket == 'watch' AND non-pass criteria == {'risk_feasibility'} AND nothing else

Returns `list[HypothesisMatch]` — usually 0 or 1 entry, occasionally 2 if a candidate fits multiple. Each `HypothesisMatch` has `hypothesis_id`, `suggested_label_descriptive` (e.g., "watch-bucket; failed: proximity_20ma; defensible-miss"), `priority_hint` (numeric).

TDD: cases for each hypothesis, edge cases (no matching active hypothesis; multi-match; closed hypothesis ignored).

Commit: `feat(recommendations): candidate-to-hypothesis matcher`.

### 4.3 Prioritizer

`prioritize_recommendations(matches, registry, current_progress)`:

Rank candidates by hypothesis-investigation value:
- Active hypotheses far from target sample size get higher priority
- Hypotheses with `tripwire_fired` status fall to bottom of list (operator should evaluate before more samples)
- Closed hypotheses produce no recommendations
- Within same hypothesis, candidates ordered by some stable signal (use match's `priority_hint`; ties broken by ticker alphabetical)

Returns `list[CandidateRecommendation]` ordered for display.

TDD.

Commit: `feat(recommendations): hypothesis-aware recommendation prioritizer`.

### 4.4 Tripwire compute

`compute_tripwire_status(hypothesis_id, conn) -> TripwireStatus`:

For the given hypothesis, compute:
- `consecutive_max_loss_streak`: count of trailing consecutive trades (by entry_date) under this hypothesis with R-multiple ≤ -1.0
- `cumulative_loss`: sum(realized_pnl) across all trades with this hypothesis_label
- `consecutive_tripwire_fired`: streak >= hypothesis.consecutive_loss_tripwire
- `absolute_tripwire_fired`: |cumulative_loss| / starting_equity >= hypothesis.absolute_loss_tripwire_pct / 100
- `any_tripwire_fired`: True if either above

Hypothesis identity: derived from matching `hypothesis_label` startswith the hypothesis name (since labels may have additional descriptive content). Use a stable matching rule documented in the function docstring.

TDD: cases covering all combinations (no trades; below tripwire; consecutive fired; absolute fired; both fired).

Commit: `feat(recommendations): per-hypothesis tripwire computation`.

### 4.5 Journal review extension

Extend `swing/journal/stats.py` with `compute_hypothesis_progress_breakdown(conn) -> list[HypothesisProgress]`. Each entry: hypothesis_id, name, target_sample, current_sample, mean_r_multiple, win_rate, tripwire_status, status.

Extend `swing journal review` rendering (in `swing/cli.py` or wherever journal renders) to append after the existing hypothesis breakdown:

```
## Hypothesis investigation progress
- A+ baseline (active): 0 / 20 samples
- Near-A+ defensible: extension test (active): 0 / 10 samples
- Sub-A+ VCP-not-formed (active): 1 / 5 samples; mean R: -0.33; (no tripwire)
- Capital-blocked: smaller-position test (active): 0 / 10 samples
```

When a tripwire fires:
```
- Sub-A+ VCP-not-formed (active, TRIPWIRE FIRED — 3 consecutive -1R; recommend escape evaluation): 3 / 5 samples; mean R: -0.95
```

TDD covering tripwire display.

Commit: `feat(cli,journal): hypothesis-progress section in journal review`.

### 4.6 Hypothesis CLI commands

`swing hypothesis list`: prints all hypotheses with id, name, status, n/N progress.

`swing hypothesis status <id>`: prints detailed status for one hypothesis (statement, decision criteria, current samples, tripwire status, decisions-recorded if any).

`swing hypothesis update <id> --status <new-status> --reason "..."`: updates status, requires `--reason`. Allowed transitions: active → paused, active → closed-escaped, paused → active, paused → closed-escaped, closed-escaped → active (operator decides to resume); active → closed-target-met (when target hit). Records change with timestamp + reason.

TDD: each command + each transition + invalid-transition rejection.

Commit: `feat(cli): hypothesis list/status/update commands`.

---

## 5. Adversarial review

After all task commits land, `copowers:adversarial-critic` on combined diff. Iterate to `NO_NEW_CRITICAL_MAJOR`. **Specific watch items:**

- **Migration safety.** ALTER TABLE is not used here (new table); CREATE TABLE is additive. Verify seed inserts run idempotently — re-running the migration on an existing DB should not duplicate (use INSERT OR IGNORE or check schema_version).
- **Matcher precision.** Verify that "non-pass criteria == {'proximity_20ma'}" excludes any `na` results — should `na` count as non-pass? Decision: yes, per the candidate-sparsity diagnostic's binding-constraint logic. Confirm in the matcher.
- **Hypothesis-label string matching.** Verify that the tripwire computation correctly identifies which trades belong to which hypothesis. Free-text labels make this fuzzy. Pattern: trades created via the recommendation engine carry a structured prefix (e.g., the hypothesis name); trades created with custom labels match by prefix or fail to match. Document the matching rule clearly.
- **Pre-registration anti-rationalization.** Verify that the hypothesis investigation plan v0.1 cannot be modified through the `swing hypothesis update` command — only `status` is mutable; `target_sample_size`, `consecutive_loss_tripwire`, `decision_criteria`, etc., cannot be changed via CLI. (They can be changed only via a new migration with explicit version-bump, signaling formal amendment.)
- **Status transition completeness.** Verify all status transitions are tested; verify the registry never enters an inconsistent state (e.g., status=closed but tripwire still surfaces in active recommendations).
- **Win-rate computation.** Verify it uses realized P&L > 0 as the win definition (consistent with existing journal review).

Fix major findings in NEW commits per no-amend rule.

---

## 6. Done criteria

- All task commits landed.
- Migration 0008 creates table + seeds 4 hypotheses.
- `swing hypothesis list` prints all 4 active hypotheses.
- `swing journal review` shows hypothesis-progress section with VIR contributing as 1/5 sample under "Sub-A+ VCP-not-formed" (the backfilled hypothesis_label starts with that name).
- Adversarial review verdict `NO_NEW_CRITICAL_MAJOR`.
- Fast suite green; trust pytest output.
- Return report per §7.

---

## 7. Return report format

```
## Hypothesis recommendation backend (Session 1) — return report

### Commits landed
- <SHA1> feat(data): migration 0008 — hypothesis registry + initial v0.1 seed
- <SHA2> feat(recommendations): candidate-to-hypothesis matcher
- <SHA3> feat(recommendations): hypothesis-aware recommendation prioritizer
- <SHA4> feat(recommendations): per-hypothesis tripwire computation
- <SHA5> feat(cli,journal): hypothesis-progress section in journal review
- <SHA6> feat(cli): hypothesis list/status/update commands
- <SHA7+> (if any) adversarial review fixes

### Tests
- Before: <baseline>
- After: <N>, 0 failing. New tests: <count>.

### Adversarial review verdict
- <NO_NEW_CRITICAL_MAJOR | findings summary>

### Verification
- `swing hypothesis list` output: <paste>
- `swing journal review` excerpt showing hypothesis-progress section: <paste>
- VIR (trade_id=1, hypothesis_label='sub-A+ VCP-not-formed test ...') correctly contributing to "Sub-A+ VCP-not-formed" hypothesis as 1/5 sample: <yes/no, explain>

### Deviations from brief
- <Empty if none.>

### Open questions for orchestrator
- <Empty if none.>
```

---

## 8. If you get stuck

- **If the hypothesis-label matching rule is unclear** for VIR (whose backfilled label is "sub-A+ VCP-not-formed test (proximity_20ma + tightness fails); inaugural trade test"): use case-insensitive substring match against hypothesis name's keywords ("VCP-not-formed" matches the "Sub-A+ VCP-not-formed" hypothesis). Document precisely. The matching rule itself is something the operator will iterate on as labels accumulate.
- **If a candidate fits multiple hypotheses** (e.g., A+ candidate that also has watchlist relevance): allow the matcher to return multiple matches; the prioritizer picks the most-investigation-valuable one. Document the choice.
- **If migration 0008 conflicts with an in-flight 0008 from parallel work**: use 0009; flag in return report.
