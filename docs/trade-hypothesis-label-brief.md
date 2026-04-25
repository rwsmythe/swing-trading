# Trade Hypothesis Label — Phase 3e Operational Change Brief

**Audience:** Fresh Claude Code instance with no prior conversation context.
**Mission:** Add a free-text `hypothesis_label` field to the trade-entry path so each operator-recorded trade can carry a frozen pre-trade hypothesis. Extend `swing journal review` to aggregate by hypothesis label when trades carry one. Strictly additive — existing trade-entry calls without `--hypothesis` continue to work; existing journal-review output is preserved unchanged with the hypothesis breakdown added alongside. Phase 2 carve-out scoped to specific files.
**Expected duration:** ~1 session (3–4 hours).
**Prepared:** 2026-04-25 by orchestrator instance.

---

## 0. Read first

1. `CLAUDE.md` — project conventions (conventional commits, no-amend, no `--no-verify`, no Claude co-author footer, Phase isolation, TDD discipline, fast-test-suite must stay green).
2. `docs/orchestrator-context.md` — particularly §"Recent decisions and framings" 2026-04-25 entries: framework framing, evidence gap framing, sub-A+ trading is operator's actual practice, **operational branch as evidence-generation surface** (the framing this brief implements). §"Anti-patterns to avoid" — particularly mid-session scope expansion, vacuous tests.
3. `swing/data/migrations/` — read all migrations 0001 through 0006 in order. **Identify which existing table records trade-entry events.** This is likely `trades` (in `0003_phase2_pipeline_trades.sql`) but may have evolved across migrations. The new `hypothesis_label` column goes on the table that records the entry event — verify via the migration history.
4. `swing/data/models.py` — current Trade dataclass (or equivalent). Your model extension must preserve existing field ordering; new field is appended with `None` default.
5. `swing/data/repos/trades.py` — existing entry-recording repo function. You'll extend its signature with the new optional parameter.
6. `swing/trades/` — entry service module. You'll extend the service signature similarly.
7. `swing/cli.py` (or `swing/cli/trade.py` and `swing/cli/journal.py` if CLI is split) — existing `swing trade entry` and `swing journal review` commands. You'll add `--hypothesis` flag to entry, and a hypothesis-breakdown to review output.
8. `swing --help` and `swing trade --help` and `swing journal --help` — current CLI shape, so the new flag fits idiomatically.

**Skill posture.**
- DO invoke `superpowers:verification-before-completion` before declaring done.
- DO invoke `copowers:adversarial-critic` after task commits land. Standing convention; iterate to `NO_NEW_CRITICAL_MAJOR`. Watch items in §5.
- Do NOT invoke `copowers:brainstorming` or `copowers:writing-plans` — scope is fully specified by this brief.

---

## 1. Strategic context (compressed)

The operator (per orchestrator-context.md 2026-04-25) is willing to take hypothesis-tagged sub-optimal trades within risk discipline, treating losses as cost-of-development to generate evidence for framework iteration. The operational branch shifts from "execute proven framework" to "execute candidate framework variations to generate evidence."

For that to produce analyzable data, each trade needs a frozen pre-trade hypothesis label. Examples of hypothesis classes the operator might use:

- "Sub-A+ candidate meeting TT + price threshold (VIS-style)"
- "A+ except risk_feasibility, smaller position than standard"
- "A+ except proximity_20ma, accepted late entry"
- "S&P 1500 universe-broadening test"

Free-text is the right initial design (per operator confirmation 2026-04-25): hypothesis classes have not yet stabilized; controlled vocabulary is premature. A future formalization (enum + validation) is a deferred follow-on once 5+ labeled trades reveal the natural categories.

The label is recorded at trade-entry time and is FROZEN — outcome-driven re-labeling is anti-pattern (the same anti-rationalization discipline as research-study pre-registration).

---

## 2. Scope

### In scope (Phase 2 carve-out granted to these files)

- **Migration:** add nullable `hypothesis_label TEXT` column to the trade-entry-recording table. New column has no default value; existing rows have `NULL`. Migration is forward-only; no rollback needed.
- **`swing/data/models.py`:** extend the relevant dataclass (likely `Trade` or `TradeEntry`) with `hypothesis_label: str | None = None`. Default `None` so existing constructors continue to work.
- **`swing/data/repos/trades.py`:** extend the entry-recording function's signature with `hypothesis_label: str | None = None` parameter; pass through to INSERT.
- **`swing/trades/` entry service:** extend service signature with `hypothesis_label: str | None = None`; pass through to repo.
- **`swing/cli/`:** add `--hypothesis TEXT` flag to `swing trade entry` (optional; default None); pass through to service. Add a hypothesis-breakdown section to `swing journal review` output: groups labeled trades by `hypothesis_label`; reports per-group count + sum P&L + (if ≥3 trades in group) win rate. Unlabeled trades grouped under `(no label)`. The breakdown appears AFTER the existing review output, not replacing it.
- Tests across all the above per TDD.
- Adversarial review pass on the combined diff.

### Out of scope

- **Backfill of historical trades.** The existing trade(s) (e.g., VIS) have NULL hypothesis_label. If the operator wants to retro-label, it's a one-off SQL UPDATE outside this commit's scope — do NOT include backfill scripts or migrations.
- **Controlled vocabulary / enum / validation of label values.** Free-text only. Future work.
- **Per-hypothesis advanced statistics** (expectancy intervals, R-multiples, etc.). MVP: count + sum P&L + win rate (when applicable).
- **Web dashboard surface** for hypothesis labels. CLI only for this commit. Web exposure is a separate Phase 3e candidate.
- **Modification of existing journal review fields or computations.** Existing output stays unchanged; hypothesis breakdown is additive.
- **Renaming or refactoring of any existing field, function, or class.** Strictly additive change.

---

## 3. Binding conventions

- **Branch:** `main`. No feature branch.
- **Commits:** conventional. **No Claude co-author footer. No `--no-verify`. No amending.**
- **TDD:** failing test first → see fail → minimal implementation → see pass → commit, per task. Multiple commits expected (one per logical change at minimum: migration commit, models+repo+service commit, CLI commit, journal-review commit). Use judgment on commit boundaries; don't over-fragment.
- **Tests:** `python -m pytest -m "not slow" -q` must stay green. **Trust pytest output, not the brief's baseline number** — there is parallel work (Finviz-pool analysis under `research/`) that may shift the baseline before or during your work. Current baseline is 770 as of `4a372da`; could be 770+N when you start.
- **Phase isolation + Phase 2 carve-out:** carve-out is GRANTED ONLY for the files listed in §2 In scope. Touching any other file in `swing/data/` or `swing/trades/` requires a return-report deviation note. Do NOT broaden the carve-out.
- **Migration discipline:** new migration file gets the next sequential number (likely `0007_*.sql`). Migration is additive only — no `DROP`, no `ALTER` of existing columns, no data movement of existing rows. If the SQL DDL needs different shape on SQLite vs other engines, this project is SQLite-only — write SQLite-flavored DDL.

---

## 4. Task specifications

### 4.1 Identify the entry-recording table

Read `swing/data/migrations/` files 0001 through 0006 in order. Identify the table that records trade-entry events. Record the table name in your working notes. This determines:
- Which migration adds the new column.
- Which dataclass in `models.py` needs extension.
- Which repo function in `trades.py` needs the new parameter.

### 4.2 Migration commit

Create `swing/data/migrations/0007_trade_hypothesis_label.sql` (adjust number if 0007 is taken). Single statement:

```sql
ALTER TABLE <entry_table_name> ADD COLUMN hypothesis_label TEXT;
```

(SQLite ALTER ADD COLUMN does not require explicit `NULL` declaration; absence of `NOT NULL` makes it nullable.)

TDD: test that running migrations end-to-end on a fresh DB results in the column present and accepting NULL inserts.

Commit:
```
feat(data): migration 0007 — trade hypothesis_label nullable column

Adds nullable hypothesis_label TEXT column to the trade-entry table.
Enables hypothesis-tagged trade-entry recording per the operational-
branch evidence-generation framing settled 2026-04-25.

Phase 2 carve-out (CLAUDE.md): swing/data/migrations/.

Existing rows have NULL; migration is additive and forward-only.
```

### 4.3 Models + repo + service commit

- Extend the dataclass in `models.py`: `hypothesis_label: str | None = None` (appended to existing fields).
- Extend the repo function in `repos/trades.py`: new `hypothesis_label: str | None = None` parameter; pass through to INSERT statement.
- Extend the entry service in `swing/trades/`: new `hypothesis_label: str | None = None` parameter; pass through to repo.

TDD per layer:
- Model: round-trip serialization works with and without label.
- Repo: insert with label persists correctly; insert without label persists NULL; fetch returns the field correctly populated.
- Service: round-trip end-to-end test that an entry call with `hypothesis_label="some text"` results in a stored row with that label.

Commit:
```
feat(data,trades): hypothesis_label optional field on entry path

Extends Trade dataclass + entry repo + entry service with optional
hypothesis_label parameter (free-text). Default None preserves
existing call-site behavior.

Phase 2 carve-out (CLAUDE.md): swing/data/models.py,
swing/data/repos/trades.py, swing/trades/<entry-service>.
```

### 4.4 CLI: `swing trade entry --hypothesis` flag

Extend the existing entry command with a `--hypothesis TEXT` flag. Default: not provided → service receives `None` → DB column gets NULL.

TDD:
- CLI test that `swing trade entry --ticker XYZ --shares 1 --price 10 --stop 9` (no --hypothesis) still works and stores NULL.
- CLI test that `swing trade entry --ticker XYZ --shares 1 --price 10 --stop 9 --hypothesis "test label"` stores `"test label"`.

Commit:
```
feat(cli): trade entry accepts --hypothesis free-text flag

Optional flag carries the operator's pre-trade hypothesis through to
storage. Default unset preserves existing entry workflow.
```

### 4.5 CLI: `swing journal review` hypothesis breakdown

Extend the journal review output. AFTER the existing per-period statistics block, add a new section:

```
## Hypothesis breakdown
- (no label): N trades, $X.XX total
- "label A": N trades, $X.XX total, win rate W% (if N ≥ 3)
- "label B": N trades, $X.XX total
...
```

Sort labeled groups by trade count DESC. The `(no label)` group always appears first if non-empty. Win rate suppressed when N < 3 (small-sample noise).

TDD:
- Synthetic trade rows with mixed labels and outcomes; assert the breakdown matches expected counts/sums/win-rates.
- Edge cases: zero trades in period; all trades unlabeled; one labeled trade (no win-rate shown).

Commit:
```
feat(cli): journal review aggregates by hypothesis_label

Adds a "Hypothesis breakdown" section to `swing journal review`
output. Groups labeled trades by their hypothesis_label; reports
count + sum P&L + (when N ≥ 3) win rate. Unlabeled trades grouped
under "(no label)". Existing review output preserved unchanged.
```

---

## 5. Adversarial review (post-tasks)

After all task commits land, invoke `copowers:adversarial-critic` on the combined diff. Iterate to `NO_NEW_CRITICAL_MAJOR`. **Specific watch items:**

- **Migration safety.** Verify the migration is purely additive: no DROP, no ALTER of existing columns, no data manipulation. Verify ALTER TABLE ADD COLUMN behavior on SQLite is non-rewriting (it is, for nullable columns without defaults; SQLite doesn't rewrite the table).
- **Existing-call-site preservation.** Verify that existing tests calling the entry repo / service / CLI without the new parameter still pass. Verify that existing trades (NULL hypothesis_label) flow through journal review correctly under the `(no label)` group.
- **Phase 2 carve-out boundary.** Verify ONLY the files listed in §2 In scope are touched. Any incidental edit elsewhere (e.g., a docstring update in an unrelated file) needs flagging.
- **Free-text safety.** Verify nothing in the journal review output is an injection vector when the label contains special characters (newlines, quotes, etc.). Free text is fine; just don't let it break the table format.
- **Win-rate definition.** Per task 4.5: win rate is "fraction of trades with positive realized P&L." Verify the definition is clearly stated in the review output OR in the relevant docstring; reviewer will catch ambiguity.
- **Preserve existing journal-review computations.** Verify the existing output (period stats, win rate of all closed trades, etc.) is not modified or removed; the hypothesis breakdown is additive.

Fix major findings in NEW commits per no-amend rule. Minor findings either fix in same follow-up or `ACCEPT-with-rationale`.

---

## 6. Done criteria

- All task commits landed in §4 order.
- Adversarial review pass landed; verdict `NO_NEW_CRITICAL_MAJOR`.
- Fast suite green; trust pytest output.
- Migration 0007 (or next sequential) creates the column on a fresh DB.
- `swing trade entry --hypothesis "test"` stores the label correctly.
- `swing trade entry` without `--hypothesis` continues to store NULL and existing tooling continues to work.
- `swing journal review` shows the hypothesis breakdown when trades have labels; existing review output preserved unchanged.
- Phase 2 carve-out boundary respected.
- Return report produced per §7.

---

## 7. Return report format

```
## Trade hypothesis label — return report

### Commits landed
- <SHA1> feat(data): migration 0007 — trade hypothesis_label nullable column
- <SHA2> feat(data,trades): hypothesis_label optional field on entry path
- <SHA3> feat(cli): trade entry accepts --hypothesis free-text flag
- <SHA4> feat(cli): journal review aggregates by hypothesis_label
- <SHA5+> (if any) fix: address adversarial review finding(s)

### Files touched (Phase 2 carve-out scope)
- swing/data/migrations/0007_*.sql (new)
- swing/data/models.py (extended dataclass)
- swing/data/repos/trades.py (extended repo function)
- swing/trades/<entry-service> (extended service)
- swing/cli/<trade-cmd> (added --hypothesis flag)
- swing/cli/<journal-cmd> (added hypothesis breakdown)
- tests/data/, tests/trades/, tests/cli/ (new tests)

### Tests
- Before: <baseline> passing (likely 770+; trust pytest)
- After: <N> passing, 0 failing. New tests: <count>.

### Adversarial review verdict
- <NO_NEW_CRITICAL_MAJOR | findings summary>

### Schema-change notes
- Entry-recording table: <table_name>
- Migration is additive and forward-only.
- Existing rows have NULL hypothesis_label (including the historical VIS trade).

### Deviations from brief
- <Empty if none.>

### Open questions for orchestrator
- <Empty if none.>
```

---

## 8. If you get stuck

- **If the entry-recording table is split across multiple tables** (e.g., `trades` for the lifecycle row + a separate `trade_entries` events table): the column goes on whichever table is the source-of-truth for the per-entry hypothesis. If unclear, flag in return report and use judgment; the operator can clarify via a follow-up commit.
- **If the existing CLI uses a framework that needs special handling for free-text optional flags** (e.g., click's `option`): just follow the existing pattern in the same command file. Don't introduce new CLI patterns.
- **If existing journal-review output isn't structured for additive sections** (e.g., it returns a single string/table that's hard to extend): minimal-touch refactor to make it extendable is acceptable, but flag it as a minor scope expansion in the return report. Do NOT do a large refactor.
- **If migration ordering shows 0007 already taken** (parallel work landed it): use the next number; flag in return report.
- **If a Phase 2 carve-out boundary issue arises** (e.g., a touched file imports something that itself needs a small change): flag in return report; the operator can scope the additional change separately, OR you can do the minimal additional touch with explicit deviation noting. Do NOT silently broaden.
- **If you discover that existing trade-entry tests are testing positional arguments and your new optional kwarg breaks them**: switch the signatures to keyword-only for the new field (`*, hypothesis_label: str | None = None`) so positional callers are unaffected. Document the rationale.
