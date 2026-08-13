# Demand C — the cohort-key provenance-correction surface (implementation plan)

**Commissioning brief:** [`docs/demand-c-cohort-provenance-commissioning-brief.md`](../../demand-c-cohort-provenance-commissioning-brief.md)
(CHARC, 2026-08-12). **Binding constraint:** RD's evidence rule (brief §2).
**Reference, not template:** [`swing/trades/entry_date_correction.py`](../../../swing/trades/entry_date_correction.py) (item 5).
**Plan base:** `b3cdde23` · **Live DB at authoring:** `schema_version = 35`, 23 trades, 138 evaluation runs.

This is the WRITING-PLANS deliverable. It carries: every premise re-derived against
the live DB with the query that produced it (§1); the §3 audit-shape fork resolved
with reasoning (§2); the contemporaneity semantics and the anchor discriminator's
arithmetic with both values shown (§3); the schema, service, CLI and test design
(§4-§8); the TDD task ladder (§9); the accepted limitations WITH their reasons
(§10); the operator gate (§11); and what is flagged rather than fixed (§12).

**Four findings in §1 DISAGREE with the brief.** They are stated loudly rather than
reconciled quietly, per the dispatch instruction. Two of them change what the plan
builds (§1.6 the label string, §1.7 the test-5 arithmetic); one strengthens the
§3 fork (§1.2); one is an out-of-scope live-data defect (§1.8).

**Two questions are ROUTED TO RD as interpretations of his rule, not silently
decided:** the `<=`-vs-`<` reading of "PRE-DATE the fill" (§3.1.4) and the
last-word guard's refusal shape (§3.3). Neither affects the live CADL case, which
is verified to pass under either reading — so both can be ruled on calmly.

> **REVIEW STATE: ELEVEN counted rounds at tier `strong`, 37 critical/major
> findings, all adjudicated, ZERO reopened, ZERO reverts.** The loop passed two
> ledger gates (rounds 5 and 10) and stopped at round 11 under an
> orchestrator-issued disposition rule: round 11's single finding was
> `REACHABILITY: PRODUCTION` — a real correctness defect, not the
> schema-legal-but-emitter-impossible class — so it was FIXED, reported, and the
> loop stopped rather than continuing on momentum. **Round 11's fix is applied and
> unreviewed; it is the executing arc's binding review that covers it.**
> Ledger + verbatim transcripts: `.copowers-findings.md` at the worktree root.
> **§0 carries ONE ENVELOPE EXTENSION REQUEST that must be answered before Task 4
> executes.**

*Adversarial-review revisions, round 11 (Codex R11, same tier — the final round):
`fills.fill_id` is `INTEGER PRIMARY KEY` **without `AUTOINCREMENT`**, i.e. a bare
rowid, so SQLite REUSES the number when the deleted row held the maximum — and the
production split handler deletes the consolidated fill and reinserts partials with
no explicit id. Demonstrated rather than argued: a date-preserving split of fill 45
(the max) reinserted a partial that came back as **fill 45 with the identical
datetime**, so the round-9 drift check on `(fill_id, date)` reported NO DRIFT on a
row that had been deleted and replaced — a false clean in the audit command, which
would additionally have turned §8.4's own composition test RED. Round 9's
"immutable identity" wording is corrected (the NUMBER is durable, the ROW is not),
deletion is now detected from `entry_fill_id IS NULL` FIRST — verified reuse-proof,
because an INSERT does not restore an FK — and the reader compares the WHOLE frozen
snapshot rather than an id-and-date pair. A `MAX(fill_id)` rowid-reuse discriminator
is added.*

*Adversarial-review revisions, round 10 (Codex R10, same tier): date validation
checked PARSEABILITY but not MEANING — `action_session_date='2026-08-09'` is a
Sunday, parses cleanly, round-trips, and satisfies `<= F` against a Monday fill.
`action_session_for_run` always derives an NYSE session, so a non-session anchor
cannot come from the real emitter and its presence is corruption, not an edge case.
Every parsed date (both cited anchors, every COMPETITOR's, and `F`) must now
satisfy the repo's existing `is_trading_session` — the helper written for exactly
this and already used this way by item 5. Verified zero live rows are affected:
0 of 46 fills, 0 of 138 evaluation runs, 0 of 182 recommendations.*

*Adversarial-review revisions, round 9 (Codex R9, same tier): both findings were
RESIDUALS of this plan's own earlier fixes. The drift reader still named
`get_authoritative_entry_fill` — text written in round 4, before §3.0 existed — so
the supported audit command would have computed its verdict through the exact
lexical ordering §3.0 forbids, on a path no authorization test exercises; it now
uses the same local validated resolver, and emits `CITATION ANCHOR UNVERIFIABLE`
rather than manufacturing a clean verdict from rows its own validator rejected. And
`entry_fill_snapshot_json` was never BOUND to the fill it claimed to preserve —
`entry_fill_id=45` with `{"fill_id":999,...}` passed both layers, and since
`entry_fill_id` goes NULL on delete the JSON would have been the only surviving
identity, making it a false provenance record rather than validation debt. Added an
immutable `entry_fill_id_at_correction` (NOT NULL, no FK) that survives the delete,
with the snapshot's `fill_id`/`trade_id`/`action` pinned against it in SQL and in
`__post_init__`; all ten shapes were run against the CHECK before it was written
down.*

*Adversarial-review revisions, round 8 (Codex R8, same tier): THREE findings turned
out to be ONE CLASS met for the third time — a lexical SQL predicate FILTERING,
ORDERING or LIMITING on an unconstrained TEXT timestamp, so a malformed row is
excluded before any validator sees it. Rounds 4 and 8 had each fixed an INSTANCE;
the class is now stated once as §3.0 and applied at all four sites, the sharpest
being that `get_authoritative_entry_fill`'s own `ORDER BY ... LIMIT 1` returns the
2026-08-12 fill as "earliest" when a schema-legal basic-form 2026-08-11 row exists
(`'2026-08-12T16:00:00' < '20260811T160000'` is True), handing the gate a
day-later, MORE PERMISSIVE `F`. Separately the round-7 JSON CHECKs were still wrong
in the same NULL-passing way one level in: guarding only `$.id` still ACCEPTED the
partial object `{"id":172}`, so all three are rewritten in this repo's established
`CASE WHEN json_valid(...) THEN COALESCE(<all predicates>, 0) ELSE 0 END` form
(migration 0033's pattern), verified against good / partial / malformed / `{}`
before being written down. Plus the operator runbook said `swing db migrate`; the
command is `swing db-migrate`.*

*Adversarial-review revisions, round 7 (Codex R7, same tier): `entry_fill_id`'s
`ON DELETE RESTRICT` would have made a provenance correction BLOCK the production
`split_into_partials` handler, which DELETEs the consolidated fill — cohort
bookkeeping vetoing a money-bearing reconciliation, the exact priority inversion
§3.1.3 forbids, introduced by this plan two sections later. Changed to
`ON DELETE SET NULL` (migration 0035's own precedent) with the fill's identity
frozen in a new `entry_fill_snapshot_json`, plus a COMPOSITION test that runs the
real split path. And §8.4's "raw INSERT → rejected at `__post_init__`" tests were
unpassable — a raw INSERT never constructs the dataclass — so the three snapshots
are now pinned by SQL `json_valid`/`json_extract` CHECKS as well, asserted at both
layers. Writing those CHECKs surfaced a further trap verified at the sqlite prompt:
`json_extract('{}','$.id')` is NULL, `NULL = x` is NULL, and a SQLite CHECK PASSES
on NULL, so the unguarded form ACCEPTED `{}` — the `IS NOT NULL` guards are
load-bearing and are migration 0033's documented lesson met again.*

*Adversarial-review revisions, round 6 (Codex R6, same tier): round 5's own clock
fix was found to be internally contradictory — its prose froze normalized UTC
bounds while its DDL had no such column and its pipeline-snapshot validator
required the RAW `finished_ts` to equal the same field, which cannot both hold
(live CADL: raw `2026-08-10T17:44:45` HST vs normalized `2026-08-11T03:44:45` UTC).
Split into four columns with one job each — `cited_run_ts_raw`,
`cited_pipeline_finished_ts_raw`, `cited_run_ts_utc`,
`cited_status_window_upper_utc` — history compared only against `_utc`, the
snapshot validated only against `_raw`, plus a POSITIVE assertion of the stored
values on an ACCEPTING case (the margin refusal fires whether or not normalization
happened, so refusal-only tests could not see a skipped conversion). And round 5's
instruction to "import the project's timezone constant, never re-spelled" named a
symbol that DOES NOT EXIST — `"Pacific/Honolulu"` is two independent function
defaults — so Task 4 now creates it, which requires the §0 envelope extension.*

*Adversarial-review revisions, round 5 (Codex R5, same tier): the hypothesis-status
comparison was found to span TWO CLOCK DOMAINS ten hours apart — pipeline
timestamps are naive LOCAL, the Phase-9 audit tables are naive UTC — so the window
bounds are now normalized through the project's own declared
`tz="Pacific/Honolulu"` and a ±24h margin refusal covers the unprovable historical
zone (§3.4.1-clock, and the general case is flagged repo-wide at §12.9);
`recorded_at` — the column the whole retrospective guard rests on — was missing
from the validation manifest and `recorded_at=''` would have satisfied the guard
lexically (§5.1); and `--reason` was `required=True` at the click parser, which
would have made the promised no-payload idempotent replay impossible on the actual
operator surface while the service-level test passed (§6).*

*Adversarial-review revisions, round 3 (Codex R3, same tier): the retrospective
status disposition FLIPPED from disclose to **REFUSE** — round 2 had shipped a
relaxation of the binding rule as a default, and the strict reading is now the
default with the relaxation routed to RD (§3.4.1); the interval query moved from
COVERING to INTERSECTING with a four-case ladder, because a mid-window transition
produces ZERO covering intervals rather than two and round 2's guard would have
excluded silently while its test asserted an unconstructible shape (§3.4.1); the
pipeline row supplying the window's upper bound is now CITED by a NOT NULL FK
(§3.4.1); SELECT-first idempotency moved ABOVE `--reason` validation per CLAUDE.md
(§3.5); the unreachable recommendation-kind rung moved up (§3.5); the label's
name-vs-identity tension is declared with its bound (§3.4.1a); and the v35 pin
count went 35 → 36 with the binding criterion changed from the count to the
SUITE (§4.2).*

*Adversarial-review revisions, round 2 (Codex R2, same tier): the hypothesis-status
anchor became a WINDOW `[run_ts, pipeline_runs.finished_ts]` because `run_ts` is a
run-START stamp (14m19s of uncertainty on the live CADL run) and an unbounded
window is now refused; a hypothesis with no covering interval is EXCLUDED from the
as-of registry rather than refusing the whole correction (round 1's fix would have
made every pre-H5 record uncorrectable); retrospective seed intervals are disclosed
via a new frozen `recorded_at` column; the recommendation snapshot's column set is
PRAGMA-DERIVED rather than hand-listed (the hand-list had silently dropped
`action_text`, `risk_dollars`, `risk_pct`); every cited date is validated inside
`_authorize` so `--dry-run` and apply cannot diverge; and the v35 pin inventory
went 34 → 35 across 26 files when the search's own `0035` exclusion turned out to
have hidden a file (§4.2).*

*Adversarial-review revisions, round 1 (Codex R1, `strong` / `gpt-5.6-sol` / effort high):
the hypothesis is now derived against the registry status AS OF the cited record
rather than as of today, with the covering `hypothesis_status_history` interval
cited structurally (§3.4.1); the cited `daily_recommendations` row is recognised as
MUTABLE IN PLACE and its content is frozen + drift-reported (§3.4.2); the
already-applied check moved ABOVE the unset-state gate and the supersession chain
was removed in favour of a schema-enforced one-correction-per-trade (§3.5, §4.1);
the fill-side anchor column is now discriminated and offset-bearing timestamps are
refused (§3.1.3, §3.2.4); the recommendation lookup gained a cardinality refusal
(§3.4 eligibility 3); and Task 2 now carries the 34 literal-v35 test pins the
version bump breaks (§4.2).*

---

## 0. WHAT THIS ARC SHIPS

A CLI-only, audited, single-transaction service that writes the three cohort keys —
`trades.hypothesis_label`, `trades.candidate_id`, `trades.trade_origin` — on ONE
trade, deriving every written value from a STRUCTURALLY CITED pair of
contemporaneous pipeline records, and recording the correction in a new
purpose-built append-only audit table whose schema refuses a correction without its
citation.

**Envelope (brief §7):** `swing/trades/` (new service module), `swing/data/`
(migration 0036 + new repo + two read-only repo additions + one narrow writer +
one model), `swing/cli.py`.

**ONE ENVELOPE EXTENSION IS REQUESTED AND MUST BE APPROVED BY CHARC BEFORE
EXECUTING (Codex R6 Major 1):** a module-level
`PIPELINE_LOCAL_TIMEZONE: str = "Pacific/Honolulu"` added to
**`swing/evaluation/dates.py`**, with that file's two existing helper defaults
repointed at it. It is a pure constant-extraction with **zero behavioural delta** —
both defaults already carry that exact literal — but §3.4.1-clock's normalization
depends on a single source for it, and today there is none. **An implementer may
not grant itself an envelope widening**, so this is routed, not assumed. If it is
declined, §3.4.1's clock normalization has no single source and the window
comparison must fall back to the margin refusal alone, which is materially weaker;
that consequence is stated so the decision is made with it in view.

**Not in this arc:** any web surface; any change to `derive_trade_origin`; any
change to how `record_entry` resolves the keys at ENTRY time; any re-audit of the
cohort keys already on trades 1-22.

---

## 1. PREMISE RE-DERIVATION

Every premise below was re-established against `%USERPROFILE%/swing-data/swing.db`
(read-only URI) or against the code on disk. **Each states the query or search that
produced it**, per the recipe's REPORT-EVERY-COUNT-WITH-ITS-METHOD discipline. A
grep bounds a family from below; where a manifest is claimed, the members were
READ.

### 1.1 `reconciliation_corrections.discrepancy_id` is NOT NULL with an FK — CONFIRMED

`PRAGMA table_info(reconciliation_corrections)` → column 1 `discrepancy_id INTEGER`
`notnull=1`. `PRAGMA foreign_key_list(reconciliation_corrections)` → entry
`(4, 0, 'reconciliation_discrepancies', 'discrepancy_id', 'discrepancy_id',
'NO ACTION', 'CASCADE', 'NONE')`.

CHARC's antecedent holds. RD's "no schema change if the existing audit table
suffices" has a false antecedent.

### 1.2 …AND SO IS `reconciliation_run_id` — **A SECOND NOT NULL THE BRIEF DID NOT NAME**

Same `PRAGMA`: column 17 `reconciliation_run_id INTEGER` `notnull=1`, FK entry
`(0, 0, 'reconciliation_runs', 'reconciliation_run_id', 'run_id', 'NO ACTION',
'CASCADE', 'NONE')`.

Option (i) therefore requires making **two** columns nullable, not one, and both
carry `ON DELETE CASCADE` — i.e. a `reconciliation_corrections` row is by
construction a CHILD of a reconciliation run AND a discrepancy. This is not a
correction to the brief so much as an omission that strengthens its own leaning;
it is load-bearing in §2 and is why the fork is not close.

`swing/trades/entry_date_correction.py:15-19` already states the pair as the reason
a correction "cannot float", and its CLI help (`swing/cli.py:2231-2236`) repeats it
to the operator.

### 1.3 Trades 17/18 carry `'A+ baseline (aplus)'` + `'pipeline_aplus'` — CONFIRMED, with a caveat

`SELECT id, ticker, entry_date, state, hypothesis_label, candidate_id,
trade_origin, entry_intent FROM trades ORDER BY id` (all 23 rows read, not
sampled):

| id | ticker | entry_date | state | hypothesis_label | candidate_id | trade_origin | entry_intent |
|---|---|---|---|---|---|---|---|
| 17 | VSTS | 2026-06-25 | reviewed | `A+ baseline (aplus)` | 8851 | `pipeline_aplus` | `standard` |
| 18 | AMN | 2026-07-01 | reviewed | `A+ baseline (aplus)` | 9276 | `pipeline_aplus` | `standard` |

**Caveat the brief does not mention:** trade **4** (YOU, 2026-05-04) ALSO carries
`hypothesis_label='A+ baseline (aplus)'` and `trade_origin='pipeline_aplus'`, but
`candidate_id=NULL` and `entry_intent='hypothesis_test_by_design'`. It is a
pre-epoch tuition trade excluded from the H1 cohort by the D29 intent filter. So
"the existing cohort rows" is a set of THREE label-bearing rows, of which two are
in-cohort. This matters only because §3.4 derives the label from the CITED RECORD
rather than from these rows — see §1.6.

### 1.4 Candidate 12341 / `daily_recommendations` 172 / trade 23 — CONFIRMED

- `SELECT * FROM candidates WHERE id=12341` → `ticker='CADL'`, `bucket='aplus'`,
  `evaluation_run_id=137`, `close=10.5`, `pivot=10.8149995803833`.
- `SELECT * FROM evaluation_runs WHERE id=137` → `run_ts='2026-08-10T17:30:26'`,
  **`data_asof_date='2026-08-10'`**, **`action_session_date='2026-08-11'`**.
- `SELECT * FROM daily_recommendations WHERE id=172` → `ticker='CADL'`,
  `recommendation='today_decision'`, `evaluation_run_id=137`,
  `data_asof_date='2026-08-10'`, `action_session_date='2026-08-11'`.
- `SELECT ... FROM trades WHERE id=23` → CADL, `entry_date='2026-08-12'`,
  `state='entered'`, all three cohort keys NULL / `manual_off_pipeline`,
  `entry_intent='standard'`.
- `SELECT fill_id, action, fill_datetime, fill_origin FROM fills WHERE trade_id=23`
  → exactly one row: `fill_id=45`, `action='entry'`,
  `fill_datetime='2026-08-12T16:00:00'`, `fill_origin='schwab_auto'`.

The orchestrator's live-DB observation is reproduced exactly: on the CADL rows the
two anchors ALREADY DIFFER (08-10 vs 08-11) and BOTH pre-date the 08-12 fill. §3.2
is written on the assumption that an implementer sanity-checking here sees the
divergence and concludes it is harmless.

### 1.5 No UPDATE path to the three cohort keys except the generic corrector — CONFIRMED, and here is the search

The claim is an ABSENCE, so the search is stated in full (three passes, because a
column-name grep is blind to a dynamic-SQL writer — the class the orchestrator
named).

**Pass A — every `UPDATE trades` in `swing/`, case-insensitive, `.py` + `.sql`:**
`grep -rniE "update[[:space:]]+trades" --include=*.py --include=*.sql swing/` →
**21 hits, each READ.** Of those: 6 are prose in comments/docstrings; 3 are in
migration `0014` (a historical one-time backfill, including the only SQL that ever
wrote `trade_origin` in bulk); 12 are live writers, each with a LITERAL
single-purpose column list — `repos/fills.py:130` (`current_size`/
`current_avg_cost`/`last_fill_at`), `repos/trades.py:455` (`current_stop`),
`repos/trades.py:778` (`entry_intent`), `repos/trades.py:824` (`entry_date`),
`state.py:149` (`state`), `entry.py:454` (`risk_policy_id_at_lock`),
`diagnostics/backfill_trades_sector_industry.py:303,315` (`sector`/`industry`).
**None of the twelve names any of the three cohort columns.**

**Pass B — dynamic-SQL UPDATE builders (f-string / `.format` / concatenation):**
`grep -rniE '(f"|f'\'')[^"'\'']*update |"UPDATE \{|SET \{|\.format\(.*UPDATE|UPDATE " *\+' --include=*.py swing/`
→ two interpolated-identifier UPDATEs reach `trades`:
- `swing/data/repos/trades.py:735` — `f"UPDATE trades SET {', '.join(set_clauses)} WHERE id = ?"`.
  **READ, not grepped:** `set_clauses` is a fixed literal list of the ten Phase-6
  review columns plus an optional `failure_mode` (`repos/trades.py:717-732`). It
  cannot address a cohort column. *This is the writer a column-name grep would not
  have seen; it is benign, and that is established by reading its construction.*
- `swing/trades/reconciliation_auto_correct.py:2060` — `f"UPDATE trades SET {field_name} = ? WHERE id = ?"`.
  `field_name` is byte-exact-validated against `PRAGMA table_info(trades)`
  (`_assert_real_column_name`, `reconciliation_auto_correct.py:261-286`), so it CAN
  address all three. **This is the generic corrector the brief names.**

**Pass C — row-replacing writes:**
`grep -rniE "replace[[:space:]]+into[[:space:]]+trades|insert[[:space:]]+or[[:space:]]+replace[[:space:]]+into[[:space:]]+trades"`
→ **zero hits.** `grep -rn "executescript"` → 7 hits, all in `db.py`/`cli.py`/
`risk_policy.py` migration plumbing, none constructing a `trades` UPDATE.
`INSERT INTO trades` → `repos/trades.py:246,305,369` (creation) and migration 0014.

**Conclusion:** the only live UPDATE path to `hypothesis_label` / `candidate_id` /
`trade_origin` is `reconciliation_auto_correct._update_journal_field`, which
requires a discrepancy. The brief's premise holds.

**D36 — the immutability claim is verified against the AUDIT TRAIL, not inferred
from that absence:**
- `SELECT COUNT(*) FROM reconciliation_corrections` → **37**;
  `GROUP BY affected_table, field_name` → `('fills','fill_match',19)`,
  `('fills','price',13)`, `('cash_movements','net_amount',2)`,
  `('trades','current_stop',2)`, `('trades','entry_date',1)`. **No cohort column.**
- Every one of the 37 rows' `field_name`, `pre_correction_value_json`,
  `applied_value_json` and `operator_truth_value_json` was string-scanned for the
  three column names → **zero matches** (a value-envelope scan, not a column scan,
  because the item-5 surface records coupled columns inside JSON).
- `SELECT COUNT(*) FROM trade_events` → **190**; all 190 `payload_json` values
  scanned for the three names → **zero matches**. `event_type` distribution:
  `note` 72, `stop_adjust` 56, `exit` 24, `entry` 24,
  `reconciliation_auto_correct` 14.

No cohort key on any trade has ever been corrected. The correction this arc applies
to trade 23 will be the first.

### 1.6 **DISAGREEMENT 1 — the derived label for CADL is NOT `'A+ baseline (aplus)'`**

Brief §5 states `hypothesis_label` NULL → `'A+ baseline (aplus)'` and calls it
derivable. It IS derivable. **The derivation that reproduces trades 17/18 produces a
DIFFERENT string for CADL.**

The framework's own label builder is
`swing/recommendations/hypothesis.py:_descriptive_label` (line 275), surfaced
publicly as `HypothesisMatch.suggested_label_descriptive`:

```
non_pass = sorted(_non_pass_criterion_names(candidate))
suffix   = f"; failed: {', '.join(non_pass)}" if non_pass else ""
return f"{hypothesis_name} ({bucket_disp}){suffix}"
```

and `_non_pass_criterion_names` (line 211) counts `result != 'pass'` — **its
docstring states that `na` counts as non-pass**, matching `bucket_for`'s VCP gating.

Live `candidate_criteria` (a per-candidate table, 218,286 rows, FK to
`candidates(id)` ON DELETE CASCADE — so the criterion detail IS persisted and the
label IS reconstructible):

| candidate | trade | non-`pass` criteria | `_descriptive_label` output |
|---|---|---|---|
| 8851 (VSTS) | 17 | *(none)* | `A+ baseline (aplus)` |
| 9276 (AMN) | 18 | *(none)* | `A+ baseline (aplus)` |
| **12341 (CADL)** | 23 | **`TT8_rs_rank` = `na`** | **`A+ baseline (aplus); failed: TT8_rs_rank`** |

(`SELECT criterion_name, result FROM candidate_criteria WHERE candidate_id=? AND
result<>'pass'`. CADL's `TT8_rs_rank` row reads
`value='fallback, excess=+13.31% vs SPY 12w'`, `rule=NULL`, `result='na'` — the
RS-rank universe fallback, `rs_method='fallback_spy'` on the candidates row.)

**The plan writes the derived string, not the brief's string.** Reasons:

1. It is what the framework's OWN contemporaneous record says, which is the
   evidence rule verbatim. `'A+ baseline (aplus)'` for CADL would be read off
   trades 17/18 — a COHORT VOTE, i.e. composed from other rows, which is what
   brief §2 consequence 2 forbids.
2. Both strings are cohort-equivalent. `swing/metrics/label_match.py:label_matches_hypothesis`
   matches on exact-equality OR `name + " "` prefix OR `name + ";"` prefix;
   `"a+ baseline (aplus); failed: tt8_rs_rank"` matches rule 2. **Measured** on a
   copy of the live DB: `list_trades_for_cohort("A+ baseline")` returns
   `[4, 17, 18, 23]` under either string (§1.7).
3. Reusing the framework's builder means there is no second implementation of the
   label to drift (the #24-#26 two-path-divergence class).

**Named wart, not hidden:** the suffix renders an `na` as `failed:`. That is a
pre-existing inaccuracy in `_descriptive_label`, not one this arc introduces, and
fixing it would change every future recommendation label — out of scope. The
operator gate (§11) prints the exact string before the write so nobody discovers
it afterwards. **Routed to RD:** if he wants the brief's literal string, that is a
ruling to record, and the plan's §3.4 changes to read the label from the cohort —
with the curation surface that re-opens, stated.

### 1.7 **DISAGREEMENT 2 — the monthly read does NOT move `2/20 → 2/21`**

Brief §6 test 5 requires "the monthly-read denominator moving 2/20 → 2/21".
**Measured, both paths, on a `shutil.copy2` of the live DB** (the pre-fix read, then
`UPDATE trades SET hypothesis_label=?, candidate_id=?, trade_origin=? WHERE id=23`,
then the post-fix read; the copy was deleted):

| read | PRE | POST |
|---|---|---|
| `compute_hypothesis_progress_breakdown(...)` H1 `current_sample` | **2** | **2** (unchanged) |
| H1 `target_sample` | **20** | **20** (unchanged) |
| H1 `in_flight_sample` | **0** | **1** |
| `list_trades_for_cohort("A+ baseline")` | `[4, 17, 18]` | `[4, 17, 18, 23]` |
| `list_trades_for_cohort("A+ baseline", entry_intent='standard')` | `[17, 18]` | `[17, 18, 23]` |

Identical under BOTH candidate label strings from §1.6.

Two independent reasons the brief's figure cannot be right:

- **20 is not a denominator that grows.** It is
  `hypothesis_registry.target_sample_size` for row `id=1` (`SELECT id, name,
  target_sample_size, status FROM hypothesis_registry` → H1 = 20, H2 = 10, H3 = 5,
  H4 = 10, H5 = 30). Nothing a correction does moves a registry column.
- **The numerator cannot move either, because trade 23 is OPEN.**
  `compute_hypothesis_progress_breakdown` (`swing/journal/stats.py:334`) computes
  `current_sample` from `list_closed_trades` only; open trades go to the separate
  display-only `in_flight_sample` field (`stats.py:323-331`, whose own comment says
  it "does NOT count toward `current_sample` ... or any tripwire arithmetic").
  Trade 23 is `state='entered'`.

**Test 5's real arithmetic is the table above**, and the plan's §8.5 asserts those
values. When trade 23 eventually CLOSES, `current_sample` goes 2 → 3, i.e. the
display moves `2/20` → `3/20` — never `2/21`.

### 1.8 **DISAGREEMENT 3 (out of scope, reported) — trade 21's existing citation POST-DATES its own fill**

`SELECT t.id, ca.bucket, er.action_session_date, t.entry_date FROM trades t JOIN
candidates ca ON ca.id=t.candidate_id JOIN evaluation_runs er ON
er.id=ca.evaluation_run_id` — all 11 candidate-bearing trades:

- **10 of 11 have `action_session_date == entry_date`** (delta 0). This is the
  modal shape and it decides `<=` over `<` in §3.1.
- **Trade 21 (LQDA) has delta = -3**: `entry_date='2026-08-07'` but its
  `candidate_id=12237` belongs to run 136, whose `action_session_date` is
  **`2026-08-10`** (`run_ts='2026-08-07T17:30:02'` — the run happened the EVENING
  of the fill). Its entry fill is `fill_id=42`,
  `fill_datetime='2026-08-07T16:00:00'`.

So a live row already cites a record written after its own entry. Demand C's rule
would refuse that citation. **This arc does not re-audit existing rows and does not
touch trade 21.** It is reported because (a) it is a fact about H2's provenance that
RD owns, and (b) it is the source of the §3.2 discriminator fixture — real emitter
output rather than a synthetic shape.

### 1.9 The root cause of trade 23's NULLs (established, not fixed)

`swing/trades/origin.py:derive_trade_origin` resolves the bucket through
`_latest_complete_evaluation_run_id` — "the most-recent COMPLETE pipeline run" —
not "the run whose recommendation the operator acted on".
`SELECT id, state, evaluation_run_id, finished_ts FROM pipeline_runs WHERE
state='complete' AND evaluation_run_id IS NOT NULL ORDER BY finished_ts DESC, id
DESC LIMIT 3` → pipeline run 152 → `evaluation_run_id=138`, finished
`2026-08-11T17:44:24`. `SELECT COUNT(*) FROM candidates WHERE
evaluation_run_id=138 AND ticker='CADL'` → **0** (run 138's buckets: 46 skip, 10
watch, 3 excluded, 0 aplus). Bucket `None` → `manual_off_pipeline`; and
`swing/trades/entry.py:356` resolves `candidate_id` only when
`derived_origin != "manual_off_pipeline"`, so all three keys stayed empty.

This is gotcha #30's family one level up — a RUN-LEVEL selection standing in for
"the record this trade came from". **Flagged, not fixed** (§12.1): fixing
`derive_trade_origin` is a change to the ENTRY path, outside this brief's envelope,
and it would not retroactively repair trade 23 anyway.

### 1.10 Schema version is 35, not 34

`SELECT * FROM schema_version` → `(35,)`; `swing/data/db.py:73`
`EXPECTED_SCHEMA_VERSION = 35`; `swing/data/migrations/` ends at
`0035_fills_trades_price_divergence.sql`. `CLAUDE.md` line 3 still says v34 —
stale, harmless, noted because this plan adds **migration 0036** and the backup
gate keys on `current_version == 35` STRICT.

---

## 2. §3 — THE AUDIT-SHAPE FORK, RESOLVED

**Decision: option (ii) — a NEW purpose-built `provenance_corrections` table.**
This agrees with CHARC's leaning; the reasons below were derived independently and
are stated so RD and CHARC can attack the reasoning rather than the conclusion. The
first three are facts CHARC's brief did not have.

**(a) Option (i) is a REBUILD, and this repo names that the highest-risk shape it
runs.** SQLite cannot drop a `NOT NULL`; making `discrepancy_id` nullable means
`CREATE TABLE ... _new` + copy + drop + rename on the audit table of record, with
37 live rows and a self-FK (`superseded_by_correction_id`). `swing/data/db.py:1001`
says of the 0035 rebuild, in the repo's own words: *"A rebuild is the highest-risk
shape of migration this project runs; the snapshot is the belt."* Option (ii) is a
bare `CREATE TABLE` — additive, nothing dropped, no existing row touched.

**(b) It is TWO NOT NULLs, not one, and both are `ON DELETE CASCADE` (§1.2).** A
`reconciliation_corrections` row is a CHILD of a reconciliation run. A provenance
correction has no run and no discrepancy, so under (i) it becomes a permanent
double-orphan-by-NULL living in a table whose deletion semantics assume parentage —
and if a future cleanup ever deletes a run, the cascade's behaviour toward
NULL-parent rows becomes a question nobody asked.

**(c) Option (i) cannot make the citation structural, which is the whole point.**
`reconciliation_corrections` has no column for a cited candidate or recommendation;
the citation would live in `pre_correction_value_json` — unenforced text. To make it
structural under (i) you must ADD two FK columns AND a CHECK coupling them to the
NULL `discrepancy_id`, i.e. strictly MORE schema work than (ii), performed as a
rebuild. Brief §2 consequence 1 requires the surface to "refuse without them", and
the cheapest honest way to get "refuse" is a `NOT NULL` the writer cannot evade.

**(d) Option (i) would make a SHIPPED module's stated refusal false.**
`swing/trades/entry_date_correction.py:15-19` justifies requiring a discrepancy with
*"`reconciliation_corrections` declares `discrepancy_id` and `reconciliation_run_id`
NOT NULL with FKs, so a correction cannot float"* — and `swing/cli.py:2231-2236`
repeats it to the operator as the reason `--discrepancy` is required. Weakening the
constraint silently converts both statements into falsehoods while they keep reading
as invariants. That is exactly gotcha **#31** (a comment that stays true-looking
after the thing it describes changes), and this arc exists to stop the system
recording claims that are not so.

**(e) The existing 37 rows' semantics.** Under (i) they would become
"discrepancy-anchored rows in a table that no longer guarantees anchoring" — the
guarantee is not recoverable from the data, only from the fact that they predate the
change. Under (ii) they are untouched and their table's invariant is untouched.

**What I would do if (ii) is rejected.** Option (i) plus `cited_candidate_id` /
`cited_daily_recommendation_id` columns plus a CHECK of the form
`(discrepancy_id IS NOT NULL AND cited_candidate_id IS NULL) OR (discrepancy_id IS
NULL AND cited_candidate_id IS NOT NULL AND cited_daily_recommendation_id IS NOT
NULL)` — a disjoint-union table. It is strictly more schema, delivered as a rebuild,
and it forces a `None` branch into `ReconciliationCorrection.discrepancy_id`
(`swing/data/models.py:1463`, currently a bare `int`) and into
`repos/reconciliation_corrections.py:49,95,145`. It is buildable; it is worse.

**Consequence for the review:** a new table is a §3 architecture tripwire. The
migration is ADDITIVE (`CREATE TABLE` + two `CREATE INDEX` + the version bump);
nothing is rebuilt.

---

## 3. THE EVIDENCE RULE, ENCODED

### 3.0 THE PLAN-WIDE SELECTION RULE — no SQL predicate may filter, order or limit on an unconstrained TEXT timestamp

**This rule exists because the same defect was found at THREE separate sites across
three rounds, and each time it was fixed as an instance (Codex R4 Major 3, R8 Major
2, R8 Major 3). It is a CLASS, and it is stated once here so a fourth site cannot
hide.**

Every timestamp this arc reads — `evaluation_runs.run_ts` / `action_session_date`,
`daily_recommendations.action_session_date`, `fills.fill_datetime`,
`pipeline_runs.finished_ts`, `hypothesis_status_history.effective_from` /
`effective_to` / `recorded_at` — is an **unconstrained `TEXT` column**. A lexical
SQL comparison over such a column does not order them by time, and worse, **a
malformed row that a `WHERE`/`ORDER BY`/`LIMIT` excludes never reaches the
validator at all** — so a validation manifest that covers "every row we inspect" is
vacuous when SQL decided what we inspect.

Verified on the exact production shapes:

- `'2026-08-12T16:00:00' < '20260811T160000'` is **`True`** ( `'-'`=0x2D sorts
  before `'0'`=0x30 ), so `get_authoritative_entry_fill`'s
  `ORDER BY fill_datetime ASC, fill_id ASC LIMIT 1` (`repos/fills.py:216-228`)
  returns the **2026-08-12** row as "earliest" when a schema-legal basic-form row
  for **2026-08-11** exists. `F` becomes a day LATER, i.e. **more permissive**, and
  the malformed competitor is never validated. `fills.fill_datetime` is bare `TEXT`
  (`0014_phase7_state_machine_and_fills.sql`), and `repos/fills.py:149-185` already
  documents that lexical consumers are unsafe.
- The same shape excludes a malformed `hypothesis_status_history` interval from a
  SQL intersection predicate, leaving a genuinely-overlapping corrupt interval
  invisible and a single valid interval looking uniquely authoritative — **the exact
  false single-interval result §3.4.1's guard exists to prevent.**
- The same shape drops a competitor `candidates` row from the last-word guard
  (§3.3).

**THE RULE, binding on every site in this plan:**

> **LOAD ALL candidate rows with NO date-based `WHERE`, NO `ORDER BY` on a
> timestamp, and NO `LIMIT`. VALIDATE every timestamp on every loaded row, refusing
> the whole operation on any malformed one. THEN filter, order and select IN PYTHON
> on PARSED values.**

Applied at all four sites: the authoritative-entry-fill resolver (a NEW local
resolver — `get_authoritative_entry_fill` is **not reused**, because its SQL
ordering is the defect; the local one loads every `action='entry'` fill for the
trade, validates each, and selects on `(parsed_datetime, fill_id)`), the
status-history intervals (loaded via the existing unfiltered
`list_history_for_hypothesis` reader, then intersected in Python), the last-word
competitor set (§3.3), and the recommendation cardinality lookup (§3.4 — an
equality on ids, not a timestamp, but it loads before it counts).

**The same resolver is used by BOTH authorization and the drift reader**, or the two
would disagree about which fill is authoritative — which is how the round-4 drift
fix would have silently drifted from the round-8 selection fix.

### 3.1 Contemporaneity — the comparison the code performs

> **A citation is CONTEMPORANEOUS iff the cited record's OWN action-session anchor
> does not POST-DATE the session of the trade's authoritative entry fill.**

Formally, with `F` = the entry fill's session date (see §3.1.3):

- `evaluation_runs.action_session_date` of the cited candidate's run `<= F`, **and**
- `daily_recommendations.action_session_date` on the cited row itself `<= F`.

#### 3.1.1 Why `action_session_date` and never `data_asof_date`

`data_asof_date` is the cohort-max of the per-ticker bar dates the run consumed — a
BATCH aggregate. Gotcha **#30**: a run-level aggregate is not provenance for a
per-row value, and CLAUDE.md names `evaluation_runs.data_asof_date` as an instance
by name. Beyond the doctrine, the live distribution makes it a strictly weaker gate:

`SELECT julianday(action_session_date)-julianday(data_asof_date) AS d, COUNT(*)
FROM evaluation_runs GROUP BY d` → **delta = 1 day on 96 runs, 3 days on 32 runs,
4 days on 10 runs; 138 of 138. There is no run where the two are equal, and none
where `data_asof_date` is later.** So on this database `data_asof_date` is
UNIFORMLY EARLIER than `action_session_date`, which means the wrong anchor is not
differently wrong — it is **monotonically more permissive**. Every citation the
right anchor refuses on the 1-day runs, and every citation it refuses by up to 4
days on the weekend runs, the wrong anchor accepts.

`daily_recommendations` carries its OWN `data_asof_date` column, so the same trap
exists a second time on the DR row. Both are refused as anchors.

#### 3.1.2 Why not `run_ts`, and why each row is gated on its own anchor

`run_ts` is the physical write time. `SELECT CASE WHEN substr(run_ts,1,10) >
action_session_date THEN 'after' WHEN substr(run_ts,1,10) = action_session_date
THEN 'same' ELSE 'before' END, COUNT(*) FROM evaluation_runs GROUP BY 1` →
**113 before, 25 same, 0 after.** So `action_session_date >= date(run_ts)` always:
`action_session_date` is the *later*, i.e. the *more conservative*, of the two, and
using it never accepts something `run_ts` would refuse. It is also the semantic
anchor — the session the record is ABOUT — which is what "contemporaneous with the
trade" means. `run_ts` is recorded in the audit row for forensics but is not the
gate.

The two cited rows are gated **independently**, on their own columns, even though
`SELECT COUNT(*) FROM daily_recommendations dr JOIN evaluation_runs er ON
er.id=dr.evaluation_run_id WHERE dr.action_session_date <> er.action_session_date`
→ **0 across all 182 rows**. That equality is NOT schema-enforced, so it is a
regularity, not a guarantee, and inferring one row's anchor from the other's is the
premise-by-neighbour habit the recipe forbids.

#### 3.1.3 `F` — which fill, and which column

`F` is the `[:10]` prefix of the AUTHORITATIVE entry fill's `fill_datetime`, under
the project's existing DEFINITION — "first entry fill by `(fill_datetime ASC,
fill_id ASC)`" (`repos/fills.py:216`, the same definition item 5 uses at
`entry_date_correction.py:599-608`).

**The DEFINITION is reused; the SQL IMPLEMENTATION is NOT (§3.0, Codex R8 Major
2).** `get_authoritative_entry_fill` performs that ordering as a lexical
`ORDER BY ... LIMIT 1` over an unconstrained `TEXT` column, which mis-ranks a
schema-legal basic-form timestamp and hides it from validation. This arc therefore
uses a LOCAL resolver that loads every `action='entry'` fill for the trade,
validates each `fill_datetime` (whole-string, extended-form, no offset/`Z`), refuses
the operation on any malformed one, and then selects the minimum on
`(parsed_datetime, fill_id)`. On well-formed data it returns exactly what
`get_authoritative_entry_fill` returns — a test asserts that equivalence on a
canonical corpus, so the divergence is scoped to the malformed case and cannot
become a second definition (the #24-#26 two-path class).

**Not `trades.entry_date`**, for two reasons: it is itself correctable by item 5, so
anchoring on it would make a contemporaneity claim that silently changes when
someone else's correction lands; and the fill is the execution fact while
`entry_date` is a journal restatement of it. The full datetime is validated whole
before its prefix is used, reusing item 5's
`_canonical_fill_datetime_or_refuse` idiom (`fills.fill_datetime` is bare
`TEXT NOT NULL`, so `'2026-08-12garbage'` is schema-legal).

If the local resolver finds NO `action='entry'` fill, REFUSE — a trade with no
entry fill has no session to be contemporaneous with.

**`F` IS NOT IMMUTABLE EITHER, AND THE PLAN MUST NOT PRETEND OTHERWISE (Codex R4
Major 1).** The paragraph above rejects `trades.entry_date` partly because item 5
can move it — but item 5 moves the FILL in the same transaction:
`entry_date_correction.py:1442-1445` calls `update_fill_datetime` on the
discrepancy's bound entry fill, and `get_authoritative_entry_fill` orders by that
very column (`repos/fills.py:216-228`), so a later entry-date correction can move
`F` **and can change WHICH fill is authoritative.** A provenance correction accepted
today can therefore have its foundational comparison invalidated tomorrow — by a
legitimate, higher-priority correction — while its audit row still reads as valid.
V1 is one-shot (limitation 4) and rung 2 returns idempotently BEFORE
re-authorization, so nothing in the write path would ever notice.

**The response is detection, not prevention, and the reason is priority:** blocking
an entry-date correction (a money-bearing ledger fix) because a provenance
correction (a cohort-bookkeeping fix) cites its fill would invert the two surfaces'
importance. So:

- the audit row freezes `entry_fill_id_at_correction` (a NOT NULL scalar with NO
  FK, so the NUMBER survives a DELETE), `entry_fill_id` (a nullable convenience
  FK), `entry_fill_session_date`, and `entry_fill_snapshot_json`
  (§4.1, Codex R7 Major 1 + R9 Major 2);

**`entry_fill_id_at_correction` IS NOT AN IMMUTABLE IDENTITY, AND ROUND 9's WORDING
OVERCLAIMED IT (Codex R11 Major 1).** `fills.fill_id` is `INTEGER PRIMARY KEY`
**without `AUTOINCREMENT`** (`0014_phase7_state_machine_and_fills.sql:8-10`), so it
is a bare rowid and **SQLite REUSES a deleted rowid when it was the largest.** The
split handler deletes the consolidated fill and reinserts partials with no explicit
id (`reconciliation_auto_correct.py:2925-2927, 2961-2994`). **Demonstrated, not
argued:** with the cited fill at `fill_id=45` (the max) and a date-PRESERVING split,
the reinserted partial came back as **`fill_id=45` with the identical
`fill_datetime`** — a DIFFERENT ROW wearing the cited row's number. The stored
number survives; the row it names does not.

**Consequence, and it would have shipped as a false clean:** a drift check on
`(fill_id, date)` alone reports **NO DRIFT** in exactly that case — the cited row
was deleted and replaced and the audit says everything is fine. It would also have
turned §8.4's own composition test RED, because that test asserts drift IS reported.

- **`entry_fill_id IS NULL` is CONCLUSIVE deletion drift and is checked FIRST,
  before any recomputation.** Also demonstrated: the FK's `ON DELETE SET NULL` fires
  at the DELETE, and a later INSERT that happens to reuse the number **does not
  restore it** — the column stays NULL. That makes it a reliable, reuse-proof
  marker, which is the property the whole fix rests on.
- **the READ command then recomputes the anchor through THE SAME LOCAL VALIDATED
  RESOLVER the authorization path uses — never `get_authoritative_entry_fill`
  (§3.0, Codex R9 Major 1)** — and compares the **WHOLE frozen
  `entry_fill_snapshot_json`** against the current authoritative fill's
  identity-bearing fields (`fill_id`, `trade_id`, `action`, `fill_datetime`), not
  merely the id-and-date pair. *The residual reference here
  was written in round 4, before §3.0 existed; leaving it would have had the
  supported audit command computing its verdict through the very lexical ordering
  §3.0 forbids — hiding a malformed earlier fill and reporting NO drift, on a path
  no authorization test exercises.* When the resolver REFUSES (a malformed fill
  exists), the reader emits an explicit
  `CITATION ANCHOR UNVERIFIABLE: trade <id> has a malformed fill_datetime` rather
  than a drift verdict computed from the well-formed rows — a reader must not
  manufacture a clean answer out of data its own validator rejects* — and, when the recomputed `F` would make either cited anchor
  post-dating, escalates to `CITATION INVALIDATED: the cohort assignment recorded
  by correction <id> no longer satisfies contemporaneity under the current
  authoritative entry fill`;
- §8.4 tests it through the REAL `update_fill_datetime` path plus a two-entry-fill
  reorder that changes WHICH fill is authoritative — not a hand-written UPDATE,
  which would not prove the production path reaches it.

**Repairing an invalidated correction needs an authority decision, not a re-run**
(V1 records provenance once), so it is FLAGGED (§12.9) rather than designed here.

**The choice of anchor COLUMN must itself be discriminated (Codex R1 Major 2).**
Every §3.2 fixture as first drafted specified only `F`, so an implementation
reading `trades.entry_date` instead of the fill would have passed all of them. The
divergence is a real supported state, not a contrivance — item 5 explicitly
compares the two and handles disagreement
(`entry_date_correction.py:588-608, 612-618`). §8.2 therefore adds **T2f**, in
which `trades.entry_date` and the authoritative fill's date deliberately DIFFER
and the fill must win, and **T2g**, a two-entry-fill trade pinning that the
`(fill_datetime ASC, fill_id ASC)` authoritative fill supplies `F` rather than the
latest one.

**Offset-bearing and `Z`-suffixed fill timestamps are REFUSED, not converted.**
`fill_datetime[:10]` is a UTC-or-naive calendar prefix, not an exchange session: a
`2026-08-13T00:30:00Z` fill is the 2026-08-12 ET session, and taking the prefix
would set `F` one day LATE — i.e. **more permissive**, accepting a citation the
correct anchor refuses. Converting to `America/New_York` would import a whole
correctness surface (and a tz dependency) into an arc that has no other need of it,
so the surface REFUSES any `fills.fill_datetime` that is not the naive extended
form — no offset, no `Z` — naming it unsupported and routing it to CHARC. This is
item 5's own posture for the after-hours UTC-residue case, verbatim in spirit
(`entry_date_correction.py:309-318`: "UNSUPPORTED by this surface rather than
silently mis-dated").

**What that refusal costs today: nothing.**
`SELECT DISTINCT length(fill_datetime), substr(fill_datetime,11) FROM fills` over
all **46** live rows returns exactly **one** shape — `length=19`, suffix
`T16:00:00` — the synthetic naive convention. **Zero live fills would be refused.**
Noted as a disagreement with the codebase's own prose: item 5's docstring
(`entry_date_correction.py:1088-1091`) states that `fills.fill_datetime` "holds two
production shapes -- the synthetic naive `T16:00:00` and Schwab's offset-bearing
`...T13:00:00.000Z`". The second shape has **no instances in this database**. The
refusal is written for the shape the schema permits, not for the shape the comment
claims, and the comment is left alone (out of scope).

#### 3.1.4 `<=`, not `<` — and this is an interpretation, stated for RD

Brief §2 consequence 3 says the surface "REFUSES a citation whose record does not
PRE-DATE the fill." Read strictly (`<`), that refuses **10 of the 11**
candidate-bearing live trades' own provenance (§1.8: delta 0 on ten of them),
**including trades 17 and 18** — the exact cohort rows this correction is trying to
join. A pipeline run on the evening of session *N* produces records for action
session *N+1*, and the operator acts on session *N+1*; same-session is the designed,
modal case, not an edge.

So the encoded rule is **"must not POST-date"**, `<=`. §8.2's boundary tests pin
both sides (equality ACCEPTS, +1 day REFUSES) so neither a `<` nor an off-by-one can
pass. **This is flagged to RD as an interpretation of his words, not a silent
choice.** If he means strict, the surface becomes inapplicable to same-session
entries and to trades 17/18's shape, and the CADL case still works (08-11 < 08-12) —
so the live deadline is unaffected either way and the ruling can be taken calmly.

### 3.2 **THE ANCHOR DISCRIMINATOR — §6 test 2, with both values shown**

#### 3.2.1 Why CADL cannot be the fixture

| anchor | value | vs `F = 2026-08-12` | verdict |
|---|---|---|---|
| WRONG — `evaluation_runs[137].data_asof_date` | `2026-08-10` | `2026-08-10 <= 2026-08-12` | **ACCEPT** |
| RIGHT — `evaluation_runs[137].action_session_date` | `2026-08-11` | `2026-08-11 <= 2026-08-12` | **ACCEPT** |
| WRONG — `daily_recommendations[172].data_asof_date` | `2026-08-10` | `<= 2026-08-12` | **ACCEPT** |
| RIGHT — `daily_recommendations[172].action_session_date` | `2026-08-11` | `<= 2026-08-12` | **ACCEPT** |

The anchors DIFFER on the live case and BOTH accept. An implementation that reads
`data_asof_date` is green on CADL, green on the acceptance test, green on the
operator gate, and wrong. **This is why test 2 is mandatory.**

#### 3.2.2 The discriminating fixture — shapes taken from LIVE emitter output (trade 21 / LQDA)

`F = 2026-08-07` (fill 42, `fill_datetime='2026-08-07T16:00:00'`), cited candidate
12237 in evaluation run 136, whose real columns are
`data_asof_date='2026-08-07'`, `action_session_date='2026-08-10'`,
`run_ts='2026-08-07T17:30:02'`:

| anchor | value | vs `F = 2026-08-07` | verdict |
|---|---|---|---|
| **WRONG — `data_asof_date`** | **`2026-08-07`** | `2026-08-07 <= 2026-08-07` → true | **ACCEPT** |
| **RIGHT — `action_session_date`** | **`2026-08-10`** | `2026-08-10 <= 2026-08-07` → **false** | **REFUSE** |

**The wrong anchor accepts exactly where the right one refuses.** The gap is the
weekend: the 08-07 evening run's action session is Monday 08-10.

Three fixtures, because the two anchors and their conjunction are three separately
breakable things. Each fixture is a synthetic DB seeded with rows of the shapes
above; the trade is synthetic (the tests must not depend on trade 21, which is real
and out of scope).

- **T2a — candidate anchor.** Candidate run: `data_asof_date='2026-08-07'`,
  `action_session_date='2026-08-10'`. DR row: `action_session_date='2026-08-07'`
  (accepting, so it cannot mask the candidate's refusal). `F='2026-08-07'`.
  → the service REFUSES, and the refusal message names
  `evaluation_runs.action_session_date` and the two dates.
  *Distinguishes:* an implementation reading `data_asof_date` for the candidate
  ACCEPTS and writes three columns → test fails. Verified arithmetic:
  wrong `2026-08-07 <= 2026-08-07` = accept; right `2026-08-10 <= 2026-08-07` = refuse.
- **T2b — recommendation anchor.** Candidate run:
  `action_session_date='2026-08-06'` (accepting). DR row:
  `data_asof_date='2026-08-07'`, `action_session_date='2026-08-10'`.
  `F='2026-08-07'` → REFUSES, message names
  `daily_recommendations.action_session_date`.
  *Distinguishes:* an implementation that gates only the candidate, or that reads
  the DR's `data_asof_date`, ACCEPTS. Verified: candidate right-anchor
  `2026-08-06 <= 2026-08-07` accept; DR wrong `2026-08-07 <= 2026-08-07` accept;
  DR right `2026-08-10 <= 2026-08-07` refuse.
- **T2c — the inference trap.** Candidate run `action_session_date='2026-08-10'`;
  DR row `action_session_date='2026-08-07'` — i.e. the two DISAGREE, which live data
  never shows (§3.1.2, 0/182) and the schema does not forbid. `F='2026-08-07'`
  → REFUSES on the candidate. *Distinguishes:* an implementation that reads ONE
  anchor and applies it to both cited rows ACCEPTS.

**Both values are shown in every fixture's docstring**, so a future reader cannot
mistake the fixture for an arbitrary date choice — the numbers ARE the test.

#### 3.2.3 Boundary tests (pin `<=` in both directions)

- **T2d** candidate + DR `action_session_date = F = '2026-06-25'` → **ACCEPT**
  (trade 17's real shape; a `<` implementation fails).
- **T2e** candidate `action_session_date = '2026-08-13'`, `F = '2026-08-12'` →
  **REFUSE** (this is brief §6 test 1, the later-record refusal; note it is
  ALSO refused by `data_asof_date='2026-08-12'`… only if that column is set to a
  post-`F` value, so T2e is deliberately built with
  `data_asof_date='2026-08-12'` — which the WRONG anchor accepts. T2e therefore
  discriminates too, and T2a-c remain the sharper instruments).

#### 3.2.4 The ANCHOR COLUMN on the fill side is discriminated too (Codex R1 Major 2)

The three fixtures above pin which COLUMN of the CITED rows supplies the anchor.
They say nothing about which column supplies `F`, so an implementation reading
`trades.entry_date` passes all of them. Two more:

- **T2f — `trades.entry_date` vs the authoritative fill.** `trades.entry_date =
  '2026-08-11'`; authoritative entry fill `fill_datetime = '2026-08-12T16:00:00'`,
  so `F = '2026-08-12'`; cited candidate `action_session_date = '2026-08-12'`.
  → **ACCEPT** (`2026-08-12 <= 2026-08-12`). *Distinguishes:* an implementation
  reading `trades.entry_date` computes `F = '2026-08-11'` and REFUSES
  (`2026-08-12 <= 2026-08-11` is false). Both values shown; the divergence is a
  supported live state (`entry_date_correction.py:612-618` handles it explicitly).
- **T2g — two entry fills.** Fills on `2026-08-12T16:00:00` (id 1) and
  `2026-08-14T16:00:00` (id 2); cited candidate `action_session_date = '2026-08-13'`.
  → **REFUSE**, because the AUTHORITATIVE fill is the earlier one and
  `2026-08-13 <= 2026-08-12` is false. *Distinguishes:* an implementation taking
  the latest fill computes `F = '2026-08-14'` and ACCEPTS.
- **T2h — offset-bearing fill.** `fill_datetime = '2026-08-13T00:30:00Z'` →
  **REFUSE with the unsupported-representation message**, not silently anchored on
  the `[:10]` prefix `2026-08-13` (which is one session late, i.e. permissive).

### 3.3 The LAST-WORD guard — one citation per trade, and it is the framework's last word

**The problem contemporaneity alone does not solve.** `SELECT ca.id, er.action_session_date,
ca.bucket FROM candidates ca JOIN evaluation_runs er ON er.id=ca.evaluation_run_id
WHERE ca.ticker='CADL' ORDER BY ca.id` → **33 rows** for CADL alone, four of them in
the fill's vicinity: 12148 (`watch`, session 08-06), 12215 (`watch`, 08-07), 12270
(`watch`, 08-10), 12341 (`aplus`, 08-11). **All four pre-date the 08-12 fill and all
four are therefore contemporaneous.** An operator free to pick among them picks the
bucket he likes — which is the curation the evidence rule exists to prevent,
re-entering through the choice of WHICH true record to cite.

**The guard.** The cited candidate row MUST be the maximum, under ordering
`(evaluation_runs.action_session_date, evaluation_runs.run_ts, candidates.id)`,
among all `candidates` rows for the trade's ticker whose run's
`action_session_date <= F`. In words: **the framework's last word before the fill.**

**EVERY COMPETITOR ROW IS VALIDATED, NOT JUST THE CITED ONE (Codex R4 Major 3).**
The guard's `action_session_date <= F` filter and its ordering are LEXICAL
comparisons over `evaluation_runs.action_session_date` and `run_ts`, both
unconstrained `TEXT NOT NULL` (`0001_phase1_initial.sql`). A competitor row
carrying a basic-ISO date is therefore **silently dropped from the competitor
set** — verified in Python: `'20260811' <= '2026-08-12'` is **`False`**, because
`'0'` (0x30) sorts after `'-'` (0x2D), even though 2026-08-11 genuinely precedes
2026-08-12. A newer, semantically-qualifying row disappears and the guard then
blesses an OLDER operator-selected citation: **precisely the citation-shopping the
guard exists to prevent, arriving through the guard's own comparison.**

So the service canonically round-trip-validates `action_session_date` and `run_ts`
on **every competitor row it loads**, before any filtering or ordering, and
**REFUSES on any malformed competitor** — naming the offending row rather than
skipping it. **The general rule this instance teaches: validation scope is every
row the DECISION READS, not every row the OPERATOR CITED.** §5.1's validation
requirement was scoped to the cited rows and was therefore two-thirds of a guard.

**Verified against live data** (`ORDER BY er.action_session_date DESC, er.run_ts
DESC, ca.id DESC LIMIT 1`), and it independently reproduces the citations two
existing cohort rows already carry:

| ticker | `F` | guard picks | trade's actual `candidate_id` |
|---|---|---|---|
| CADL | 2026-08-12 | **12341** (aplus, session 08-11) | — (the target) |
| VSTS | 2026-06-25 | **8851** (aplus, 06-25) | **8851** (trade 17) ✓ |
| AMN | 2026-07-01 | **9276** (aplus, 07-01) | **9276** (trade 18) ✓ |
| SLDB | 2026-04-22 | 782 (aplus, 04-22, run 10) | — |
| YOU | 2026-05-04 | 2752 (aplus, 05-04, run 32) | — (trade 4 has NULL) |
| NVCR | 2026-06-18 | 8411 (aplus, 06-18, run 95) | — |
| LQDA | 2026-08-07 | 12169 (**watch**, 08-07, run 135) | 12237 (post-dating; §1.8) |

That the guard reproduces 8851 and 9276 exactly — two rows written by an entirely
different code path, months apart — is the strongest available evidence the ordering
is the right one.

**The DR row is then LOOKED UP, not picked.** It must be the
`daily_recommendations` row with the SAME `evaluation_run_id` as the cited candidate
and the same ticker. This collapses the citation to ONE degree of freedom, which the
guard pins. **Satisfiability, measured:** of the 14 `bucket='aplus'` candidate rows
in the DB, 11 have a same-run DR row; the 3 that do not (681/SLDB run 9,
2648/YOU run 31, 8295/NVCR run 94) are each SUPERSEDED under the guard by a later
same-session row that DOES (782 run 10, 2752 run 32, 8411 run 95 — the table above).
**So on live data the guard and the same-run DR requirement are jointly satisfiable
for every aplus candidate.** (Separately: 58 DR rows have no same-run candidate row
at all — `SELECT ... WHERE NOT EXISTS (...)` → 58 — and **every one is
`recommendation='near_trigger'`**, the persisted-watchlist emit. All 11
`today_decision` rows have their candidate. This is why §3.4 requires
`today_decision`.)

The CLI still takes BOTH ids and REFUSES unless the supplied DR id equals the
derived one — item 5's "`--to` is a CONFIRMATION, never the source" idiom
(`entry_date_correction.py:652-658`) applied to the citation. The brief's
requirement that the correction "names the `candidates` row and the
`daily_recommendations` row" is honoured; the operator confirms rather than selects.

**ROUTED TO RD as a semantics question (§12.2).** The guard is conservative in a
contestable way: if the ticker reappeared in the *next* run as `skip` before the
fill, the last word is that `skip` row and the trade becomes uncorrectable even
though the operator's buy-stop was placed off the earlier `aplus` recommendation.
**The live CADL case is unaffected — verified: `SELECT COUNT(*) FROM candidates
WHERE evaluation_run_id=138 AND ticker='CADL'` → 0**, so run 138 (action session
2026-08-12) contains no CADL row and 12341 remains the last word. The refusal is
implemented with its own message so the case is legible if it ever fires.

### 3.4 Deriving the three values — every one a function of the cited record

Inputs: cited candidate row `C` (hydrated WITH its `candidate_criteria`), its run
`R`, the cited DR row `D`.

**Eligibility, checked before any derivation:**

1. `C.bucket == 'aplus'`. **This is not a convenience restriction — it is the
   boundary of what is derivable.** `swing/trades/origin.py:derive_trade_origin`
   maps `bucket='watch'` to `pipeline_watch_hyp_recs` *or* `pipeline_watch_manual`
   **according to `entry_path`** (`origin.py:69-72`), and `entry_path` is an
   in-process enum that is persisted NOWHERE. For a watch candidate the framework's
   own record cannot say which of the two origins is true, so a watch correction
   would have to COMPOSE the value — the thing brief §2 consequence 2 forbids. Only
   `bucket='aplus'` is a total function of the persisted row
   (`origin.py:66-67`: `if bucket == "aplus": return "pipeline_aplus"`,
   entry-path-independent).
2. `D.recommendation == 'today_decision'`. A `near_trigger` row says "watching,
   approaching" — it is not the framework recording a decision for that session, and
   58 of them have no candidate row at all (§3.3).
3. **DR CARDINALITY — exactly one, established by a COUNT, not by `fetchone()`
   (Codex R1 Major 3).** The unique index on `daily_recommendations` is
   `ux_daily_recs_action_session_date_ticker_rec` on
   `(action_session_date, ticker, recommendation)` — **NOT** on
   `(evaluation_run_id, ticker, recommendation)`. Two `today_decision` rows for the
   same ticker with DIFFERENT action sessions may both carry the same
   `evaluation_run_id`, because `upsert_recommendation` REWRITES
   `evaluation_run_id` in place on conflict (§3.4.2). So the same-run lookup can
   legitimately return more than one row, and a bare `fetchone()` would let SQLite's
   row order — or the operator's supplied id — pick the citation, reopening the
   citation-shopping channel §3.3 exists to close. The service SELECTs **all**
   same-run same-ticker `today_decision` rows and REFUSES on zero or on two-or-more,
   naming the count, **before** the supplied confirmation id is compared. (The
   exactly-one-or-refuse idiom is item 5's `_resolve_archive_row`,
   `entry_date_correction.py:1173-1179`.)
4. `D.ticker == C.ticker == trades.ticker`.
5. The last-word guard (§3.3) and both contemporaneity anchors (§3.1).
6. **The matched hypothesis was ACTIVE when the framework wrote the record**
   (§3.4.1) — not merely active today.
7. All three cohort keys are currently in their UNSET state:
   `hypothesis_label IS NULL`, `candidate_id IS NULL`,
   `trade_origin = 'manual_off_pipeline'`. **This surface FILLS empty provenance; it
   does not re-decide provenance the framework already recorded.** A trade whose
   keys are already set is refused, with the reason named. **This gate fires AFTER
   the idempotency check, not before** — see §3.5 and Codex R1 Major 1.

**Derivations:**

| written column | source | mechanism |
|---|---|---|
| `trades.candidate_id` | `C.id` | the cited row's own primary key |
| `trades.trade_origin` | `C.bucket` | `swing.metrics.funnel.APLUS_TRADE_ORIGIN` (`funnel.py:51`, the EXISTING constant `"pipeline_aplus"`) — imported, **not a third copy**, per the #11 mirror discipline. Pinned to `origin.py` by a drift test (§8.6). |
| `trades.hypothesis_label` | `C` + `candidate_criteria` | `match_candidate_to_hypotheses(C, registry=<the AS-OF registry, §3.4.1>)` (`hypothesis.py:313`) must return **exactly one** match; take its `suggested_label_descriptive`; pass it through `canonicalize_hypothesis_label` (`swing/trades/entry.py:202`) exactly as `record_entry` does at the persistence boundary. **NOT `list_hypotheses(conn)` unmodified** — that is today's mutable status, which §3.4.1 replaces. |

**The hypothesis is DERIVED, not chosen.** The matcher's rules are
`_aplus_baseline_match` = `bucket == 'aplus'`; `_near_aplus_extension_match` and
`_sub_aplus_vcp_not_formed_match` and `_broad_watch_baseline_match` all require
`bucket == 'watch'`; `_capital_blocked_match` requires the non-pass set to be
exactly `{'risk_feasibility'}` (`hypothesis.py:222-270`). So an `aplus` candidate
matches H1 and only H1 — but the plan asserts "exactly one" at runtime rather than
assuming it, because the registry is data and a future hypothesis could widen the
set. `include_baseline` is left at its `False` default: the broad-watch fallback is
a caller-side opt-in for the recommendation surface, and firing it here would let a
fallback rule label a correction. Zero matches or two-or-more → REFUSE, naming what
was found.

#### 3.4.1 The registry status is evaluated AS OF THE RECORD, never as of today (Codex R1 Critical 1)

`match_candidate_to_hypotheses` filters `h.status == 'active'`
(`hypothesis.py:326-328`) on the registry rows handed to it. Passing today's
`list_hypotheses(conn)` would make the derived hypothesis a function of
**present-day mutable state** — which is exactly the thing RD's rule forbids, one
level up from the values themselves. The failure is two-directional and both
directions are wrong: a hypothesis PAUSED when the record was written but active
today would be assigned anyway; a hypothesis active then and closed now would be
refused.

**This is not hypothetical on this database.** `SELECT * FROM
hypothesis_status_history` → 8 rows, and H2 has a real
`active → paused → active` cycle on 2026-05-12 (history rows 2, 5, 6;
`effective_from='2026-05-12T17:22:54.847'` → `effective_to='2026-05-12T17:22:56.143'`),
while H3 went `active → closed-target-met` on 2026-06-04 (rows 3, 7). The mechanism
is live; only H1's own history is a single uninterrupted interval
(`history_id=1`, `active`, `effective_from='2026-04-25T00:00:00.000'`,
`effective_to=NULL`), which is why the CADL case would have come out right by luck.

**The as-of anchor is a WINDOW, not an instant (Codex R2 Major 1).** `run_ts` is
NOT the record-write moment: `swing/evaluation/orchestration.py:107` takes
`run_now` as a parameter captured once by the adapter at run START, copies it into
`EvaluationRun.run_ts` at step 13 (`orchestration.py:305-308`), and only persists
at step 14 (`persist(run, candidates)`, `orchestration.py:322-323`); the
recommendation rows are emitted later still. **The gap is not nominal — measured on
the live CADL run: `evaluation_runs[137].run_ts = '2026-08-10T17:30:26'` and its
pipeline run 151 `finished_ts = '2026-08-10T17:44:45'`, a 14-minute 19-second
window.** A status transition inside that window would reproduce the very defect
this fix exists to close, through a narrower race.

So the rule is: **ONE interval must cover the ENTIRE window `[run_ts, upper]`.** If
one interval spans the whole window, the status is unambiguous no matter where in
the window the write actually landed. `upper` is
`pipeline_runs.finished_ts` for the pipeline run owning the evaluation run, and it
is admitted only when **exactly one** `pipeline_runs` row references it AND that
row is `state='complete'` with a non-NULL `finished_ts`. Otherwise the persistence
instant is unbounded above and the surface **REFUSES**, naming that it cannot bound
when the record was written.

**Live cost of that refusal, measured:** `SELECT COUNT(*) FROM evaluation_runs er
WHERE NOT EXISTS (SELECT 1 FROM pipeline_runs pr WHERE pr.evaluation_run_id=er.id)`
→ **15 of 138** evaluation runs have no pipeline row. Of the **14** `bucket='aplus'`
candidate rows, **11 sit in runs with exactly one complete pipeline run**; the three
that do not are candidates 681 / 782 / 1006 (SLDB, runs 9/10/12, 2026-04-21…04-23),
from before the `pipeline_runs.evaluation_run_id` linkage was populated. **SLDB was
never traded, so the refusal costs nothing on live data.**

#### 3.4.1-clock TWO CLOCK DOMAINS MEET HERE, AND THEY ARE TEN HOURS APART (Codex R5 Critical 1)

**The window and the intervals are written by different clocks.** Verified on disk:

| value | writer | clock |
|---|---|---|
| `evaluation_runs.run_ts` | `runner.py:608` `run_now = _dt.now()` → `orchestration.py:308` | **naive LOCAL** |
| `pipeline_runs.started_ts` / `finished_ts` | `pipeline/lease.py:38` `datetime.now().isoformat(timespec="seconds")` | **naive LOCAL** |
| `hypothesis_status_history.effective_from` / `effective_to` / `recorded_at` | `trades/hypothesis.py:254,265` → `data/datetime_helpers.py:now_ms()` | **naive UTC** (`datetime.utcnow()`, and the module docstring says so) |

This box is **Pacific/Honolulu, UTC−10**. Comparing them as text — which is what
rounds 2-4 specified — compares instants ten hours apart. The consequence is
exactly the one the window was built to prevent: **a status change physically
inside a 17:30-17:44 HST window is stored as ~03:35 UTC the NEXT DAY, so the old
interval appears to cover the whole textual window and the correction is authorized
on a status that had already changed.** Canonical parsing does not fix this; the
strings are well-formed and mean different things.

**The normalization, and it is grounded in the project's own declaration, not
invented here.** `swing/evaluation/dates.py:101,123` already declares the local zone
for exactly these naive pipeline timestamps — `def last_completed_session(now_local,
*, tz: str = "Pacific/Honolulu")` and the same default on
`action_session_for_run`, the functions that produce `data_asof_date` and
`action_session_date` from `run_now`. The window bounds are localized with that same
zone and converted to UTC before any comparison with a history timestamp.

**THE CONSTANT DOES NOT EXIST YET, AND SAYING "IMPORT IT" WAS A DEFECT (Codex R6
Major 1).** Round 5 instructed the implementer to import the project's timezone
constant "never re-spelled". There is no such symbol: `"Pacific/Honolulu"` is
embedded independently as TWO function DEFAULTS (`dates.py:101` and `:123`) and
nowhere else. Executing that instruction exactly would either import a nonexistent
name and go red, or re-spell the literal a THIRD time in direct contradiction of the
single-source guarantee the same sentence claimed.

**So Task 4 ADDS the constant, and this REQUIRES AN ENVELOPE EXTENSION that CHARC
must approve before executing:** a module-level
`PIPELINE_LOCAL_TIMEZONE: str = "Pacific/Honolulu"` in **`swing/evaluation/dates.py`**
— a file the brief's §7 envelope (`swing/trades/`, `swing/data/`, `swing/cli.py`)
does **not** cover — with both existing helper defaults repointed at it
(`tz: str = PIPELINE_LOCAL_TIMEZONE`) and the correction service importing it. A pin
asserts all THREE consumers resolve to that one constant. **This is a
stop-and-route, not a self-authorized widening:** the change is a pure
constant-extraction with no behavioural delta (both defaults already carry that
exact literal), but it is outside the declared envelope and an implementer may not
grant that to itself. **If CHARC declines, the arc cannot normalize clocks
correctly and §3.4.1's window comparison must be reduced to the margin refusal
alone — which is materially weaker.**

**RAW AND NORMALIZED ARE STORED SEPARATELY — the round-5 prose and the round-5
schema contradicted each other (Codex R6 Critical 1).** Round 5 said the normalized
bounds were "frozen into `cited_status_window_upper` and a new `cited_run_ts_utc`",
but the DDL had no such column, kept comparing the raw `cited_run_ts`, and — via the
R4 pipeline-snapshot validator — required the snapshot's RAW `finished_ts` to EQUAL
`cited_status_window_upper`. **Both cannot hold.** On the live CADL row the raw
bound is `2026-08-10T17:44:45` (HST) and the normalized one is
`2026-08-11T03:44:45` (UTC): following the prose fails snapshot validation and the
insert dies; following the schema stores raw local bounds and reinstates the very
mixed-clock defect round 5 existed to remove. Four columns, each with one job:

| column | domain | used for |
|---|---|---|
| `cited_run_ts_raw` | naive LOCAL, verbatim | snapshot/provenance fidelity |
| `cited_pipeline_finished_ts_raw` | naive LOCAL, verbatim | the pipeline snapshot equality check |
| `cited_run_ts_utc` | normalized | **every** comparison against history |
| `cited_status_window_upper_utc` | normalized | **every** comparison against history |

**History timestamps are compared ONLY against the `_utc` pair; the pipeline
snapshot is validated ONLY against the `_raw` pair.** Note the date itself rolls on
the live case — `2026-08-10T17:30:26` HST is `2026-08-11T03:30:26` UTC — so a stored
`_utc` value that equals its `_raw` sibling is proof the normalization was skipped,
and §8.6 asserts exactly that inequality on an ACCEPTING case rather than resting on
a refusal (the margin refusal fires whether or not normalization happened, so a
refusal-only test cannot distinguish an implementation that omitted it).

**Plus a MARGIN, because the historical zone cannot be proved.** A naive stamp
carries no zone, and nothing records where the box was when it was written; a
laptop that travelled, or a DST-less HST assumption applied to a machine that later
moved, silently shifts every historical comparison. So the surface additionally
**REFUSES when any inspected interval boundary falls within ±24 hours of either
normalized window bound** — the region where a wrong-by-hours conversion could flip
the verdict. Outside that band the ten-hour question cannot change the answer, and
inside it the honest response is to decline rather than to guess.

**Live cost, measured: none.** H1's only interval begins `2026-04-25T00:00:00.000`
and never ends; the CADL window is 2026-08-10T17:30:26 → 17:44:45 local, **107 days
from the nearest boundary.** The margin refusal cannot fire on the acceptance case.

**This is a REPO-WIDE finding, not a Demand-C one** — two clock domains coexist in
one database and any future comparison across them inherits the bug. Flagged at
§12.10; this arc normalizes only at its own comparison site.

**Building the as-of registry.** For each registry row, resolve intervals from
`hypothesis_status_history` (`history_id` PK; `hypothesis_id` FK to
`hypothesis_registry(id)`; half-open `[effective_from, effective_to)`, `effective_to
IS NULL` = still current):

**The query is on intervals INTERSECTING the window, not covering it — and that
distinction is the whole guard (Codex R3 Major 1).** Round 2's rule counted only
COVERING intervals and claimed a mid-window transition would produce "more than
one". **It produces ZERO.** `swing/data/repos/hypothesis_status_history.py:12-18`
states the sequence in its own words: *"predecessor's open interval is CLOSED first
(`UPDATE prior SET effective_to = ?`), THEN successor is INSERTed"* — both at the
same instant `t`. So a transition strictly inside `[run_ts, upper]` yields two
ADJACENT half-open intervals `[a, t)` and `[t, ...)`, **neither of which covers the
window**. Round 2's rule would therefore have fallen through to its "no covering
interval" branch and SILENTLY EXCLUDED the hypothesis instead of refusing — and its
proposed test asserted a shape (`two intervals covering the window`) that **cannot
be constructed**, so the test was unwritable and would have been quietly weakened
into a generic zero-match assertion. A false green inside the mechanism added to
close a false green.

**Load ALL history rows for the hypothesis through the existing unfiltered
`list_history_for_hypothesis` reader (`repos/hypothesis_status_history.py:101`,
verified to return *all* rows for the hypothesis with no date predicate) — NO SQL
intersection predicate (§3.0, Codex R8 Major 3).** That reader does carry an
`ORDER BY effective_from ASC` in SQL, which is harmless HERE precisely because it
ORDERS without FILTERING — no row is hidden — and its ordering is discarded and
re-derived in Python on parsed values anyway. **The rule §3.0 states is about
FILTERING and LIMITING, which lose rows; a pure ordering that loses none is safe to
inherit and unsafe to RELY on.** A lexical `WHERE` would drop a malformed interval that genuinely
overlaps the window (a basic-form `20260811T033500` sorts after a normalized
`2026-08-11T03:44:45` upper bound), leaving a corrupt overlapping interval invisible
and one valid interval looking uniquely authoritative — manufacturing exactly the
false single-interval result this guard exists to prevent. Validate `effective_from`,
`effective_to` and `recorded_at` on EVERY loaded row and refuse the whole operation
on any malformed one; then intersect, order and select IN PYTHON on parsed values:

| case | verdict |
|---|---|
| zero intersecting **AND** the whole window precedes the hypothesis's earliest `effective_from` | **NOT YET PRESENT — exclude from the as-of registry, no refusal** |
| zero intersecting otherwise (a HOLE in the history) | **REFUSE** — `status history has a gap over the window` |
| exactly one intersecting **and it covers the whole window** | **use it** |
| exactly one intersecting but it does NOT cover the whole window | **REFUSE** — `the status changed inside the window` |
| two or more intersecting | **REFUSE** — same message (transition, or overlapping corruption) |

The NOT-YET-PRESENT exclusion is what round 2 got right and must be kept: migration
`0026_broad_watch_baseline.sql` created H5 on 2026-06-09 with its history starting
there, so refusing on absence would have made *every* citation older than that
uncorrectable because an unrelated FUTURE hypothesis had not yet existed. Exclusion
is also what the matcher itself does — `hypothesis.py:326-328` omits non-active rows
rather than erroring.

The surviving rows are handed to the matcher with `status` replaced
(`dataclasses.replace`) by their as-of values. **The refusal messages are distinct
per case and §8.6 asserts the SPECIFIC message**, not merely that a refusal
happened — otherwise the transition case passes through the absence branch and
proves nothing.

For run 137 the window `['2026-08-10T17:30:26', '2026-08-10T17:44:45']` sits inside
H1's single interval (`history_id=1`, `active`, from `'2026-04-25T00:00:00.000'`,
`effective_to` NULL) → `active` → the derivation is unchanged. **Verified: the live
case is unaffected by this fix; the fix is for every case after it.**

**Retrospective status intervals are REFUSED (Codex R3 Critical 1 overturned this
plan's round-2 disposition, and it was right to).**
`0017_phase9_risk_policy_and_reconciliation.sql:306-320` seeds one interval per
registry row with `effective_from = strftime('%Y-%m-%dT00:00:00.000', created_at)`
but `recorded_at = strftime(..., 'now')` — **the migration's own comment says so**:
*"effective_from = day-start anchor of the registry's created_at (preserves
chronology); recorded_at = migration apply time."* Those seeds are therefore
BACKDATED ASSERTIONS, not contemporaneous records, and on the strictest reading of
RD's rule they are inadmissible.

**The rule: REFUSE when `recorded_at > run_ts`** — i.e. when the status interval was
not on record by the START of the uncertainty window. `cited_hypothesis_status_recorded_at`
is frozen onto the audit row so the admitted intervals' contemporaneity is checkable,
and the refusal message names migration 0017 as the reason a seed interval fails.

**Why this plan changed its mind.** Round 2 chose DISCLOSE, reasoning that refusing
would block older citations. Round 3's reviewer answered that correctly and the
answer stands: ***disclosure is not authorization***, and "otherwise the correction
is unavailable" is an AVAILABILITY argument, not evidence of contemporaneity. The
binding rule (brief §2) admits only the framework's own contemporaneous record; an
interval asserted after the record it describes is not one. Shipping the relaxation
and asking RD to bless it would have inverted the burden — a plan may ship the
STRICT reading of a director's rule and ask him to relax it, but it may not ship a
relaxation of his rule as a default and call the choice "routed".

**Live cost of the strict reading, measured: none.** Exactly **5** of the 14 aplus
candidates have `run_ts` before the seed `recorded_at` (`'2026-05-12T08:18:10.560'`)
— 681/782/1006 (SLDB) and 2648/2752 (YOU) — and **none is a correction target**
(SLDB was never traded; YOU is trade 4, already labelled and pre-epoch tuition).
**Routed to RD as a RELAXATION request, not as a decision:** if he rules that
migration 0017's backdated seeds are admissible, the refusal becomes the disclosure
described above and the machinery is already there. Nothing live turns on it either
way, which is what makes the strict default free.

**Frozen structurally into the audit row** (§4.1), so the claim is checkable later
rather than re-derived from a registry that keeps moving: `cited_hypothesis_id`
(NOT NULL FK), `cited_hypothesis_status_history_id` (NOT NULL FK to the covering
interval), `cited_hypothesis_status_at_record` (frozen TEXT, CHECK `= 'active'`),
`cited_hypothesis_status_recorded_at`, the four clock columns
`cited_run_ts_raw` / `cited_pipeline_finished_ts_raw` / `cited_run_ts_utc` /
`cited_status_window_upper_utc` (§3.4.1-clock), **`cited_pipeline_run_id`** (NOT NULL FK —
see below), and `cited_hypothesis_name_at_correction` (§3.4.1a).

**The pipeline row that supplies the upper bound is CITED, not merely consulted
(Codex R3 Major 3).** `pipeline_runs.evaluation_run_id` is a NULLABLE, NON-UNIQUE
FK (`0006_pipeline_chart_linkage.sql`), so "exactly one complete row referenced
this evaluation run" is a fact about the table AT AUTHORIZATION TIME that a later
insert, delete or state change silently unmakes — while the audit row would still
read as fully cited. `cited_pipeline_run_id INTEGER NOT NULL REFERENCES
pipeline_runs(id) ON DELETE RESTRICT` pins it, the service validates that the cited
row's own `evaluation_run_id` equals `cited_evaluation_run_id`, and its
`state`/`started_ts`/`finished_ts` are frozen into
`cited_pipeline_run_snapshot_json` and drift-reported exactly as the recommendation
snapshot is (§3.4.2). Without it, the round-2 status repair rests on a proof the
audit cannot reconstruct.

#### 3.4.1a The label's NAME is a join key, its IDENTITY is the FK — the tension, stated (Codex R3 Major 2)

The reviewer is right that the written label's hypothesis-name component is taken as
spelled TODAY, and that `DERIVATION_RULE_VERSION` records which correction-time code
ran without making that code contemporaneous. The finding is real and it is
DECLARED, not dismissed. What follows is why the proposed fixes are worse, so RD and
CHARC can attack the reasoning rather than guess at it:

- **"Freeze the cited name" is self-defeating.** `label_matches_hypothesis`
  (`label_match.py:27-38`) matches `trades.hypothesis_label` against the registry's
  CURRENT `name`. A frozen stale name would produce a trade that is IN no cohort —
  the correction would write a historically-purer string that fails to do the one
  thing the correction exists to do (§1.7's `list_trades_for_cohort` flip).
- **"Refuse older citations lacking a rule-version anchor" refuses ALL of them.** No
  such anchor exists anywhere in the schema — `EvaluationRun` carries none
  (`models.py:202-217`), nor does any pipeline or candidate row. That fix cancels
  the arc, including the CADL case it was commissioned for.
- **Adding a run-linked rule-version anchor is a change to the pipeline WRITE
  path**, outside the brief's envelope (§0). Recommended as a follow-on (§12.11).

**What the plan does instead, and it is a strengthening rather than a defence:** the
correction's identity claim is the **FK `cited_hypothesis_id`**, which is immutable
and survives any rename; the NAME is a rendering of that identity for the join. Both
are recorded — `cited_hypothesis_name_at_correction` freezes the spelling actually
written, so a later rename is visible as drift rather than as a mystery. And a test
asserts, at write time, that
`label_matches_hypothesis(written_label, registry[cited_hypothesis_id].name)` holds.

**The decisive point, and it bounds the finding:** a registry rename breaks
`label_matches_hypothesis` for **every trade in the cohort**, including the 3 the
framework labelled itself. It is a pre-existing framework-wide property of using a
name as a join key — **this arc does not introduce it and cannot fix it from inside
its envelope.** A corrected trade is left exactly as sound as a natively-labelled
one, which is the correct bar for a correction surface.

**The label string plays TWO roles and the plan separates them deliberately.**
`trades.hypothesis_label` is not only a historical record — it is the LIVE JOIN KEY
that `label_matches_hypothesis` compares against the registry's CURRENT `name`
(`label_match.py:27-38`, `cohort.py:list_trades_for_cohort`). So the label must
carry the name as spelled TODAY or the trade silently leaves the cohort. The
immutable historical fact is carried by the three audit columns above, which is
where it belongs; the label carries the join key, which is what it is for. Stating
this is the point — a reader who thinks the label is pure history will "fix" it into
a stale name and break cohort membership without a test failing.

**Derivation-rule version, MECHANICALLY BOUND (Codex R4 Major 4).**
`_descriptive_label`'s format and `_non_pass_criterion_names`'s
`na`-counts-as-non-pass semantics are CODE, not data, so no FK can pin them. A
module constant `DERIVATION_RULE_VERSION = "2026-08-12.1"` is frozen into
`derivation_rule_version` on every audit row.

**The first draft said it "is bumped by hand when either is changed" and tested
only that it was non-empty — which is gotcha #31 in the plan's own words, in a
paragraph elsewhere in this plan that cites #31 against someone else.** An
unenforceable promise about future discipline; `_descriptive_label`'s own docstring
even invites the drift (*"the descriptive suffix may evolve"*,
`hypothesis.py:276-280`). Two corrections would then claim the same derivation
version while using different rules — defeating the one mitigation §3.4.1a offers
for the missing contemporaneous rule anchor.

**The fix is a pin, not a promise:** a test computes
`sha256(inspect.getsource(_descriptive_label) + inspect.getsource(_non_pass_criterion_names))`
and asserts it equals a constant recorded ALONGSIDE `DERIVATION_RULE_VERSION`.
Changing either function fails that test until both the hash and the version are
updated in the same commit. This is the project's own idiom — the H1 amendment text
is pinned by sha256 for exactly this reason (CLAUDE.md line 3). The failure message
names the version constant as the thing to bump, so the test teaches its own fix.

#### 3.4.2 The cited recommendation row is MUTABLE IN PLACE — bounded, frozen, and checkable (Codex R1 Critical 2)

`swing/data/repos/recommendations.py:9-33`:

```sql
INSERT INTO daily_recommendations (...) VALUES (...)
ON CONFLICT(action_session_date, ticker, recommendation) DO UPDATE SET
    evaluation_run_id = excluded.evaluation_run_id,
    data_asof_date = excluded.data_asof_date, action_text = ..., entry_target = ...,
    stop_target = ..., shares = ..., risk_dollars = ..., risk_pct = ...,
    rationale = ...
```

A second pipeline run for the SAME action session UPDATES the existing row **in
place, including `evaluation_run_id`**, keeping its primary key. This is not
theoretical: `SELECT action_session_date, COUNT(*) FROM evaluation_runs GROUP BY 1
HAVING COUNT(*)>1` → **multiple runs per session are routine** (6 runs on
2026-07-06, 6 on 2026-06-08, 4 on 2026-06-15, 2 on nine more sessions), and §3.3's
three aplus-without-same-run-DR cases are exactly this shape.

So `ON DELETE RESTRICT` stops the cited row DISAPPEARING and does nothing about it
CHANGING. **An FK alone is not a durable citation for a mutable row, and the plan
must not claim it is.** Three responses, in order of what they buy:

1. **Freeze the row's identity AND content at authorization** into
   `cited_recommendation_snapshot_json` (NOT NULL). **The column set is DERIVED
   from `PRAGMA table_info(daily_recommendations)` at read time, never hand-listed
   (Codex R2 Major 3).** The first draft enumerated ten fields and silently omitted
   **`action_text`, `risk_dollars` and `risk_pct`** while calling itself "the full
   row" — and `action_text` is the most material of the three, being the
   framework's own operator-facing instruction (live value on DR 172:
   `Buy-stop $10.81 ... 19 sh ... $37.41 risk = 19 x ($11.1300 cap - $9.1610
   stop)`). All three are in the `DO UPDATE SET` clause, so all three can drift.
   A hand-list is a manifest that rots on the next `ALTER TABLE`; deriving it from
   the PRAGMA is the same reasoning `_assert_real_column_name` uses
   (`reconciliation_auto_correct.py:273-275`: *"DERIVED from `PRAGMA table_info`
   rather than hand-listed, so it cannot rot as columns are added"*).
2. **Make drift DETECTABLE and REPORTED, field-by-field over the SAME derived
   column set.** `swing journal provenance-corrections` re-reads each cited row and
   prints an explicit `CITATION DRIFT: <field> was <frozen> now <live>` line per
   changed field, plus a `CITATION SCHEMA DRIFT` line naming any column present in
   one and not the other. A silent contradiction between the audit row and the row
   it cites is the failure mode; a loud one is a finding the operator can act on.
3. **Name what this does NOT buy.** A frozen snapshot is a SERVICE ASSERTION about
   what was read, not an independent immutable record. If the DR row is rewritten,
   the framework retains no proof of what it said at authorization beyond this
   correction's own copy. **The real fix is making recommendation persistence
   append-only/versioned, which is a change to a production WRITE path outside this
   brief's envelope** — flagged in §12.6 as a follow-on, not silently absorbed.

The bound is worth stating precisely, because it is narrower than "anything can
change": the upsert's conflict identity is `(action_session_date, ticker,
recommendation)` and those three are exactly the fields the citation's MEANING rests
on — they are the only three the `DO UPDATE SET` clause does **not** touch. A re-run
for the same session, ticker and recommendation kind therefore produces a
semantically equivalent record; what can move underneath the citation is
`evaluation_run_id`, the prices, the sizing and the rationale. The `evaluation_run_id`
move is the one that matters, because §3.4's same-run requirement is stated against
it — which is precisely why it is frozen and drift-checked.

### 3.5 The complete refusal ladder

Ordered so that every refusal is a VERDICT about eligibility before any refusal that
is an INSTRUCTION — item 5's Codex-R4/R5 ordering lesson
(`entry_date_correction.py:514-523, 692-700`).

**SELECT-FIRST IDEMPOTENCY LEADS THE LADDER (Codex R1 Major 1, tightened by Codex
R3 Major 4).** Round 1 moved the already-applied check above the unset gate, which
was necessary but not sufficient: it still sat BELOW `--reason` validation, so an
already-applied re-run carrying an empty or stale reason would REFUSE instead of
returning its existing correction id — and the happy-path test used a valid reason,
so it could not catch that. CLAUDE.md states the rule directly: *"SELECT-first
idempotency MUST precede payload validation — a terminal-state row must return its
existing audit-row id even with a stale/None payload."* So the lookup runs FIRST,
and `--reason` is validated only on the path that actually writes.

1. Trade not found (the minimum needed to query safely).
2. **A `provenance_corrections` row already exists for this trade** — SELECT-first,
   BEFORE any payload validation →
   - the supplied citation ids MATCH the stored citation → **idempotent return of
     the existing correction id; nothing written, and `--reason` is never
     inspected**;
   - they differ → **REFUSE**, naming the existing correction id and that V1
     records provenance ONCE (limitation 4). There is no `--supersede`.
3. `--reason` empty/non-string (validated only for a NEW write).
4. Cohort keys not all in the unset state (a VERDICT, and terminal).
5. No authoritative entry fill; or its `fill_datetime` is not a whole parseable
   extended-ISO datetime; or it carries an offset / `Z` (§3.1.3, unsupported).
6. Cited candidate id not found; DR id not found.
7. Ticker disagreement among trade / `C` / `D`.
8. **`D.recommendation != 'today_decision'`** — checked HERE, immediately after the
   supplied row is loaded and its ticker verified (Codex R3 Minor 1). Below the
   cardinality lookup it was UNREACHABLE: a `near_trigger` row can never share an
   id with the selected `today_decision`, so it always stopped at rung 10 or 11 and
   the operator got a confusing confirmation-id error instead of the eligibility
   verdict — and the promised one-test-per-rung suite could not exercise it at all.
9. `C.bucket != 'aplus'` (message names §3.4's derivability reason explicitly, so
   the operator is not left thinking it is arbitrary).
10. Every cited date / timestamp fails canonical round-trip validation (§5.1) —
    before any comparison uses it.
11. Same-run same-ticker `today_decision` rows number zero, or two-or-more
    (§3.4 eligibility 3) — the CARDINALITY refusal, evaluated before the supplied
    id is compared.
12. Supplied DR id ≠ the single id that lookup produced.
13. Candidate anchor post-dates `F`.
14. Recommendation anchor post-dates `F`.
15. Last-word guard: a later qualifying candidate row exists.
16. The evaluation run's persistence bound is unavailable (not exactly one COMPLETE
    `pipeline_runs` row with a `finished_ts`, or the cited pipeline row does not own
    the cited evaluation run) — §3.4.1.
17. Hypothesis status over the window: a history gap, or no single interval covering
    it, or a `recorded_at` that post-dates `run_ts` (retrospective) — §3.4.1.
18. Matcher returns ≠ 1 match.

Every refusal raises `CohortProvenanceCorrectionError(ValueError)` so the CLI's
`except ValueError -> ClickException` discipline applies, and every one ends with
"Nothing was written."

---

## 4. SCHEMA — migration 0036 (schema_version 35 → 36)

**#11 is binding: the SQL CHECK, the Python constant and the dataclass
`__post_init__` validator land in ONE commit** (Task 2), together with the
`EXPECTED_SCHEMA_VERSION` bump and the backup gate.

### 4.1 DDL

```sql
-- 0036_provenance_corrections.sql
-- Demand C: the cohort-key provenance-correction audit table.
-- ADDITIVE ONLY. Nothing is rebuilt, dropped or renamed.
-- Atomic via explicit BEGIN; ... COMMIT; per gotcha #9 (executescript
-- implicit COMMIT). Bumps schema_version 35 -> 36.
BEGIN;

CREATE TABLE provenance_corrections (
    provenance_correction_id INTEGER PRIMARY KEY AUTOINCREMENT,

    trade_id      INTEGER NOT NULL REFERENCES trades(id)      ON DELETE RESTRICT,
    -- ON DELETE SET NULL, NOT RESTRICT (Codex R7 Major 1). RESTRICT would make
    -- cohort bookkeeping BLOCK a supported money-bearing operation: the
    -- production `split_into_partials` handler DELETEs the consolidated fill
    -- (`reconciliation_auto_correct.py:2925`, `DELETE FROM fills WHERE
    -- fill_id = ?`), including entry fills, and two shipped tests protect that
    -- capability. After a provenance correction existed, a legitimate
    -- date-preserving execution-grain split of the cited fill would die on an
    -- FK IntegrityError -- the exact priority inversion section 3.1.3 says must
    -- be avoided, introduced by this plan two sections later. Migration 0035
    -- already set the precedent: its own `fill_id` reference is ON DELETE SET
    -- NULL. The PROVENANCE survives the delete in the frozen snapshot below;
    -- the pointer is a convenience and is allowed to go NULL.
    entry_fill_id INTEGER REFERENCES fills(fill_id) ON DELETE SET NULL,
    -- THE FROZEN NUMBER (Codex R9 Major 2). `entry_fill_id` goes NULL the
    -- moment the fill is deleted, so it CANNOT be the thing the snapshot is
    -- checked against -- after a split, the JSON would be the only surviving
    -- identity and nothing would ever have bound it to the fill actually used.
    -- A plain NOT NULL scalar with NO FK survives the delete and is what the
    -- snapshot CHECK pins.
    --
    -- IT IS NOT AN IMMUTABLE *IDENTITY*, and round 9 called it one (Codex R11
    -- Major 1). `fills.fill_id` is INTEGER PRIMARY KEY WITHOUT AUTOINCREMENT
    -- -- a bare rowid -- so SQLite REUSES the number when the deleted row held
    -- the maximum. Verified: a date-preserving split of fill 45 (the max)
    -- reinserted a partial that came back as fill_id 45 with the same
    -- datetime. The NUMBER is durable; the ROW is not. Deletion is therefore
    -- detected from `entry_fill_id IS NULL` (which an INSERT does not restore,
    -- also verified), never from the number matching.
    entry_fill_id_at_correction INTEGER NOT NULL,
    -- The fill's identity, owner, role and datetime frozen verbatim, so a
    -- deleted or replaced fill leaves the audit row still able to say WHAT it
    -- anchored on -- and able to PROVE it was that fill.
    entry_fill_snapshot_json TEXT NOT NULL,

    -- THE CITATION. NOT NULL is the evidence rule made structural: the schema
    -- refuses a correction that does not name the records it derives from.
    -- ON DELETE RESTRICT (not CASCADE, not SET NULL): an audit row whose
    -- citation can vanish is not a citation, and RESTRICT matches the
    -- latch_view_events.candidate_id precedent from migration 0033.
    cited_candidate_id            INTEGER NOT NULL REFERENCES candidates(id)             ON DELETE RESTRICT,
    cited_daily_recommendation_id INTEGER NOT NULL REFERENCES daily_recommendations(id)  ON DELETE RESTRICT,
    cited_evaluation_run_id       INTEGER NOT NULL REFERENCES evaluation_runs(id)        ON DELETE RESTRICT,

    -- THE HYPOTHESIS ASSIGNMENT'S OWN PROVENANCE (Codex R1 Critical 1). The
    -- matcher filters on registry `status`, which is MUTABLE, so the derived
    -- hypothesis is only as contemporaneous as the status it was evaluated
    -- against. The interval that made it active is cited structurally.
    cited_hypothesis_id                INTEGER NOT NULL REFERENCES hypothesis_registry(id)              ON DELETE RESTRICT,
    cited_hypothesis_status_history_id INTEGER NOT NULL REFERENCES hypothesis_status_history(history_id) ON DELETE RESTRICT,
    cited_hypothesis_status_at_record  TEXT NOT NULL,
    -- The interval must cover the WHOLE uncertainty window, because run_ts is
    -- the run's START and the record is persisted later (section 3.4.1;
    -- 14m19s on the live CADL run). Both bounds are frozen so the window this
    -- correction actually proved is legible without re-deriving it.
    -- FOUR clock columns, each with ONE job (Codex R6 Critical 1). The _raw
    -- pair is naive LOCAL verbatim from the source rows; the _utc pair is the
    -- normalized form. History timestamps are compared ONLY against _utc; the
    -- pipeline snapshot is validated ONLY against _raw. Storing one pair and
    -- pretending it serves both is what round 5 did.
    cited_pipeline_finished_ts_raw     TEXT NOT NULL,
    cited_run_ts_utc                   TEXT NOT NULL,
    cited_status_window_upper_utc      TEXT NOT NULL,
    -- The pipeline row that SUPPLIED that upper bound, cited rather than merely
    -- consulted: pipeline_runs.evaluation_run_id is a nullable NON-UNIQUE FK, so
    -- "exactly one complete row" is unrecoverable after the fact without this.
    cited_pipeline_run_id              INTEGER NOT NULL REFERENCES pipeline_runs(id) ON DELETE RESTRICT,
    cited_pipeline_run_snapshot_json   TEXT NOT NULL,
    -- recorded_at of the cited interval. An interval recorded AFTER run_ts is a
    -- RETROSPECTIVE assertion (migration 0017 backdated its seeds) and the
    -- service REFUSES it; this column makes the admitted ones checkable.
    cited_hypothesis_status_recorded_at TEXT NOT NULL,
    -- The registry NAME as spelled when the label was written. The FK above is
    -- the identity; this is the join-key rendering (section 3.4.1a).
    cited_hypothesis_name_at_correction TEXT NOT NULL,

    -- THE ANCHORS AS EVALUATED, FROZEN AT WRITE TIME (#30 applied to this
    -- table itself): per-row provenance is carried, not re-derived later. A
    -- reader must never have to re-join to learn what this correction claimed.
    cited_candidate_action_session_date      TEXT NOT NULL,
    cited_recommendation_action_session_date TEXT NOT NULL,
    entry_fill_session_date                  TEXT NOT NULL,
    cited_run_ts_raw                         TEXT NOT NULL,

    -- The cited daily_recommendations row is MUTABLE IN PLACE (Codex R1
    -- Critical 2; `upsert_recommendation` DO UPDATE SET rewrites even
    -- `evaluation_run_id`). RESTRICT stops it disappearing and does nothing
    -- about it changing, so its content at authorization is frozen here and
    -- drift is REPORTED by the read command. See section 3.4.2 for what this
    -- does and does not buy.
    cited_recommendation_snapshot_json TEXT NOT NULL,

    -- The label format and the na-counts-as-non-pass rule are CODE, not data,
    -- so no FK can pin them; the version constant makes a later change visible.
    derivation_rule_version TEXT NOT NULL,

    pre_value_json        TEXT NOT NULL,
    applied_value_json    TEXT NOT NULL,
    corrected_fields_json TEXT NOT NULL,

    applied_at        TEXT NOT NULL,
    applied_by        TEXT NOT NULL,
    correction_reason TEXT NOT NULL,

    risk_policy_id_at_correction INTEGER REFERENCES risk_policy(policy_id) ON DELETE SET NULL,

    -- Three-predicate date guards, per migration 0033's own lesson: a SQLite
    -- CHECK PASSES when its expression is NULL, so date('2026-99-99') IS NULL
    -- accepts a length-correct invalid date. Round-trip equality catches the
    -- NORMALISING case, IS NOT NULL catches the INVALID case, and the year
    -- floor catches year zero (which SQLite round-trips and Python's
    -- date.fromisoformat RAISES on -- the DB holding a row the read path
    -- cannot hydrate).
    CHECK (date(cited_candidate_action_session_date) IS NOT NULL
           AND date(cited_candidate_action_session_date) = cited_candidate_action_session_date
           AND cited_candidate_action_session_date >= '1900-01-01'),
    CHECK (date(cited_recommendation_action_session_date) IS NOT NULL
           AND date(cited_recommendation_action_session_date) = cited_recommendation_action_session_date
           AND cited_recommendation_action_session_date >= '1900-01-01'),
    CHECK (date(entry_fill_session_date) IS NOT NULL
           AND date(entry_fill_session_date) = entry_fill_session_date
           AND entry_fill_session_date >= '1900-01-01'),

    -- CONTEMPORANEITY, ENFORCED BY THE SCHEMA. The brief says this "cannot be
    -- a SQLite CHECK (cross-table)" -- true of a cross-table comparison, but
    -- FREEZING the anchors onto this row (above) makes it INTRA-row, and an
    -- intra-row CHECK is exactly what SQLite does enforce. This does NOT
    -- replace the service-layer gate, whose job is to prove the frozen values
    -- equal the cited rows' actual columns; it makes a correction row that
    -- ASSERTS a post-dating citation physically un-INSERTable.
    CHECK (cited_candidate_action_session_date      <= entry_fill_session_date),
    CHECK (cited_recommendation_action_session_date <= entry_fill_session_date),

    -- The window is well-formed in BOTH domains, compared within each.
    CHECK (cited_run_ts_raw <= cited_pipeline_finished_ts_raw),
    CHECK (cited_run_ts_utc <= cited_status_window_upper_utc),
    -- The admitted status interval was on record by the START of the window.
    -- The evidence rule made structural: a retrospective interval cannot be
    -- filed at all, not merely flagged. `recorded_at` is naive UTC, so it is
    -- compared against the UTC bound and NEVER against the raw local one --
    -- that comparison would be wrong by ten hours (section 3.4.1-clock).
    CHECK (cited_hypothesis_status_recorded_at <= cited_run_ts_utc),

    -- THE THREE SNAPSHOTS ARE PINNED IN SQL, NOT ONLY IN `__post_init__`
    -- (Codex R7 Major 2). Section 8.4 requires RAW INSERTs of `{}`, malformed
    -- JSON and wrong-id snapshots to be REJECTED -- and a raw INSERT never
    -- constructs the dataclass, so a `__post_init__`-only design would accept
    -- every one of them and turn a required test red. JSON1 is compiled in
    -- (sqlite 3.50.4 on this box; `json_valid` + `json_extract` verified).
    --
    -- THE `CASE WHEN json_valid(...) THEN COALESCE(<all predicates>, 0) ELSE 0
    -- END` FORM IS MANDATORY, and two weaker drafts were wrong (Codex R7 M2,
    -- R8 M1). **A SQLite CHECK PASSES when its expression is NULL.**
    -- `json_extract('{}','$.id')` is NULL, so the bare form ACCEPTED `{}`;
    -- adding `IS NOT NULL` on `$.id` ALONE then still ACCEPTED the PARTIAL
    -- object `{"id":172}`, because the remaining comparisons went NULL --
    -- existence != completeness, inside the fix for it. `COALESCE(..., 0)`
    -- collapses every NULL to a failure at once, and the `CASE WHEN
    -- json_valid` gate is this repo's established malformed-JSON pattern
    -- (`0033_latch_order_intents.sql`, whose exception-TYPE contract
    -- `tests/data/test_migration_0033.py` pins). All four shapes -- good,
    -- partial, malformed, `{}` -- were run against this exact form before it
    -- was written down.
    CHECK (CASE WHEN json_valid(cited_recommendation_snapshot_json) THEN COALESCE(
               json_extract(cited_recommendation_snapshot_json, '$.id')
                   = cited_daily_recommendation_id
           AND json_extract(cited_recommendation_snapshot_json, '$.evaluation_run_id')
                   = cited_evaluation_run_id
           AND json_extract(cited_recommendation_snapshot_json, '$.action_session_date')
                   = cited_recommendation_action_session_date, 0)
           ELSE 0 END),
    CHECK (CASE WHEN json_valid(cited_pipeline_run_snapshot_json) THEN COALESCE(
               json_extract(cited_pipeline_run_snapshot_json, '$.id')
                   = cited_pipeline_run_id
           AND json_extract(cited_pipeline_run_snapshot_json, '$.evaluation_run_id')
                   = cited_evaluation_run_id
           AND json_extract(cited_pipeline_run_snapshot_json, '$.state') = 'complete'
           AND json_extract(cited_pipeline_run_snapshot_json, '$.finished_ts')
                   = cited_pipeline_finished_ts_raw, 0)
           ELSE 0 END),
    -- The snapshot must BE the fill this correction anchored on -- id, owner
    -- and role, not merely a well-formed object (Codex R9 Major 2). Without
    -- the id equality, `entry_fill_id=45` with snapshot `{"fill_id":999,...}`
    -- passed BOTH layers and the audit would durably assert contemporaneity
    -- against a fill it never used.
    CHECK (CASE WHEN json_valid(entry_fill_snapshot_json) THEN COALESCE(
               json_extract(entry_fill_snapshot_json, '$.fill_id')
                   = entry_fill_id_at_correction
           AND json_extract(entry_fill_snapshot_json, '$.trade_id') = trade_id
           AND json_extract(entry_fill_snapshot_json, '$.action') = 'entry'
           AND json_extract(entry_fill_snapshot_json, '$.fill_datetime') IS NOT NULL
           AND substr(json_extract(entry_fill_snapshot_json, '$.fill_datetime'), 1, 10)
                   = entry_fill_session_date, 0)
           ELSE 0 END),
    -- The convenience FK, while it still points anywhere, must point at the
    -- same fill the immutable scalar names.
    CHECK (entry_fill_id IS NULL OR entry_fill_id = entry_fill_id_at_correction),

    CHECK (applied_by = 'operator'),
    CHECK (length(trim(correction_reason)) > 0),
    CHECK (length(trim(derivation_rule_version)) > 0),
    -- The correction may only be recorded on the strength of a hypothesis that
    -- was ACTIVE when the framework wrote the cited record.
    CHECK (cited_hypothesis_status_at_record = 'active')
);

-- ONE correction per trade, enforced by the SCHEMA (brief section 6 test 4's
-- "never a duplicate write"). This became available only once V1 dropped the
-- supersession chain (Codex R1 Major 1): a chain needs two live heads for the
-- duration of one statement, and SQLite evaluates uniqueness per statement with
-- no deferral for indexes, so a chain and this index are mutually exclusive.
-- V1 does not re-correct, so the index is both correct and strictly stronger
-- than a service-layer guard.
CREATE UNIQUE INDEX ux_provenance_corrections_trade
    ON provenance_corrections(trade_id);
CREATE INDEX ix_provenance_corrections_cited_candidate
    ON provenance_corrections(cited_candidate_id);

UPDATE schema_version SET version = 36;

COMMIT;
```

**`superseded_by_correction_id` was in the first draft and is REMOVED, not left as
a forward seam.** With no V1 write path it would be dead schema whose only
documentation would be a comment promising what a future arc will do with it —
gotcha **#31** exactly (a promise about work that has not happened, unenforceable
by construction, and still reading true after it stops being true). Adding the
column later is a plain `ALTER TABLE ADD COLUMN`, which SQLite does cheaply and
additively. Removing it is also what makes the unique index above possible, so the
subtraction bought a structural guarantee.

### 4.2 Backup gate + version

- `swing/data/db.py`: `EXPECTED_SCHEMA_VERSION = 35 → 36`.
- **THE BUMP BREAKS AT LEAST 36 EXISTING LITERAL-35 ASSERTIONS ACROSS 26 TEST
  FILES, AND Task 2 CARRIES ALL OF THEM (Codex R1 Major 4, corrected twice — R2
  Major 5, R3 Major 5).** Without this inventory the TDD ladder cannot reach green:
  Task 2 would go red for reasons unrelated to Task 2.

  **THE BINDING INSTRUCTION IS NOT THE NUMBER — IT IS THE SUITE.** This count has
  now been wrong three times (24 → 34 → 35 → 36), each correction found by someone
  running a slightly different search, and there is no reason to believe the fourth
  number is final. So Task 2's completion criterion is: **bump the constant, run
  `python -m pytest -m "not slow" -q`, and fix EVERY resulting failure, reporting
  the count OBSERVED.** The enumerated list below is a STARTING POINT that makes
  the work estimable — it is not the definition of done. A count is only as sound
  as the search that produced it; a suite run is self-verifying.

  **Method — the manifest was READ, not counted from a token match:** the widened
  search is
  `grep -rnE "(==|<=|>=|<|>)[[:space:]]*35\b|\b35[[:space:]]*(==|<=|>=|<|>)|target_version=35|version=35|\(35,?\)" tests/ --include=*.py`
  (60 raw hits), every matched LINE then inspected and the non-schema hits
  discarded — pattern-detector constants (`_flat_bars(35)`, `>= 35` base-length
  rules, `0.35` thresholds) and prose comments. Assertions written as
  `== EXPECTED_SCHEMA_VERSION` track the constant and are deliberately NOT counted.

  **The two lines the earlier searches missed, and why — both are method failures
  worth more than the number:**
  1. `tests/data/test_migration_0035_fills_trades_price_divergence.py:62-63`
     (`assert EXPECTED_SCHEMA_VERSION == 35`) — hidden by a `grep -vE "0035"`
     filter added to drop migration-filename noise. **A filter that removes noise
     can remove signal wearing the same token.**
  2. `tests/data/test_no_schema_change_v3.py:37`
     (`assert versions[-1] <= 35, "a new migration file was added"`) — a HEAD
     *ceiling* guard, missed because the earlier regex only matched `assert 35` and
     `== 35`, never a `<=`. **A pin is not always an equality.** This one is
     load-bearing in a second way: it is the guard that trips on an UNAUTHORIZED
     migration, and its own comment says raising the ceiling *"is the guard WORKING
     AS DESIGNED for an AUTHORIZED migration ... which is why the bump belongs in
     the same commit as the migration and nowhere else"* — i.e. migration 0036 and
     this line MUST move together, in Task 2.

  **THE 26TH FILE, AND WHY THE FIRST PASS MISSED IT — the method's own defect,
  recorded because it is the more useful half of the finding.** The filter carried
  `grep -vE "0035|..."` to drop migration-0035 *filename* noise, and that predicate
  **excluded an entire test file from the manifest**:
  `tests/data/test_migration_0035_fills_trades_price_divergence.py:62-63` is
  `def test_expected_schema_version_is_35(): assert EXPECTED_SCHEMA_VERSION == 35`
  — a HEAD-tracking assertion that MUST become 36. This is the recipe's
  count-with-its-method discipline biting the person applying it: **a count is only
  as sound as the filter that produced it, and a filter that removes noise can
  remove signal wearing the same token.**
  **That file is also the one place both kinds coexist, so it must be edited
  SURGICALLY and never by bulk replace:** its `target_version=35` /
  `_current_version(conn) == 35` assertions (lines ~77, ~385, ~400) are
  migration-0035-SPECIFIC and MUST STAY 35.

  **Instruction to the executing implementer:** classify every one as HEAD-tracking
  (→ 36) or target-version-specific (stays 35) by READING it. Do not run a bulk
  `sed`. The 26 files:
  `test_b7_failure_mode_schema.py`, `test_db_v8.py`,
  `test_migration_0010_trade_chart_pattern.py`, `test_migration_0012.py`,
  `test_migration_0013.py`, `test_migration_0015_finviz_api_calls.py`,
  `test_migration_0016.py`, `test_migration_0017.py`, `test_migration_0018.py`,
  `test_migration_0019_atomic_apply.py`, `test_migration_0025_phase16.py`,
  `test_migration_0026_broad_watch_baseline.py`,
  `test_migration_0027_entry_intent.py`, `test_migration_0028_watchlist_pin.py`,
  `test_migration_0030_yfinance_calls.py`,
  `test_migration_0031_untracked_broker_position.py`, `test_migration_0032.py`,
  `test_migration_0033.py`, `test_migration_0034_h1_criteria_amendment.py`,
  `test_no_schema_change_v3.py`, `test_phase13_t3_sb1_prerequisite.py`,
  `test_temporal_log_migration.py`, `test_v20_migration.py`,
  `test_v21_migration_trade_backlinks.py`, `test_v23_migration.py`, **and
  `test_migration_0035_fills_trades_price_divergence.py`** (all under
  `tests/data/`). **The executing implementer re-runs the search — WITHOUT the
  `0035` exclusion — rather than trusting this list**; `main` may have moved, and a
  list that does not match within one or two entries is a signal to stop and ask,
  not to adjust quietly.
  *(Round 1 reported 24; this plan's own read produced 34; round 2 found the 35th
  by reading the file a filter had hidden; round 3 found the 36th by searching for
  `<=` as well as `==`. FOUR numbers, each larger than the last, none of whose
  holders had reason to doubt it — the recipe's "the feeling of having swept is
  identical to having swept", in four acts. Which is precisely why the binding
  criterion above is the SUITE and not the count.)*
- A `DEMAND_C_PRE_MIGRATION_EXPECTED_TABLES` set derived from
  `A4_TAXONOMY_PRE_MIGRATION_EXPECTED_TABLES` (no new tables required in the PRE
  set — 0036 creates rather than rebuilds; the set is inherited so provenance stays
  auditable, matching the `PHASE14_PRE_MIGRATION_EXPECTED_TABLES` precedent at
  `db.py:217`).
- The gate function keys **`if target_version < 36 or current_version != 35: return`**
  — STRICT equality on `pre_version == target - 1`, copying the shape at
  `db.py:1837`. A run-migrate-twice no-op test is included (§8.7).

### 4.3 Model + validator (same commit)

`swing/data/models.py`:

```python
PROVENANCE_CORRECTED_FIELDS: tuple[str, ...] = (
    "trades.hypothesis_label",
    "trades.candidate_id",
    "trades.trade_origin",
)
PROVENANCE_CORRECTION_APPLIED_BY: str = "operator"

@dataclass(frozen=True)
class ProvenanceCorrection:
    ...  # one field per column, provenance_correction_id: int | None pre-INSERT

    def __post_init__(self) -> None:
        # MIRRORS the migration-0036 CHECKs. Literal[...] is not runtime-
        # enforced and a CHECK fires only at INSERT; a caller building a bad
        # row must fail at CONSTRUCTION, not three statements later.
        #  - the three dates: date.fromisoformat round-trip in EXTENDED form
        #  - both contemporaneity comparisons
        #  - applied_by == 'operator'
        #  - cited_hypothesis_status_at_record == 'active'
        #  - non-empty trimmed reason and derivation_rule_version
        #  - corrected_fields_json parses to a list that is a SUBSET of
        #    PROVENANCE_CORRECTED_FIELDS
        #  - cited_recommendation_snapshot_json parses to a dict whose `id`
        #    equals cited_daily_recommendation_id and whose
        #    `evaluation_run_id` equals cited_evaluation_run_id -- so a
        #    snapshot that does not describe the row it is filed under cannot
        #    be constructed at all
        #  - entry_fill_snapshot_json's `fill_id` == entry_fill_id_at_correction,
        #    its `trade_id` == trade_id, its `action` == 'entry', and its
        #    `fill_datetime`[:10] == entry_fill_session_date (Codex R9 Major 2)
        #  - EVERY snapshot rule here MIRRORS a SQL CHECK in migration 0036
        #    (Codex R7 Major 2). The SQL layer catches raw INSERTs, which
        #    never construct this dataclass; this layer catches every caller
        #    that does. Neither is redundant and #11 requires both in ONE
        #    commit.
        #  - cited_pipeline_run_snapshot_json gets the SAME treatment (Codex
        #    R4 Major 2): parses to a dict whose `id` == cited_pipeline_run_id,
        #    `evaluation_run_id` == cited_evaluation_run_id,
        #    `state` == 'complete', and `finished_ts` ==
        #    cited_pipeline_finished_ts_raw -- the RAW column, because the
        #    snapshot is the pipeline row verbatim and the normalized bound is
        #    a different clock domain (Codex R6 Critical 1). Without it the R3
        #    upper-bound proof is
        #    a TEXT NOT NULL column that accepts `{}` -- an unchecked JSON
        #    decoration standing in for the citation it was added to be.
        #    (Existence != completeness: the first draft validated ONE of the
        #    two snapshots and the omission was invisible.)
```

The `__post_init__` mirror is the #11 requirement and is pinned by a test that
walks the live `PRAGMA table_info` + the CHECK text and asserts every constraint has
a validator counterpart (§8.7).

---

## 5. THE SERVICE — `swing/trades/cohort_provenance_correction.py`

### 5.1 Public surface

```python
__all__ = [
    "COHORT_CORRECTED_FIELDS", "APLUS_BUCKET", "REQUIRED_RECOMMENDATION",
    "UNSET_TRADE_ORIGIN",
    "CallerHeldTransactionError", "CohortProvenanceCorrectionError",
    "CohortProvenanceCorrectionPreview", "CohortProvenanceCorrectionResult",
    "correct_cohort_provenance", "preview_cohort_provenance_correction",
]
```

`preview_...` runs `_authorize` (every read-only check in §3.5) and returns
before/after values plus the two anchors and `F`, writing nothing. It raises the
same refusals the write path raises — one authorization function, two entry points,
so `--dry-run` cannot diverge from apply.

**THAT PROMISE IS ONLY TRUE IF EVERY VALIDATION LIVES IN `_authorize` (Codex R2
Major 4).** The first draft validated only the FILL timestamp there and left the
cited dates to `ProvenanceCorrection.__post_init__` and the DDL CHECKs — which
`--dry-run` never reaches, because it constructs no model and inserts no row. The
columns are unconstrained: `evaluation_runs.run_ts` and `action_session_date` are
bare `TEXT NOT NULL` (`0001_phase1_initial.sql`), `daily_recommendations
.action_session_date` likewise (`0003_phase2_pipeline_trades.sql`), and neither
`EvaluationRun` nor `DailyRecommendation` validates dates in `__post_init__`
(`models.py:202-217, 520-533`). So a schema-legal `'2026-02-30'` passes a LEXICAL
`<=` comparison in preview and the apply path then fails at model construction —
preview says GO, apply says NO. The same lexical hazard picks the wrong
`hypothesis_status_history` interval.

**Therefore `_authorize` canonically parses and round-trip-validates, BEFORE any
comparison:** both cited `action_session_date` values, `evaluation_runs.run_ts`, the
window upper bound (`pipeline_runs.finished_ts`), the `effective_from` /
`effective_to` bounds of every interval it inspects, **`recorded_at` on every
inspected interval (Codex R5 Major 1)**, and every COMPETITOR row's
`action_session_date` and `run_ts` (§3.3, Codex R4 Major 3). Extended-form
round-trip only (the `date.fromisoformat` basic/week-date acceptance item 5
documents at `entry_date_correction.py:299-308` applies here identically). §8.8
asserts preview and apply refuse **identically** on each malformed value — the test
that would have caught this.

**PARSING IS NOT ENOUGH — A SESSION ANCHOR MUST BE A SESSION (Codex R10 Major 1).**
Round 5's validation checked ISO parseability and extended-form round-trip, which
accepts any valid calendar date — so `action_session_date='2026-08-09'` (**a
Sunday**, verified) passes both layers and satisfies `<= F` against a Monday fill.
That is an IMPOSSIBLE framework record: `action_session_for_run`
(`dates.py:123`) always derives an NYSE session, so a non-session anchor cannot
come from the real emitter and its presence IS corruption — the same class §3.0
already refuses for malformed timestamps, one level up in meaning rather than in
syntax. Manufacturing a contemporaneity verdict from it violates the binding rule
as squarely as a mis-parsed date does.

So every parsed date is additionally required to satisfy
`swing.evaluation.dates.is_trading_session` — **the repo's existing helper, written
for precisely this** (its docstring: *"Used to reject a non-session date offered as
a session ANCHOR by an external caller: a weekend/holiday date can otherwise slip
past a `sessions_behind` proximity check and corrupt a session-keyed ledger"*), and
already used this way by item 5 (`entry_date_correction.py:309-318`). Applied to:
both cited `action_session_date` values, **every COMPETITOR candidate's**
action-session date (§3.0 — a hidden competitor is exactly how the last-word guard
gets fooled), and **`F`** itself. §8.8 adds Sunday and NYSE-holiday discriminators
at all three sites, preview/apply identical.

**Live cost, measured: zero.** Checked with `is_trading_session` over the whole DB —
**0 of 46** fills, **0 of 138** `evaluation_runs.action_session_date`, and **0 of
182** `daily_recommendations.action_session_date` fall on a non-session date.

**`recorded_at` is DECISIVE and was the one omission (Codex R5 Major 1).** It is the
whole retrospective guard (§3.4.1), the column is bare `TEXT NOT NULL`
(`0017_phase9_risk_policy_and_reconciliation.sql`), and
`HypothesisStatusHistory.__post_init__` does not validate it (`models.py:1599`). So
`recorded_at=''` sorts before EVERY valid `run_ts`, satisfies `recorded_at <=
run_ts` lexically, and authorizes an interval whose recording time is unknowable —
through the guard added to enforce contemporaneity. The audit CHECK is lexical too
and would accept the frozen assertion. **The lesson is the same one §3.3 records
one level over: a validation manifest is only complete if it covers every value the
DECISION reads, and `recorded_at` was decisive precisely because it was newest.**

**The preview shows what it knows and says what it does not.** It does NOT predict
downstream cohort reads (predicting `in_flight_sample` would re-implement
`compute_hypothesis_progress_breakdown` in the preview path — item 5's
`aggregates_after` lesson, `entry_date_correction.py:226-233`).

### 5.2 Transaction contract

Identical to item 5 (`entry_date_correction.py:1341-1375`) because it is the
project's contract, not that module's invention: the outer function ALWAYS owns
`BEGIN IMMEDIATE` / COMMIT / ROLLBACK and **REJECTS** a caller-held transaction —
never auto-detects, because an auto-detect guard re-introduces the race the explicit
lock closed (CLAUDE.md, SQLite section). The inner `_correct_cohort_provenance_inner`
never commits, so a future flow can compose it under a SAVEPOINT. Every callee is
repo-level; none opens `with conn:`.

### 5.3 Write sequence (inner)

1. `_authorize(...)` → `_Authorized` (trade, fill, `F`, `C`, `R`, `D`, both
   anchors, the as-of hypothesis + its covering interval, derived
   label/origin/candidate_id, and the existing correction row if any).
2. **The already-applied check is INSIDE `_authorize` at rung 3** (§3.5), not here —
   it must precede the unset-state gate or it is unreachable. Identical request →
   `_authorize` returns an `already_applied` marker and the inner function returns
   the existing correction id having written nothing (SELECT-first idempotency,
   CLAUDE.md).
3. `pre_values` = the three current column values, read from the trade row.
4. ONE repo writer:
   `update_cohort_provenance(conn, trade_id=..., hypothesis_label=..., candidate_id=..., trade_origin=...)`
   — a LITERAL three-column `UPDATE trades SET ... WHERE id = ?` in
   `swing/data/repos/trades.py`, raising `ValueError` on `rowcount == 0`. **No
   dynamic SQL, no field name from the operator** — the operator supplies two row
   IDs and a reason, never a column name or a value.
5. `insert_provenance_correction(conn, ProvenanceCorrection(...))` — the audit row,
   carrying both citation FKs, the hypothesis + interval FKs, all frozen anchors,
   `F`, the four clock columns, the DR snapshot, `derivation_rule_version`,
   `pre_value_json`, `applied_value_json`, `corrected_fields_json`,
   `risk_policy_id_at_correction` (via the existing
   `_maybe_get_active_risk_policy_id`), and the composed reason.

**There is no step 6.** V1 writes exactly one correction row per trade and never
supersedes; `ux_provenance_corrections_trade` makes a second row impossible even if
the service were wrong.

**No `trade_events` row is emitted, deliberately.** `trade_events.event_type` is a
CHECK enum of exactly seven values — verified by reading the live DDL:
`('entry','stop_adjust','note','exit','flag','pre_trade_edit','reconciliation_auto_correct')`.
None of them truthfully names an operator cohort-provenance correction; item 5
already carries `reconciliation_auto_correct` as recorded naming debt
(`entry_date_correction.py:1551-1556`) and repeating it here would be worse, because
there is no reconciliation anywhere in this arc. Writing a MISLABELLED audit record
alongside a purpose-built correct one is the precise failure this arc exists to stop.
**Consequence, named:** any `trade_events`-backed timeline will not show this
correction; `swing journal provenance-corrections` (§6) is the read surface.
Widening the CHECK is a separate schema decision for CHARC (§12.3).

### 5.4 Composed reason

The stored reason = the operator's `--reason`, plus a server-composed clause the
operator cannot know, naming: the two cited row ids and their anchors, `F`, the
matched hypothesis, the derived label VERBATIM, and — when it applies — that the
derived label carries a `failed:` suffix for a criterion whose result was `na`
rather than `fail` (§1.6), so the audit trail explains its own string.

---

## 6. CLI

`swing journal correct-cohort-provenance TRADE_ID` in the existing `journal` group,
beside `correct-entry-date`.

| option | required | role |
|---|---|---|
| `--cited-candidate` INT | yes | the `candidates.id` cited |
| `--cited-recommendation` INT | yes | the `daily_recommendations.id` cited; **CONFIRMS** the row derived from the candidate's run, never selects it |
| `--reason` TEXT | **`required=False, default=None` at the parser** | non-empty, enforced by `_authorize` on the WRITE path only |
| `--dry-run` | no | full validation + before/after; writes nothing |

**`--reason` MUST NOT be `required=True` (Codex R5 Major 2), and this is the one
place the CLI could silently void a service-level guarantee.** §3.5 rung 2 promises
that an already-applied replay returns its existing correction id BEFORE any payload
is inspected — including with no reason at all. **Click rejects a missing required
option during PARSING, before the command body runs**, so a `required=True`
declaration would make that promise true for direct service calls and false for the
commissioned operator-facing surface: the operator replaying a correction would get
`Missing option '--reason'` instead of the existing id. Declared optional at the
parser; `_authorize` raises the non-empty-reason refusal only on the path that
writes. §8.3 tests this **at the CLI level** — a service-level test cannot see it.

**Exactly five declared parameters. There is no `--supersede`** (Codex R1 Major 1:
V1 records provenance once; §3.5 rung 3 either recognises an identical re-run or
refuses).

**There is deliberately NO `--label`, NO `--origin`, NO `--hypothesis` option** —
brief §6 test 3's "preferred" form. The surface takes no value parameter at all, so
free-typing is not refused at runtime, it is **unrepresentable**. §8.3 pins this at
two levels (the click parameter manifest, and the module-symbol manifest).

Plus a read command `swing journal provenance-corrections [TRADE_ID]` printing each
correction with its citations, its frozen anchors, its hypothesis interval, and any
**CITATION DRIFT** lines (§3.4.2). Without it the audit table has no supported
reader and D36's "verify against the audit trail" would need raw SQL.

All output ASCII (`->`, not an arrow glyph): Windows cp1252 crashes on non-ASCII in
`click.echo`, and `capsys` hides it.

---

## 7. THE GENERIC-CORRECTOR INTERACTION

**Decision: YES — the three cohort keys join `_RESERVED_JOURNAL_FIELDS`**
(`swing/trades/reconciliation_auto_correct.py:156`), matching CHARC's leaning and
for the same coupled-surface reason as `entry_date`:

```python
_COHORT_PROVENANCE_COUPLED_SURFACE = "swing journal correct-cohort-provenance"
_RESERVED_JOURNAL_FIELDS = {
    ...existing four...,
    ("trades", "hypothesis_label"): _COHORT_PROVENANCE_COUPLED_SURFACE,
    ("trades", "candidate_id"):     _COHORT_PROVENANCE_COUPLED_SURFACE,
    ("trades", "trade_origin"):     _COHORT_PROVENANCE_COUPLED_SURFACE,
}
```

**Why.** The three are a COUPLED TRIPLE, not three independent columns: a
`candidate_id` pointing at an `aplus` row beside a `trade_origin` of
`manual_off_pipeline` is an internally contradictory cohort assignment, and the
generic path applies operator-supplied fields SEQUENTIALLY
(`_handle_multi_field_correction`) with no cross-field coherence check. Worse, the
generic path takes an operator-supplied VALUE — so `hypothesis_label` reachable
through it is precisely the free-typing surface brief §2 consequence 1 forbids, with
an audit trail attached. Reserving it routes cohort writes to the one surface that
derives instead of accepting.

`_reservation_applies` (`reconciliation_auto_correct.py:343`) returns `True`
unconditionally for `affected_table != 'fills'`, so `trades`-scoped reservations
need no per-row scoping — the three entries are sufficient as written.

**What this closes and what it does not.** It closes every generic tier-1/2/3
journal write, which §1.5 established is the only other UPDATE path. It does not
close a hand-written SQL edit, which nothing can.

**Regression risk, checked:** no live `reconciliation_corrections` row has ever
targeted these fields (§1.5, 37 rows read), so the reservation cannot break a
replay of anything that has happened. A test asserts the generic path now refuses
each of the three with a message naming the new surface.

---

## 8. TESTS

New file `tests/trades/test_cohort_provenance_correction.py` (mirroring
`tests/trades/test_entry_date_correction.py`), plus additions to
`tests/data/` for the migration and `tests/cli/` for the command.

Fixtures are built from REAL emitter shapes: `evaluation_runs` rows with the live
1-day and 3-day `data_asof`/`action_session` gaps, `candidates` + `candidate_criteria`
rows with the live criterion names and `pass`/`fail`/`na` results, entry fills with
the synthetic `T16:00:00` convention. **No test depends on the live DB or on a real
trade id.**

### 8.1 The acceptance case (brief §5, both modes)

A CADL-shaped fixture: candidate `aplus` in a run with `data_asof='2026-08-10'`,
`action_session='2026-08-11'`; a `today_decision` DR row in the same run; an entry
fill on `2026-08-12`; criteria with 17 `pass` and `TT8_rs_rank='na'`. Asserts the
three written values, the audit row's two FKs, both frozen anchors, and — critically
— the exact label string `"A+ baseline (aplus); failed: TT8_rs_rank"` (§1.6). A
second variant with all criteria `pass` asserts `"A+ baseline (aplus)"`, pinning
that the suffix is a function of the record and not a constant.

### 8.2 Brief §6 test 1 + test 2 — the anchor discriminator

T2a … T2h exactly as specified in §3.2.2, §3.2.3 and §3.2.4, each docstring
carrying **both** anchor values and the verdict each produces. Each of T2a-c is
verified to FAIL against a deliberately-wrong implementation (`data_asof_date`
substituted) during the red phase, and T2f/T2g against a `trades.entry_date` /
latest-fill implementation — those substitutions ARE the red step, not a thought
experiment.

### 8.3 Brief §6 test 3 — free-typing is unrepresentable

Two levels, because one is a claim about the CLI and the other about the service:

- The click command's `params` manifest is READ and asserted to be exactly
  `{trade_id, cited_candidate, cited_recommendation, reason, dry_run}` — five
  entries, no label/origin/hypothesis parameter of any name. (A manifest READ, not a
  name grep: a grep for `"--label"` bounds the family from below and would miss
  `--hypothesis-label` or a differently-spelled option.)
  **`help` is NOT a member** — Codex R1 Major 4b, and verified empirically on the
  installed click 8.3.1: for a command with an argument and two options,
  `[p.name for p in cmd.params]` → `['trade_id', 'foo', 'dry_run']` while
  `[p.name for p in cmd.get_params(ctx)]` → `[..., 'help']`. The auto help option is
  appended by `get_params(ctx)` at parse time and never lives in `.params`. Help
  availability is asserted separately by invoking `--help`.
- `inspect.signature(correct_cohort_provenance)` is asserted to accept no parameter
  carrying a cohort VALUE.
- A positive control: given a fixture whose sibling cohort rows carry a DIFFERENT
  label, the written label still equals the one derived from the cited record —
  proving the value comes from the record and not from the cohort.
- **CLI-LEVEL idempotency with `--reason` OMITTED** (Codex R5 Major 2): invoke the
  real click command via `CliRunner` on an already-corrected trade WITHOUT
  `--reason` → exit 0 and the existing correction id printed, NOT
  `Missing option '--reason'`. Plus a FRESH request with `--reason` omitted → a
  clean refusal from `_authorize`, nothing written. *A service-level test passes
  under either parser declaration and therefore cannot pin this.*

### 8.4 Brief §6 test 4 — audit round-trip and re-application

- Apply → the audit row carries `cited_candidate_id`, `cited_daily_recommendation_id`,
  `cited_hypothesis_id`, `cited_hypothesis_status_history_id`, all frozen anchors,
  `entry_fill_session_date`, `entry_fill_id_at_correction`,
  `entry_fill_snapshot_json`,
  `cited_recommendation_snapshot_json`,
  `derivation_rule_version`, `pre_value_json` (all three pre-values,
  `hypothesis_label` NULL and `trade_origin` `manual_off_pipeline`) and
  `applied_value_json`.
- Apply the identical request again → **no second row**, the same id returned,
  `SELECT COUNT(*)` unchanged, and the trade row byte-identical.
  *This test is only reachable because §3.5 rung 2 precedes rung 4 — it is the
  regression pin for Codex R1 Major 1, and it FAILS under the unset-gate-first
  ordering.*
- **Re-apply the same citation with an EMPTY `--reason`** → still the idempotent
  return of the existing id, NOT a reason-validation refusal (Codex R3 Major 4:
  SELECT-first idempotency must precede payload validation — CLAUDE.md's rule
  verbatim). *The happy-path test above uses a valid reason and therefore cannot
  catch this ordering; this one can.* Same with a `None` reason.
- Apply a DIFFERENT citation to the same trade → **refusal** naming the existing
  correction id; count unchanged; trade row unchanged.
- Two `provenance_corrections` rows for one trade raise `sqlite3.IntegrityError` on
  a RAW INSERT — `ux_provenance_corrections_trade`, exercised at the schema rather
  than through the service.
- An attempt to INSERT a row whose frozen candidate anchor post-dates
  `entry_fill_session_date`, or whose `cited_hypothesis_status_at_record` is not
  `'active'`, or whose snapshot JSON names a different `id`, raises
  `sqlite3.IntegrityError` / `ValueError` respectively — the §4.1 CHECKs and the
  `__post_init__` mirror, each exercised directly.
- **Citation drift is reported, not swallowed:** after a correction, UPDATE the
  cited DR row's `evaluation_run_id` (the real `upsert_recommendation` behaviour,
  §3.4.2) and assert `swing journal provenance-corrections` emits a
  `CITATION DRIFT: evaluation_run_id was <frozen> now <live>` line. Without this the
  frozen snapshot is decoration.
- **The PIPELINE snapshot gets the same round-trip, rejection and drift coverage as
  the recommendation snapshot** (Codex R4 Major 2) — **and the rejection is asserted
  at BOTH layers, because they catch different callers (Codex R7 Major 2).** A RAW
  `conn.execute` INSERT never constructs the dataclass, so a `__post_init__`-only
  design would ACCEPT `{}` and the required test would be red. Therefore:
  (a) **RAW INSERT** of `{}`, malformed JSON, **a PARTIAL object missing EACH
  required key in turn — one case per key, not merely `{}` (Codex R8 Major 1: the
  `IS NOT NULL`-on-`$.id`-only form ACCEPTED `{"id":172}`)**, a snapshot naming a
  different `id`, `state != 'complete'`, or
  `finished_ts != cited_pipeline_finished_ts_raw` → `sqlite3.IntegrityError` from
  the §4.1 `CASE WHEN json_valid(...) COALESCE(...)` CHECKs. The malformed case
  asserts `IntegrityError` SPECIFICALLY, not any exception — the exception-TYPE
  contract `tests/data/test_migration_0033.py` already pins for this repo's other
  JSON CHECK;
  (b) **dataclass construction** of the same five shapes → `ValueError` from
  `__post_init__` (the #11 mirror);
  and a field-by-field drift test per snapshot key. Without both, the R3
  upper-bound citation is a green-suite decoration.
- **The FILL anchor is drift-checked by RECOMPUTATION, not by re-reading the frozen
  value** (Codex R4 Major 1): after a correction, move the entry fill through the
  real `swing.data.repos.fills.update_fill_datetime` and assert
  `CITATION ANCHOR DRIFT`; then a two-entry-fill fixture where the move hands
  authority to the OTHER fill, asserting the drift line names the new fill id; then
  a move large enough that the recomputed `F` precedes a cited anchor, asserting
  `CITATION INVALIDATED`. A hand-written `UPDATE fills` would not prove the
  production path reaches this.
- **Drift is PARAMETERIZED over every mutable column** (Codex R2 Major 3), driven
  from the `DO UPDATE SET` list in `repos/recommendations.py:18-27` — i.e.
  `evaluation_run_id`, `data_asof_date`, `action_text`, `entry_target`,
  `stop_target`, `shares`, `risk_dollars`, `risk_pct`, `rationale`. One case per
  column, each asserting its own drift line. The three the first draft omitted
  (`action_text`, `risk_dollars`, `risk_pct`) are ORDINARY members here, which is
  the point: the snapshot column set is PRAGMA-derived, so an omission is not
  expressible.

### 8.5 Brief §6 test 5 — cohort read flips, computed under BOTH paths

The values are §1.7's measured table, re-derived on a seeded fixture rather than on
the live DB:

| assertion | PRE | POST |
|---|---|---|
| `list_trades_for_cohort("A+ baseline")` contains the trade | **False** | **True** |
| …with `entry_intent='standard'` | **False** | **True** |
| H1 `in_flight_sample` | **0** | **1** |
| H1 `current_sample` | **n** | **n** (unchanged; the trade is OPEN) |
| H1 `target_sample` | **20** | **20** (registry column) |

Plus the CLOSED variant — the same fixture with the trade in `state='closed'` and an
exit fill — asserting `current_sample` moves **n → n+1** and `in_flight_sample`
stays 0. That variant is what makes the open-trade assertion non-vacuous: without
it, "current_sample unchanged" is indistinguishable from "the correction did
nothing".

### 8.6 Derivation-drift pins

- `derive_trade_origin` on a synthetic DB whose latest complete run holds an
  `aplus` row for the ticker returns the SAME literal this module writes, for every
  `EntryPath` member — so the two mappings cannot drift apart silently.
- The written label satisfies
  `label_matches_hypothesis(label, "A+ baseline")` — the property the cohort read
  actually depends on, asserted separately from the exact string so a future
  `_descriptive_label` change breaks the string test loudly rather than breaking
  cohort membership silently.
- `APLUS_TRADE_ORIGIN` is imported from `swing.metrics.funnel`, asserted to be the
  same object, so no third copy of `"pipeline_aplus"` exists.
- **Hypothesis status is evaluated AS OF the record, not as of now** (§3.4.1):
  (a) H1 PAUSED across the whole window but ACTIVE at test time → **REFUSE**
  (this FAILS an implementation passing `list_hypotheses(conn)` straight through —
  the whole point of the fix);
  (b) H1 ACTIVE across the window but CLOSED at test time → **ACCEPT**, and the
  audit row cites the historical interval's `history_id`;
  (c) **a mid-window status transition, built the way the production writer builds
  one** — `UPDATE prior SET effective_to = t` then `INSERT successor` at the same
  `t`, per `repos/hypothesis_status_history.py:12-18`, with
  `run_ts < t < finished_ts` → **REFUSE, asserting the SPECIFIC
  status-changed-inside-the-window message** (Codex R3 Major 1). *The assertion on
  the exact message is the test: round 2's version asserted a shape — "two
  intervals COVERING the window" — that the writer cannot produce, so it would have
  been silently weakened into a generic zero-match assertion and proved nothing.*
  (d) a HOLE in the history spanning the window → **REFUSE** with the
  gap message (distinct from (c));
  (e) **a DIFFERENT hypothesis whose entire history post-dates the window (H5's real
  shape: created 2026-06-09, cited record from May) → the correction still
  SUCCEEDS**, that hypothesis merely absent from the as-of registry. *Regression pin
  for Codex R2 Major 2; FAILS the round-1 fix, which refused outright.*
- **The window, not an instant** (Codex R2 Major 1): a fixture whose status flips
  strictly BETWEEN `run_ts` and `pipeline_runs.finished_ts` → **REFUSE**. An
  instant-only implementation reading `run_ts` ACCEPTS. Plus: zero pipeline rows,
  two pipeline rows, one non-`complete` row, and a cited pipeline row whose
  `evaluation_run_id` names a DIFFERENT run → **REFUSE** with the cannot-bound /
  wrong-owner message (Codex R3 Major 3).
- **Retrospective intervals are REFUSED** (Codex R3 Critical 1): an interval whose
  `recorded_at` post-dates `run_ts` (migration 0017's real seed shape) → **REFUSE**,
  message naming 0017; a contemporaneous one → **ACCEPT**. Both directions
  asserted. A raw INSERT of an audit row violating
  `cited_hypothesis_status_recorded_at <= cited_run_ts_utc` raises
  `sqlite3.IntegrityError`.
- **CLOCK-DOMAIN normalization** (§3.4.1-clock, Codex R5 Critical 1): a
  production-shaped fixture where the pipeline window is written in naive LOCAL
  (`2026-08-10T17:30:26` → `T17:44:45`) and a status transition physically inside it
  is written in naive UTC (`2026-08-11T03:35:00.000`) → **REFUSE**. A text-comparing
  implementation sees the old interval covering the whole window and ACCEPTS. Plus
  the margin: an interval boundary 12 hours from a window bound → **REFUSE**; one
  107 days away (the live CADL distance) → **ACCEPT**.
- **A POSITIVE normalization assertion, because the refusal tests above cannot see
  a skipped normalization (Codex R6 Critical 1).** The ±24h margin fires whether or
  not the bounds were converted, so a refusal-only suite passes an implementation
  that stores raw local values. On the ACCEPTING CADL-shaped case, assert the exact
  stored values:
  `cited_run_ts_raw == '2026-08-10T17:30:26'`,
  `cited_run_ts_utc == '2026-08-11T03:30:26'`,
  `cited_pipeline_finished_ts_raw == '2026-08-10T17:44:45'`,
  `cited_status_window_upper_utc == '2026-08-11T03:44:45'`
  — and assert `_utc != _raw` for both pairs. **The DATE rolls** (08-10 → 08-11), so
  this also pins that the conversion crossed midnight rather than merely shifting
  hours. Plus: preview and apply agree on an interval whose UTC date is one day
  after the raw local run date.
- **Snapshot-vs-bound domain pairing** (Codex R6 Critical 1): a RAW INSERT whose
  pipeline snapshot `finished_ts` equals `cited_status_window_upper_utc` (the
  round-5 shape) → **`sqlite3.IntegrityError`** from the §4.1 CHECK, because the
  snapshot must match `cited_pipeline_finished_ts_raw`. *This is the test that fails
  the round-5 design, in which the two rules could not both be satisfied — and it is
  a genuine RAW-insert test only because §4.1 now pins it in SQL.*
- **A `{}` snapshot is REJECTED BY THE CHECK, not merely by the validator**
  (Codex R7 Major 2 + the NULL-CHECK trap): verified empirically that
  `json_extract('{}','$.id')` is NULL, that `NULL = <id>` is NULL, and that a
  SQLite CHECK **passes** on NULL — so the guard form without `IS NOT NULL`
  accepts `{}`. The test plants `{}` by raw INSERT and asserts rejection, which
  fails the unguarded CHECK form.
- **A snapshot naming a DIFFERENT fill is rejected at BOTH layers** (Codex R9
  Major 2): `entry_fill_id_at_correction=45` with
  `{"fill_id":999,"trade_id":23,"action":"entry","fill_datetime":"2026-08-12T16:00:00"}`
  → `sqlite3.IntegrityError` by raw INSERT and `ValueError` by construction. Same
  for a snapshot whose `trade_id` names another trade or whose `action` is not
  `'entry'`.
- **THE ROWID-REUSE DISCRIMINATOR (Codex R11 Major 1)** — the sharpest test in
  §8.4, and it fails the round-9 design. Seed the cited entry fill as
  **`MAX(fill_id)`** for the whole table, apply the correction, then run the
  production date-PRESERVING `split_into_partials`. **SQLite reuses the deleted
  rowid** — verified: fill 45 deleted, the reinserted partial came back as
  **`fill_id=45` with the identical `fill_datetime`**. Assert the reader STILL emits
  `CITATION ANCHOR DRIFT`. *An implementation comparing only `(fill_id, date)` sees
  a perfect match and reports NO drift on a row that was deleted and replaced —
  a false clean in the audit command, and it would ALSO have turned the composition
  test below red.* Pair it with the control: the same split where the cited fill is
  NOT the max, so no reuse occurs and drift is reported for the ordinary reason.
- **COMPOSITION with the real split path** (Codex R7 Major 1 + R9 Major 2 + R11
  Major 1): apply a provenance correction, then run the production
  `split_into_partials` handler on the cited entry fill in its date-PRESERVING form
  → **it must SUCCEED** (no FK `IntegrityError`); `entry_fill_id` goes NULL **and
  STAYS NULL through the reinsert** (verified: an INSERT reusing the number does not
  restore an FK) **while `entry_fill_id_at_correction` and the snapshot SURVIVE
  UNCHANGED** — the assertion that the audit can still name its anchor after the
  fill is gone; and
  `swing journal provenance-corrections` reports the replacement as
  `CITATION ANCHOR DRIFT` naming the snapshot's original fill id. *This is the test
  that fails an `ON DELETE RESTRICT` design, and it is a COMPOSITION test — the
  class the review ladder structurally does not cover (CLAUDE.md #31 related).*
- **THE SELECTION-RULE DISCRIMINATORS (§3.0, Codex R8 Majors 2 and 3)** — one per
  site, each built so a SQL-side filter/order would hide the malformed row:
  (a) **fill selection:** two entry fills, canonical `2026-08-12T16:00:00` and
  basic-form `20260811T160000` — verified `'2026-08-12T16:00:00' < '20260811T160000'`
  is **True**, so a SQL `ORDER BY ... LIMIT 1` returns the 08-12 row and never sees
  the other → the local resolver must **REFUSE** on the malformed fill. *An
  implementation calling `get_authoritative_entry_fill` accepts and computes a
  day-later, more-permissive `F`.*
  (b) **interval selection:** a valid interval covering the window PLUS a
  malformed basic-form interval that genuinely overlaps it but that a lexical
  `WHERE` excludes → **REFUSE** with the malformed-history message. *An
  implementation filtering in SQL sees one covering interval and ACCEPTS.*
  (c) **competitor candidates:** §3.3's basic-form competitor.
  Plus an equivalence pin: on a CANONICAL-only corpus the local fill resolver and
  `get_authoritative_entry_fill` return the same fill, so the divergence stays
  scoped to malformed data.
- **`recorded_at` validation** (Codex R5 Major 1): `recorded_at=''` on the otherwise
  covering interval → **REFUSE**, in BOTH preview and apply. *An empty string sorts
  before every valid `run_ts` and would otherwise satisfy the retrospective guard
  lexically.* Same for a basic-form and an offset-bearing `recorded_at`.
- **The label's join-key property is pinned at write time** (§3.4.1a): assert
  `label_matches_hypothesis(written_label, <registry name for cited_hypothesis_id>)`
  and that `cited_hypothesis_name_at_correction` equals that name.

### 8.7 Schema / migration / mirror

- Migration applies 35 → 36; `schema_version` = 36; the table, both indexes and
  every CHECK exist (read from `sqlite_master`, not assumed).
- Re-running the migration is a clean no-op.
- The backup gate fires at `current_version == 35` and NOT at 34 or 36 (strict
  equality, both directions).
- The `__post_init__` mirror test: every CHECK in the 0036 DDL has a
  `ProvenanceCorrection.__post_init__` counterpart that rejects the same value.
- FK enforcement: inserting a correction naming a nonexistent candidate raises;
  deleting a cited candidate with a live correction raises (RESTRICT).

### 8.8 Reservation + refusal ladder

- Each of the three cohort fields is refused by the generic corrector, message
  naming `swing journal correct-cohort-provenance`.
- One test per §3.5 rung, each asserting the message names the specific cause and
  that **nothing was written** (all three columns AND the audit table re-read).
- **DR cardinality (§3.4 eligibility 3, Codex R1 Major 3):** zero same-run
  same-ticker `today_decision` rows → REFUSE naming the count; **two** such rows
  (schema-legal because the unique index is keyed on `action_session_date`, not on
  `evaluation_run_id`, and `upsert_recommendation` rewrites `evaluation_run_id`) →
  REFUSE naming the count and both ids, **even when the operator's supplied id is
  one of them** — the cardinality refusal precedes the confirmation compare, so a
  supplied id can never break a tie.
- `CallerHeldTransactionError` when called inside an open transaction.
- A refusal mid-sequence leaves no partial write (forced by patching the audit
  insert to raise, then asserting the trade row is unchanged after rollback).
- **NON-SESSION ANCHORS ARE REFUSED (Codex R10 Major 1)**, preview and apply
  identical, at all three sites: a cited `action_session_date` of `'2026-08-09'`
  (**a Sunday**) with a Monday `F`; the same on a HIDDEN COMPETITOR candidate row
  that would otherwise win the last-word guard; and a fill whose `F` lands on an
  NYSE holiday. Each asserts the specific not-a-trading-session message. *Parsing
  alone accepts all three — the round-5 validation would have passed every one.*
- **PREVIEW AND APPLY REFUSE IDENTICALLY (Codex R2 Major 4).** Parameterized over
  each malformed cited timestamp — `evaluation_runs.action_session_date =
  '2026-02-30'` (schema-legal, lexically `<=` a later `F`), `run_ts = 'garbage'`,
  `daily_recommendations.action_session_date = '20260811'` (basic-form ISO), and a
  `hypothesis_status_history.effective_from` of `'2026-13-01'`. For each, assert
  `preview_...` and `correct_...` raise the SAME refusal type with the SAME message.
  *This is the test that fails the round-1 design, where the checks lived only in
  `__post_init__` / the DDL and preview reached neither.*

### 8.9 Full fast suite

`python -m pytest -m "not slow" -q` to GREEN **before** the Codex loop (recipe §2),
and again on the final head.

---

## 9. TASK LADDER (TDD; one red→green→commit per task)

| # | commit | content |
|---|---|---|
| 1 | `test(trades): Task 1 — cohort-provenance fixture builders` | fixture helpers producing real-shaped runs/candidates/criteria/DR/fills; no production code |
| 2 | `feat(data): Task 2 — migration 0036 + ProvenanceCorrection model + validator` | **#11: DDL + constants + `__post_init__` + `EXPECTED_SCHEMA_VERSION` + backup gate in ONE commit**, **plus every literal-35 test pin (>=36 across the 26 files enumerated in §4.2, EACH CLASSIFIED BY READING, no bulk `sed`) — and the task is done when the FULL fast suite is green, not when the list is exhausted (§4.2)**; tests §8.7 |
| 3 | `feat(data): Task 3 — provenance_corrections repo + candidate/DR/trade readers-writer` | `repos/provenance_corrections.py`; `fetch_candidate_by_id` (returns id + `evaluation_run_id` + a hydrated `Candidate` — the existing `fetch_candidates_for_run` cannot serve, because `Candidate` carries **no `id` field**, verified at `models.py:177-199`); `get_daily_recommendation_by_id` + `list_today_decisions_for_run_ticker` + `snapshot_recommendation_row` (PRAGMA-derived column set, §3.4.2) in `repos/recommendations.py`; the UNFILTERED `list_history_for_hypothesis` reused from `repos/hypothesis_status_history.py` (NOT a new filtered reader — §3.0) + a local validated authoritative-entry-fill resolver in the service (NOT `get_authoritative_entry_fill` — §3.1.3); `evaluation_run_persistence_bound` (the single-complete-`pipeline_runs` upper bound, §3.4.1) in `repos/pipeline.py`; `update_cohort_provenance` in `repos/trades.py` |
| 4 | `feat(trades): Task 4 — the contemporaneity gate + anchor discriminators + ALL date validation + the clock constant` | `_authorize`'s anchor half incl. the `F` column choice, the offset refusal, and the canonical round-trip validation of every cited date/timestamp AND every competitor row's (§5.1, §3.3); **plus the ENVELOPE-EXTENSION constant `PIPELINE_LOCAL_TIMEZONE` in `swing/evaluation/dates.py` with both existing defaults repointed and a three-consumer pin (§0, §3.4.1-clock) — do NOT start this task until CHARC has approved that extension**; tests §8.2 (T2a-T2h) + the preview/apply-identical malformed cases **first**, each verified red against its wrong implementation |
| 5 | `feat(trades): Task 5 — the last-word guard + citation binding + DR cardinality` | §3.3 + §3.4 eligibility 3; tests incl. the multi-row CADL-shaped ticker and the two-DR-row case |
| 6 | `feat(trades): Task 6 — value derivation (as-of status + matcher + label + origin)` | §3.4, §3.4.1; tests §8.1, §8.6 |
| 7 | `feat(trades): Task 7 — the write path, audit row, idempotency, drift reporting` | §5.3, §3.4.2; tests §8.4 |
| 8 | `feat(cli): Task 8 — correct-cohort-provenance + provenance-corrections` | §6; tests §8.3 |
| 9 | `feat(trades): Task 9 — reserve the three cohort fields` | §7; tests §8.8 |
| 10 | `test(metrics): Task 10 — cohort read flips both paths` | §8.5 |

Conventional commits, task id in the subject, no `Co-Authored-By`, no `--no-verify`,
no amend; final `-m` paragraph plain prose.

---

## 10. ACCEPTED LIMITATIONS — each with its reason, challenge invited

These ride every Codex review prompt verbatim, per brief §7.

1. **`bucket='aplus'` only.** *Reason:* `origin.py:69-72` maps `watch` to one of two
   origins by `entry_path`, which is persisted nowhere, so a watch correction would
   have to COMPOSE `trade_origin`. This is the evidence rule's own boundary, not a
   scope cut. *V2 dependency:* persisting the entry path, which is an ENTRY-side
   schema change.
2. **`recommendation='today_decision'` only.** *Reason:* `near_trigger` is not the
   framework recording a decision, and 58 of the 182 live DR rows (all
   `near_trigger`) have no candidate row in their own run at all.
3. **Both citations mandatory; annotations and any post-entry record permanently
   inadmissible.** *Reason:* the Demand-B guard, made structural by the two
   `NOT NULL` FKs (brief §4). Deliberate, and to be kept.
4. **Provenance is recorded ONCE per trade; there is no re-correction path.**
   *Reason:* re-deciding provenance is a different authority question, and the
   first draft's `--supersede` contradicted this limitation while being unreachable
   anyway (Codex R1 Major 1). Enforced by `ux_provenance_corrections_trade`, not by
   prose. *Consequence, named:* a correction made on a WRONG citation is not
   repairable through a supported path — the same reduced-scope residue item 5
   records for its own gap. The `--dry-run` gate and the operator witness (§11) are
   what stand between the operator and that state.
5. **No `trade_events` row.** *Reason:* §5.3 — no truthful member of the CHECK enum
   exists, and a mislabelled audit record is worse than none.
6. **No web surface.** *Reason:* brief §7's envelope is CLI-only; a form is where
   free-typing re-enters.
7. **The written label may carry `; failed: <criterion>` for an `na` result.**
   *Reason:* §1.6 — reusing the framework's own builder beats minting a second
   label implementation; the `na`/`failed` wording is pre-existing.
8. **`<=` rather than strict `<`.** *Reason:* §3.1.4 — strict refuses 10 of 11 live
   candidate-bearing trades' own shape. **Flagged to RD as an interpretation.**
9. **The last-word guard may make a trade uncorrectable** when the framework's
   last word before the fill is a `skip`/`watch` row. *Reason:* §3.3 — the
   alternative admits citation-shopping. **Flagged to RD.** CADL verified unaffected.
10. **`hypothesis_registry.status` mutability is handled, not accepted.** The status
    is evaluated over the `[run_ts, finished_ts]` window against
    `hypothesis_status_history`, and the covering interval is cited structurally
    (§3.4.1). The residual NAME question is limitation 15, deliberately separate:
    the status has a history table and the name does not, so they are different
    problems with different answers.
11. **The cited `daily_recommendations` row can be mutated in place after the
    correction** (§3.4.2). *Reason:* `upsert_recommendation`'s
    `ON CONFLICT ... DO UPDATE SET` is a production write path outside this brief's
    envelope. *Mitigation, not a fix:* the row's content is frozen into the audit
    row and drift is REPORTED by the read command. *V2 dependency:* append-only /
    versioned recommendation persistence (§12.6).
12. **Offset-bearing and `Z`-suffixed `fills.fill_datetime` values are refused
    rather than converted to an exchange session** (§3.1.3). *Reason:* timezone
    conversion is a correctness surface this arc has no other need of, and refusing
    is the permissive-direction-safe choice. *Cost today: zero* — all 46 live fills
    are the naive `T16:00:00` shape.
13. **An evaluation run without exactly one COMPLETE `pipeline_runs` row cannot be
    cited** (§3.4.1). *Reason:* `run_ts` is a run-START stamp, so without a
    `finished_ts` the record's persistence instant is unbounded above and the
    hypothesis-status window cannot be closed. *Cost today:* 15 of 138 evaluation
    runs, of which the only `aplus` rows are SLDB candidates 681/782/1006 — a
    ticker that was never traded.
14. **A retrospective hypothesis-status interval is REFUSED** (§3.4.1) — an
    interval whose `recorded_at` post-dates the cited `run_ts`. *Reason:* the
    binding rule admits only contemporaneous records, and disclosure is not
    authorization. **Routed to RD as a RELAXATION request**: 5 aplus candidates
    carry migration-0017 backdated seeds and none is a correction target, so
    admitting them would change nothing live either.
15. **The written label's hypothesis-NAME component is spelled as of correction
    time, not as of the cited record** (§3.4.1a). *Reason:* the label is the live
    join key for `label_matches_hypothesis`, so a frozen historical spelling would
    produce a trade in NO cohort — the correction would fail at its purpose. The
    IDENTITY is carried immutably by `cited_hypothesis_id`; the spelling actually
    written is frozen in `cited_hypothesis_name_at_correction`. *Bound:* a registry
    rename breaks cohort matching for EVERY trade in the cohort, natively-labelled
    ones included — a pre-existing framework property this arc neither introduces
    nor can fix from inside its envelope. *V2 dependency:* a run-linked
    rule/name-version anchor (§12.11).

---

## 11. OPERATOR-WITNESSED LIVE GATE (step by step, one step at a time)

Never handed over as a batch — a batch collapses the gate into a self-report.

1. Operator confirms the DB backup exists (the 0036 gate writes it).
2. `swing db-migrate` → operator reads back `schema_version = 36`. (The command is `db-migrate`, hyphenated -- `swing/cli.py:186`; Codex R8 Minor 1.)
3. `swing journal correct-cohort-provenance 23 --cited-candidate 12341
   --cited-recommendation 172 --reason "..." --dry-run` → operator reads the
   before/after table, **both anchors, `F`, and the exact derived label string**,
   and confirms he accepts the §1.6 suffix before anything is written.
4. Apply without `--dry-run`; operator reads the correction id. **He is told in
   advance that V1 records provenance ONCE per trade and there is no supported
   re-correction path (limitation 4)** — so step 3's dry-run reading is the decision
   point, not this step.
5. `swing journal provenance-corrections 23` → operator confirms the citation FKs,
   the frozen anchors, the hypothesis interval, and that NO `CITATION DRIFT` line is
   present.
6. `swing hypothesis list` (or the dashboard H1 card) → operator confirms
   `2/20` with the in-flight decoration now reading 1 — **and is told in advance
   that `2/20` does NOT move**, so the unchanged number is not read as a failure
   (§1.7).
7. `swing journal correct-cohort-provenance 23 ...` re-run identical → operator
   confirms the ALREADY-APPLIED message returning the same correction id, and that
   no second audit row appeared.

---

## 12. FLAGGED, NOT FIXED

1. **`derive_trade_origin` reads "the latest complete run", not "the run the
   operator acted on"** (§1.9) — the root cause of trade 23's empty keys, and the
   reason this arc exists. It is an ENTRY-path change outside the envelope. **Left
   unfixed, the defect recurs** every time a ticker drops out of the screen between
   the recommendation and the fill. Recommend a follow-on arc; this is a #30-family
   defect (a run-level selection standing in for per-row provenance).
2. **Trade 21's `candidate_id` cites a post-dating record** (§1.8). Out of scope;
   RD's to decide whether H2's provenance needs re-basing.
3. **`trade_events` has no truthful `event_type` for an operator provenance
   correction** (§5.3). Widening the CHECK is a rebuild; CHARC's call.
4. **`CLAUDE.md` line 3 says schema v34; live and `EXPECTED_SCHEMA_VERSION` are 35**
   (§1.10). Cosmetic; orchestrator housekeeping.
5. **`watchlist_archive` has no trade identity** — noted only because item 5 records
   the same gap; this arc does not touch that table.
6. **`daily_recommendations` is mutable in place and has no version history**
   (§3.4.2, Codex R1 Critical 2). `upsert_recommendation` rewrites
   `evaluation_run_id`, prices, sizing and rationale on any same-session re-run, so
   NO durable proof exists of what a recommendation said at any past instant — a gap
   that reaches well beyond this arc (it undermines any future claim about what the
   framework recommended on a given day). **Recommended follow-on:** an append-only
   `daily_recommendation_versions` table populated by the emitter, with citations
   pointing at the version rather than the mutable row. Out of envelope here.
7. **Item 5's docstring claims a second production `fills.fill_datetime` shape that
   has zero instances in this database** (§3.1.3: 46/46 rows are naive
   `T16:00:00`). Cosmetic; noted because the plan's refusal was written against the
   schema rather than against that prose, and a future reader may otherwise
   reconcile the two the wrong way.
8. **`swing/evaluation/dates.py` embeds `"Pacific/Honolulu"` as TWO independent
   function defaults with no shared constant** (`dates.py:101,123`) — the D21 decay
   class sitting in the file that defines the project's session semantics. This arc
   REQUESTS the extraction as an envelope extension (§0); if CHARC declines, the
   duplication stands and is worth a separate housekeeping arc regardless.
9. **A provenance correction can be INVALIDATED after the fact by a legitimate
   entry-date correction** (§3.1.3, Codex R4 Major 1): item 5 moves the entry fill's
   `fill_datetime`, which can move `F` and even change which fill is authoritative,
   so a contemporaneity comparison recorded as satisfied can stop being so. V1
   DETECTS and REPORTS it (`CITATION ANCHOR DRIFT` / `CITATION INVALIDATED`) but
   cannot repair it, because V1 records provenance once. **Recommended follow-on:**
   decide the repair authority — either a supersession path for exactly this cause,
   or an item-5-side warning when the fill it is about to move is cited by a
   `provenance_corrections` row. Deliberately NOT a block on item 5: a money-bearing
   ledger correction must not be gated by a cohort-bookkeeping one.
10. **TWO CLOCK DOMAINS COEXIST IN THIS DATABASE — the most portable finding this
    review produced** (§3.4.1-clock, Codex R5 Critical 1). `evaluation_runs.run_ts`
    and `pipeline_runs.started_ts`/`finished_ts` are naive **LOCAL**
    (`runner.py:608`, `pipeline/lease.py:38`, both `datetime.now()`), while the
    Phase-9 audit tables — `hypothesis_status_history` among them — are naive
    **UTC** by explicit design (`data/datetime_helpers.py`, `utcnow()`). On this box
    that is a **ten-hour** offset with nothing in either column marking which domain
    it belongs to. **Any current or future comparison across those two families is
    wrong by ten hours and looks perfectly reasonable.** This arc normalizes at its
    own comparison site and refuses inside a ±24h margin; it does not and cannot fix
    the general case. **Recommended: a repo-wide audit of cross-domain timestamp
    comparisons, and a convention making the domain legible in the column name or
    the value.** Worth CHARC's attention independently of Demand C.
11. **No evaluation/pipeline row carries a MATCHER-RULE or HYPOTHESIS-NAME version
    anchor** (§3.4.1a, Codex R3 Major 2). Consequence: a cohort assignment
   reconstructed from a cited record necessarily applies TODAY's matcher rules and
   TODAY's registry spelling, so a rule amendment or a rename changes what the same
   citation would produce. This arc mitigates (frozen `derivation_rule_version`,
   frozen `cited_hypothesis_name_at_correction`, an immutable `cited_hypothesis_id`)
   but cannot close it — the fix is a run-linked immutable rule/name version written
   by the pipeline at evaluation time, which is a WRITE-path change outside the
   envelope. **Recommended follow-on**, and note it would also let a future arc
   reconstruct historical cohort assignments rather than only correct empty ones.
