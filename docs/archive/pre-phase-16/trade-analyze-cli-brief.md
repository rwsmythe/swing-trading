# `swing trade analyze` Post-Hoc Trade Retrospective CLI — Phase 3e Brief

**Audience:** Fresh Claude Code instance with no prior conversation context.
**Mission:** Add a new CLI command `swing trade analyze <trade_id>` that produces a structured per-trade retrospective from existing production DB data. Joins `trades`, `exits`, `candidates`, `candidate_criteria`, `evaluation_runs` to surface: bucket-at-recommendation, criteria-failed-at-recommendation, days-recommendation-to-entry, entry-vs-pivot deviation, stop-vs-recommended, R-multiple, hold duration, hypothesis_label. Handles both production-recommended trades AND manually-sourced trades (those without a corresponding candidate row). Phase 3 only — no Phase 2 carve-out needed.
**Expected duration:** ~1 session (3 hours).
**Prepared:** 2026-04-25 by orchestrator instance.

---

## 0. Read first

1. `CLAUDE.md` — project conventions (conventional commits, no-amend, no `--no-verify`, no Claude co-author footer, Phase isolation, TDD, fast suite must stay green).
2. `docs/orchestrator-context.md` — particularly §"Currently in-flight work" describing the VIR case study (n=1 closed trade as of 2026-04-25). The case-study analysis the orchestrator did manually via Python+SQL is what this CLI tool automates and standardizes.
3. `swing/data/migrations/0001_phase1_initial.sql` lines 24–56 — `candidates` + `candidate_criteria` schema (per-(ticker, criterion) results).
4. `swing/data/migrations/0003_phase2_pipeline_trades.sql` — `trades` and `exits` schema.
5. `swing/data/migrations/0007_trade_hypothesis_label.sql` — adds `hypothesis_label` column to `trades`.
6. `swing/data/repos/trades.py` and `swing/data/repos/candidates.py` — existing read repos. Reuse rather than reimplement.
7. `swing/cli.py` — current CLI structure. You'll add a `swing trade analyze` subcommand under the existing `swing trade` group.
8. `swing/journal/stats.py` — existing pure-compute pattern. New `swing/journal/analyze.py` module mirrors this layout.

**Skill posture.**
- DO invoke `superpowers:verification-before-completion` before declaring done.
- DO invoke `copowers:adversarial-critic` after task commits land. Standing convention; iterate to `NO_NEW_CRITICAL_MAJOR`.
- Do NOT invoke `copowers:brainstorming` or `copowers:writing-plans` — scope is fully specified by this brief.

---

## 1. Strategic context (compressed)

The orchestrator manually ran a SQL+Python case study on the inaugural VIR trade (2026-04-25) by querying production DB tables and joining trades + exits + candidates + candidate_criteria. The exercise produced operationally-useful insights (chase entry, tightened-stop discipline, doctrine-classification of the trade as "sub-A+ VCP-not-formed test"). With more trades closing over time, doing this manually for each one is friction. **The CLI tool automates that exercise** — reproducible, structured, low-friction post-hoc analysis per trade.

This is also forward-compatible with the active hypothesis-recommendation engine being built in parallel (the hyp1+hyp2 sessions). Once trades carry hypothesis labels and the registry tracks per-hypothesis outcomes, this tool becomes a per-trade complement to the per-hypothesis aggregation in `swing journal review`.

---

## 2. Scope

### In scope (Phase 3 only — no Phase 2 carve-out needed)

- **New module:** `swing/journal/analyze.py` — pure compute. Input: trade_id (int). Output: `TradeAnalysis` dataclass containing all the fields below. Uses existing repos (`fetch_trade_by_id`, `fetch_candidates_for_run`, etc.); no direct SQL outside repo helpers if avoidable.
- **CLI:** `swing trade analyze <trade_id>` subcommand. Renders the `TradeAnalysis` as structured text output to stdout (table-style for scannable reading; not JSON unless operator wants both — for now stdout text only).
- **Tests:** `tests/journal/test_analyze.py` for compute; `tests/cli/test_cli_trade_analyze.py` for CLI surface.

### Out of scope

- Web/dashboard surface for trade analysis. CLI only.
- Per-trade outcome aggregation across multiple trades (that's `swing journal review` and the hyp1 work).
- Trade-outcome predictions or recommendations. Descriptive only.
- yfinance OHLCV fetch for the hold window (would let us compute trajectory; out of scope to keep this synchronous + no-network).
- Modification of any existing module beyond CLI registration.
- Output format flags (--json, --csv). Plain text only for v1.

---

## 3. Binding conventions

- **Branch:** `main`.
- **Commits:** conventional. **No Claude co-author footer. No `--no-verify`. No amending.**
- **TDD.**
- **Tests:** trust pytest output. Baseline 822 at session start; may shift due to parallel work.
- **Phase isolation:** Touch `swing/journal/`, `swing/cli.py` (or `swing/cli/trade.py`), `tests/journal/`, `tests/cli/`. NO `swing/data/` or `swing/trades/` modification.

---

## 4. Task specifications

### 4.1 `TradeAnalysis` dataclass + compute function

`swing/journal/analyze.py`:

```python
@dataclass(frozen=True)
class CriterionResultDisplay:
    layer: str             # 'trend_template' | 'vcp' | 'risk'
    criterion_name: str
    result: str            # 'pass' | 'fail' | 'na'
    value: str | None      # e.g., "close=10.33 150MA=6.97 200MA=6.50"
    rule: str | None

@dataclass(frozen=True)
class RecommendationContext:
    eval_run_id: int
    eval_run_action_session_date: str
    bucket: str
    pivot: float | None
    initial_stop: float | None
    close_at_eval: float | None
    rs_rank: int | None
    rs_return_12w_vs_spy: float | None
    pattern_tag: str | None
    notes: str | None
    criteria: tuple[CriterionResultDisplay, ...]

@dataclass(frozen=True)
class TradeAnalysis:
    trade_id: int
    ticker: str
    entry_date: str
    entry_price: float
    initial_shares: int
    initial_stop: float
    current_stop: float
    status: str
    hypothesis_label: str | None
    notes: str | None
    # Recommendation context: list of all evaluation_runs that recommended this ticker
    # before or on entry date (helpful when production saw the ticker on multiple days
    # leading up to entry). Empty list = manually-sourced trade.
    recommendations: tuple[RecommendationContext, ...]
    # Exit data: list of all exits (partial exits supported)
    exits: tuple[ExitDisplay, ...]
    # Computed deviations: only populated when at least one recommendation exists
    days_rec_to_entry: int | None
    pct_above_pivot: float | None  # entry_price vs latest-pre-entry recommendation pivot
    stop_dev_pct: float | None
    realized_pnl_total: float
    r_multiple_avg: float | None  # weighted avg if partial exits

def analyze_trade(conn: sqlite3.Connection, trade_id: int) -> TradeAnalysis:
    """Compose TradeAnalysis from production DB reads."""
```

**Logic notes:**
- **Manually-sourced trades** (no candidate rows for the ticker on or before entry_date): `recommendations` is empty tuple. Deviation fields (days_rec_to_entry, pct_above_pivot, stop_dev_pct) are None. The output remains useful — just lighter.
- **Multiple recommendations:** when production recommended the ticker on multiple evaluation_runs leading to entry (e.g., VIR's 4 runs on 2026-04-20), include all of them in `recommendations` list. Use the LATEST one (by run_ts ≤ entry_date) for the deviation computations.
- **Excluded-bucket recommendations** (production marked the ticker `excluded` with notes='open position' once it became a trade): these are NOT useful for analysis; filter them out. Only include buckets in `('aplus', 'watch', 'skip')`.

TDD: tests for each branching case (manually-sourced, single-rec, multi-rec, partial-exits, no-exits-yet, excluded-only).

Commit: `feat(journal): add analyze_trade compute function`.

### 4.2 CLI subcommand

`swing trade analyze <trade_id>`. Renders `TradeAnalysis` to stdout as structured sections:

```
TRADE #<id> — <ticker>
======================
Status: <status>
Entry: <entry_date> @ $<entry_price> × <initial_shares> sh
Initial stop: $<initial_stop>     Current stop: $<current_stop>
Hypothesis: <hypothesis_label or "(none)">
Notes: <notes or "(none)">

RECOMMENDATIONS (<N>)
---------------------
<For each recommendation, in chronological order:>
[<eval_run_id>] <action_session_date> — bucket=<bucket>
  pivot=$<pivot>  rec_stop=$<initial_stop>  close=$<close_at_eval>
  rs_rank=<rs_rank>  rs_vs_spy=<rs_return_12w_vs_spy>
  Failed criteria (<count>):
    <layer>/<criterion_name>: <value>  (<rule>)
  ... 
  All criteria passed in <layer>: <count>; <layer>: <count>; ...

(Or: "MANUALLY-SOURCED — no production recommendation in DB before entry_date")

EXITS (<N>)
-----------
<exit_date>: <shares> sh @ $<exit_price>  reason=<reason>  pnl=$<realized_pnl>  R=<r_multiple>

DEVIATIONS (vs latest pre-entry recommendation)
------------------------------------------------
Days from rec to entry: <N>
Entry % above pivot: <pct>%
Stop deviation vs recommended: <pct>%

OUTCOMES
--------
Realized P&L total: $<realized_pnl_total>
R-multiple (avg, if partial): <r_multiple_avg>
Hold duration: <days> days (entry to last exit)
```

Use existing CLI patterns (click). TDD: tests covering same branching as the compute function.

Commit: `feat(cli): add swing trade analyze subcommand`.

---

## 5. Adversarial review

After task commits land, `copowers:adversarial-critic` on the combined diff. Iterate to `NO_NEW_CRITICAL_MAJOR`. **Specific watch items:**

- **Multi-recommendation handling.** Production may have recommended the ticker on multiple runs before entry. Verify the "latest pre-entry" selection logic is correct — should be MAX(run_ts) WHERE run_ts <= entry_date_timestamp AND bucket NOT IN ('error', 'excluded').
- **Manually-sourced trade graceful handling.** Verify the tool produces useful output even when `recommendations` is empty (e.g., no crash on None pivot computations).
- **Partial-exits handling.** Verify R-multiple averaging is mathematically correct when shares-weighted (sum(shares × r_multiple) / sum(shares)).
- **Hypothesis_label NULL handling.** Existing pre-migration-0007 trades have NULL; render as "(none)" not crash.
- **SQL injection.** trade_id is int; verify CLI parses it as int (rejects strings).
- **DB read-only safety.** Verify the analyze function only reads; no UPDATE/INSERT/DELETE.

---

## 6. Done criteria

- Both task commits landed.
- `swing trade analyze 1` produces structured output for VIR trade matching the case-study findings (passes all 8 trend-template; fails proximity_20ma + tightness; entry $11.30 vs pivot $10.76 = 5.0% above; -0.33 R-multiple; etc.).
- Manually-sourced trade case handled gracefully (test asserts).
- Adversarial review verdict `NO_NEW_CRITICAL_MAJOR`.
- Fast suite green.
- Return report per §7.

---

## 7. Return report format

```
## swing trade analyze — return report

### Commits landed
- <SHA1> feat(journal): add analyze_trade compute function
- <SHA2> feat(cli): add swing trade analyze subcommand
- <SHA3+> (if any) adversarial review fixes

### Tests
- Before: <baseline>
- After: <N>, 0 failing. New tests: <count>.

### Adversarial review verdict
- <NO_NEW_CRITICAL_MAJOR | findings summary>

### Verification — VIR (trade_id=1) output
<Paste the actual `swing trade analyze 1` output here so the orchestrator can confirm it matches the manual case-study findings>

### Deviations from brief
- <Empty if none.>

### Open questions for orchestrator
- <Empty if none.>
```

---

## 8. If you get stuck

- **If a partial-exit shares-weighted R-multiple computation is ambiguous** (e.g., what if exits had differing reasons): use shares-weighted average; document the choice.
- **If the trade record's recommendation can't be matched** (entry_date is before any evaluation_run, or the candidates table doesn't have the ticker on the run that should have): treat as manually-sourced. Log a warning if the ticker DOES appear in candidates after entry (suggests timing weirdness; not necessarily a bug).
- **If existing CLI pattern uses click vs argparse vs something else**: match the existing pattern. The user-facing text is the operator surface; consistency matters.
