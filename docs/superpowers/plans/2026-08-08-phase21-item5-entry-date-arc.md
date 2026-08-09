# Plan — wave item 5: the entry-date arc (D31 + A-4, with RD's two riders)

**Phase:** writing-plans. This document is the design; nothing here has been executed.
**Base:** `main` @ `37dc2caa` (schema **v34**). Worktree `.worktrees/item5-entry-date`.
**Ruled sources:** RD `20260801T145327Z` · `docs/phase21-boundary-paydown-commissioning-brief.md` §5 (CHARC §3 pass: **A-4 tripwire CROSSED — GO**) · the D31 + D25 register rows in `docs/tool-director-context.md` · `docs/wave-item5-entry-date-arc-dispatch-brief.md`.
**Governing gotchas:** #11 (CHECK + every Python mirror + validator in ONE commit) · #9 (`executescript` implicit COMMIT) · #24-#26 (two-path divergence) · #27 (silent skip without audit) · #30 (a run-level stamp is not per-row provenance).

> **Read §1 before anything else.** Three of the brief's premises do not survive contact with the code, and one of them changes what A-4 can be expected to do.

---

## §1 Premise verification — what I found that differs from the brief

Every row below was re-derived from the code or the live DB (`mode=ro`) on 2026-08-08. Where the brief is right I say so; where it is not, the code governs.

### 1.1 Confirmed

| brief claim | verified |
|---|---|
| Schema version **v34** | `schema_version` = 34; `swing/data/db.py:67 EXPECTED_SCHEMA_VERSION = 34`. Next free migration is **0035** (`swing/data/migrations/` tops out at `0034_h1_decision_criteria_amendment.sql`). |
| Trade 19 = FTRE, `entry_date=2026-07-23`, `state=closed`, `entry_price=18.8` | Exact. Also: `initial_shares=10`, `entry_intent='standard'`, `candidate_id=11852`, `pre_trade_locked_at='2026-07-23T16:00:00'`, `last_fill_at='2026-08-04T16:00:00'`. |
| Discrepancy 95 shape | Exact, and richer than the brief states: `ambiguity_kind='multi_match_within_window'`, `run_id=93`, `fill_id=39`, `resolution_reason="entry_price_mismatch on (ticker='FTRE', fill_id=39): execution is 6 NYSE-session(s) from fill (> 1) (20-A A2-date)"`, `actual_value_json` carries `execution_legs=[{leg_id:1, price:18.8, quantity:10.0, time:"2026-07-31T13:30:05+0000"}]`, `execution_sessions_from_fill: 6`, `schwab_order_price: 18.89`. |
| The CHECK is 11 values, widened at `0031` by TABLE REBUILD | Exact. `0031_untracked_broker_position.sql` is the verbatim precedent (§4.2). |
| The three Python mirrors agree at 11 | Exact — `reconciliation.py:46`, `models.py:1099`, `reconciliation.py:99`. |
| "No supported path corrects a recorded `entry_date`" (the D19-class gap) | **CONFIRMED on disk.** `swing/data/repos/trades.py` exposes exactly three write paths: `update_stop_with_event` (`current_stop`), `update_trade_review_fields`, `update_entry_intent`. There is no `entry_date` writer outside `insert_trade_with_event`. The `pre_trade_edit` `trade_events` type has a READ surface (`web/view_models/trades.py:1830`) and **no writer anywhere in `swing/`**. |
| 6 NYSE sessions between the fill date and the execution | Arithmetic checked: 07-24 Fri, 07-27, 07-28, 07-29, 07-30, 07-31 = 6. The live payload's `execution_sessions_from_fill: 6` is right. |

### 1.2 CORRECTION 1 — the D31 defect is **not** in the mapper

The brief (§1.1) and the commissioning brief (§5) both say "the **mapper** takes the EXECUTION timestamp" and "the defect is in what the mapper writes to `trades.entry_date`."

`swing/integrations/schwab/mappers.py` writes **nothing** to `trades`. It maps a Schwab order dict to a `SchwabOrderResponse` carrying BOTH facts, correctly:

- `mappers.py:283` → `enter_time` = `enteredTime` (the order-entered timestamp)
- `mappers.py:339` → `executions` = the `orderActivityCollection[].executionLegs[]` list, each leg carrying `time` (`swing/integrations/schwab/models.py:143` `SchwabExecutionLeg.time`)

The defect is one line **downstream**, in the auto-fill consumer:

```
swing/trades/entry_auto_fill.py:438
    entry_date = _extract_iso_date(getattr(chosen, "enter_time", ""))
```

That line picks `enter_time` when `chosen.executions[*].time` is sitting right beside it — and the same function already reads the execution grain for the PRICE two lines earlier (`entry_price = _compute_execution_price(chosen)`, line 418). So the module is already execution-grain for price and order-grain for date. **The register's sentence "the system already holds the correct timestamp; it is simply not the one that reaches the field" is exactly right; the file it names is not.** Fixing `mappers.py` would be fixing a file that has no bug.

This matters beyond pedantry: a plan that edited `mappers.py` would either change `enter_time`'s meaning for its OTHER four consumers (`exit_auto_fill.py:547/595/602/704`, `schwab_reconciliation.py:813`, `reconciliation_backfill.py:506`) or add a field nobody reads.

### 1.3 CORRECTION 2 — A-4 will **not** retype discrepancy 95

The brief §2 says: *"Discrepancy 95 is typed `entry_price_mismatch` and the prices match exactly. It is **mistyped** — the real divergence is the date, and the type vocabulary has no word for it. **That is what A-4 exists to fix.**"*

The first two sentences are true. The third is not, and I traced A-4 to its origin to be sure.

A-4 is `docs/archive/phase20/2026-07-11-20a-corrector-fix-plan.md` **§6.4 option A4-iii**, the schema route for **Task A-5, the fills↔trades consistency invariant**. Its semantics are fixed by that task: *"compute the entry-fill VWAP from its entry-action fills; if `abs(vwap - trades.entry_price) > $0.005` emit a material discrepancy."* The shipped no-schema approximation (A4-i) is live at `swing/trades/schwab_reconciliation.py:690 _emit_fills_trades_consistency`, which emits `discrepancy_type="entry_price_mismatch"` with `field_name="internal_consistency"` and an `actual_value_json` discriminator `{"internal_consistency": "fills_vs_trades", ...}`. A-4 promotes **that** emit to a dedicated type. The name `fills_trades_price_divergence` says what it is: a **fills-vs-trades PRICE** divergence, internal to the journal.

Discrepancy 95 is a different animal in every respect:

| | disc 95 | an A-5 / A-4 row |
|---|---|---|
| what disagrees | broker execution DATE vs journal fill DATE | journal `fills` VWAP vs journal `trades.entry_price` |
| `field_name` | `price` | `internal_consistency` |
| discriminator | absent (verified on the live row) | `actual_value_json.$.internal_consistency == 'fills_vs_trades'` |
| both sides internal? | no — one side is Schwab | yes |
| its prices | 18.8 vs 18.8, agreeing | disagree by construction |

So after A-4 lands, **discrepancy 95 is still an `entry_price_mismatch` row.** It cannot be retyped into `fills_trades_price_divergence` without writing a second false statement.

The register's own wording is careful and correct where the brief's is not: disc 95 is *"the live evidence for the banked A-4 dedicated `discrepancy_type` rider ... a date rejection routed through the only channels that existed."* It is evidence for the **class** — that the taxonomy is too coarse and forces true findings through wrong words — not an instance of the type A-4 adds. The brief compressed "evidence for the class" into "instance of the type," and the compression is load-bearing because it implies disc 95's honest close runs *through* A-4. It does not. §3 closes disc 95 without A-4, and §5 poses the second-type question rather than answering it.

### 1.4 CORRECTION 3 — trade 19 is **not** in the H1 cohort

The D31 register row says "trade 19, FTRE, **H1 cohort**" and "the August monthly read consumes this cohort." The dispatch brief inherits it ("H1-cohort data correction — his lane twice over").

Live: `trades.hypothesis_label = 'Broad-watch baseline (watch); failed: tightness'`. `hypothesis_registry` id 5 is `Broad-watch baseline` (target 30); **H1 is id 1, `A+ baseline`** (target 20). `_label_matches_hypothesis` matches on the registered name, so trade 19 lands in **H5's** sample, not H1's. H1's 2/20 is trades 17 (VSTS) and 18 (AMN) — both `A+ baseline (aplus)`, both `entry_intent='standard'`.

The register itself flags the cause in its own last clause: *"latch fills labelled from the FLICKERED bucket (`hypothesis_label` = broad-watch while `rationale` = aplus-setup) structurally starves H1 — operator's frozen field, HIS call."* That known labelling defect is precisely why the trade is not in H1. The register then, three columns earlier, describes it as H1-cohort. Both cannot be true.

**Consequence for the gate, not for the work:** the correction does not move H1's sample count, its concentration guard, or its STANDARD-intent clause (`swing/metrics/cohort_intent.py:H1_COHORT_CLAUSE` is a cohort-membership predicate on `entry_intent`, which this arc does not touch). It DOES move several cross-cohort measurement numbers RD reads — §5 enumerates them with live values. RD's merge-blocking gate stands on that enumeration; it does not stand on an H1 sample change, and the plan should not tell him it does.

### 1.5 New finding — the same defect is live on the EXIT side, and the operator already hand-patched it

`swing/trades/exit_auto_fill.py:695` is the same line:

```
    date = _extract_iso_date(getattr(o, "enter_time", ""))
```

The live ledger shows it firing. Fill 40 (trade 19's stop-out):

- `schwab_source_value_json` → `{"exit_date": "2026-08-03", ..., "schwab_order_id": "1007444179553"}`
- `operator_corrected_value_json` → `{"closed_shares": 10, "exit_price": 18.4, "exit_date": "2026-08-04"}`

A resting stop entered Monday 08-03 and executed Tuesday 08-04; the auto-fill proposed the entered date and the operator corrected it by hand. Same root, opposite leg. **Not fixed in this arc** (D31 as ruled is the entry side, and the exit path has a second consumer — `_compute_signature_hash` at `exit_auto_fill.py:713` folds `date` into the candidate dedupe hash, so changing the source changes the hash and needs its own acceptance). **Flagged, not fixed** — §9.

### 1.6 New finding — the trade row is already internally inconsistent, which corroborates the correction

`trades.candidate_id = 11852`. Live join: candidate 11852 belongs to evaluation run 130, `run_ts 2026-07-30T17:30:02`. Candidate 11551 (run 125) is the 07-23 row. `record_entry` resolves `candidate_id` from the latest complete evaluation run at record time — so the trade's own backlink already points at the **07-30** evaluation, i.e. the last one before the **07-31** execution, while `entry_date` says 07-23. The row disagrees with itself, and the half that is right is the half nobody complained about.

### 1.7 New finding — `entry_date` is not one field; `record_entry` fans it into four

`swing/trades/entry.py:297-300, 407, 472, 500`:

```
entry_iso = _normalize_trade_event_date_to_iso(...)   # entry_date + "T16:00:00"
req_view["pre_trade_locked_at"] = entry_iso
    ...
    pre_trade_locked_at=entry_iso,                    # trades.pre_trade_locked_at
    ...
    fill_datetime=entry_iso,                          # the entry fill's fill_datetime
    ...
    removed_date=req.entry_date,                      # watchlist_archive.removed_date
```

Live confirmation on trade 19: `pre_trade_locked_at = '2026-07-23T16:00:00'` and fill 39 `fill_datetime = '2026-07-23T16:00:00'` — both derived, both wrong by the same eight days.

**This is the single most consequential thing I found for the design.** A correction surface that moves `trades.entry_date` alone would leave the ledger *more* incoherent than it is now, and — critically — **would not close discrepancy 95**, because the A2-date guard that raised it measures against `fills.fill_datetime`, never against `trades.entry_date`:

```
swing/trades/schwab_reconciliation.py:578
        fill_date = _date.fromisoformat(str(fill_datetime)[:10])
```

A plan that corrected only `entry_date` would ship, be witnessed, and the very next reconciliation would re-raise the identical finding.

---

## §2 Decision 1 — the shape of the audited correction surface

### 2.1 What it is

**A CLI-only command, no web surface, no schema.**

```
swing journal correct-entry-date <trade_id> \
      --to YYYY-MM-DD \
      --discrepancy <discrepancy_id> \
      --reason "<free text, required, non-empty>" \
      [--allow-active] [--dry-run]
```

**Route verified against `cli.py`, not assumed** *(Codex R3 Major 4 — my first draft wrote `journal trade correct-entry-date`, and there is **no `trade` subgroup**: `journal_group` at `cli.py:1610` carries flat commands (`review`, `cash`, `oof-buy`, `cash-void`, `reconcile-tos`, `import-tos`, `reconcile-backfill`) and exactly one subgroup, `discrepancy` at `:2582`. The command as written could not have been registered.)* A flat `@journal_group.command("correct-entry-date")` is the right shape here — it sits beside `cash-void`, the D19 sibling this surface is modelled on, and inventing a `trade` subgroup for one command would be worse. `--allow-active` (§2.4 step 3) is part of the contract and of the tests.

### 2.2 Following the D19 / cash-void precedent — and where I depart

| D19 (`journal cash-void`, `be567712`) | here | same? |
|---|---|---|
| **CLI-only**; no web surface was built | CLI-only | **same** — and for the same reason: a rare, high-consequence, audited maintenance action. An HTMX form buys nothing and costs the two browser-only failure surfaces (`hx-headers` / 204+`HX-Redirect`) plus an operator-witness leg. |
| **NO SCHEMA** (operator chose Option A over the origin-column bundle) | NO SCHEMA for the surface | **same**. The migration in this arc belongs to A-4 alone (§4); the surface adds none. If any part of the design below turns out to need a column, that is a **SCHEMA-STOP** — route back, do not build it. |
| **Append-only**: the fix is a *reversing entry* in an append-only table, never an UPDATE | Append-only **audit**, mutating **journal** UPDATE | **DIFFERENT — stated plainly.** `cash_movements` is an append-only ledger, so a reversal is expressible. `trades.entry_date` is a mutable column with exactly one truth; there is no reversing entry that makes an eight-day error net to zero. The append-only property therefore attaches to the **audit trail** (`reconciliation_corrections`, which CLAUDE.md already pins as APPEND-ONLY) and not to the corrected value. This is the same asymmetry every existing tier-1/2/3 correction lives under: `_update_journal_field` UPDATEs the column, `insert_correction` appends the record of it. |
| **Reason-required**, fail-loud | Reason-required, fail-loud | **same** — empty/whitespace `--reason` is a `ClickException` before any DB work. |
| Idempotency via a `void:<id>` ref sentinel | Idempotency via a no-op guard: if `trades.entry_date` already equals `--to`, refuse with a clear message and write nothing | **same spirit** (the four-emitter `no_op_value_does_not_supersede` discipline in CLAUDE.md). |

### 2.3 Where the audit row goes — and the constraint that decided it

`reconciliation_corrections` is the project's canonical append-only correction ledger, and its schema already permits this row without modification:

- `affected_table TEXT NOT NULL CHECK (affected_table IN ('fills','trades','cash_movements','account_equity_snapshots'))` — `'trades'` is **already legal**.
- `field_name TEXT NOT NULL` — free text; the live table already carries a non-column value (`'fill_match'`, 19 rows), so `'entry_date'` needs no widening.
- `correction_action CHECK (... 'operator_overridden')` — legal.
- `applied_by CHECK (... 'operator')` — legal.

But two columns are `NOT NULL` **with FKs**: `discrepancy_id → reconciliation_discrepancies` and `reconciliation_run_id → reconciliation_runs`. So a correction must hang off a **finding**.

Two ways to satisfy that:

- **(a) Require an existing discrepancy** (`--discrepancy <id>`, mandatory). The correction anchors on the finding that motivated it and inherits its `reconciliation_run_id`.
- **(b) Mint an ad-hoc `source='system_audit'` run + a synthetic discrepancy**, per the live precedent at `swing/web/routes/trades.py:127 _emit_sector_tamper_audit` (`insert_run(source="system_audit") → insert_discrepancy → update_run_completed`). This works mechanically and would let the command run with no finding at all.

**Chosen: (a). Rejected: (b), for V1.**

The reason is not effort. Option (b) must choose a `discrepancy_type` for the row it mints, and **none of the twelve** (eleven today, plus A-4's) truthfully describes "the operator noticed a recorded entry date is wrong and there is no finding." `entry_price_mismatch` would be false (§1.3's exact error, committed deliberately); `fills_trades_price_divergence` would be false (both sides are not internal); `snapshot_mismatch`/`sector_tamper` are unrelated. Option (b) buys generality by minting a mistyped row — the precise failure this arc exists to stop. **The gap that (a) leaves is named, not hidden:** an entry-date error with no reconciliation finding remains uncorrectable through a supported path. That is a real, reduced-scope residue of D19, and it is the natural home for the second-type question in §5.2. It is a V2 candidate, not silent.

### 2.4 What the command writes, in one transaction

Single-transaction service contract per CLAUDE.md: the service owns `BEGIN IMMEDIATE`/COMMIT/ROLLBACK and **REJECTS** a caller-held transaction (never auto-detects). New module `swing/trades/entry_date_correction.py` (outer `correct_entry_date` + inner `_correct_entry_date_inner`, mirroring `reconciliation_auto_correct.py`'s outer/inner split so a future pivot can compose it under a SAVEPOINT).

Ordered steps:

1. **Validate `--to`**: `date.fromisoformat` (raise a typed error, not a deep `TypeError` — CLAUDE.md's TEXT→`date` boundary gotcha); reject any value containing `T` (mirroring `entry.py:290`, whose comment records that downstream callers do `date.fromisoformat(trade.entry_date)` directly and a full ISO datetime breaks them); and **refuse a non-trading-session date** via `is_trading_session` (the helper `latches/reader.py:143` already uses) — a weekend/holiday `entry_date` is persistable today, and `latches/reader.py:143-153` **LOGS a warning and DELIBERATELY RETAINS the trade** — its own comment says *"LOGGED, NOT DROPPED (a deliberate asymmetry with bars). A trade is ground truth about a REAL position."* *(Codex R10 minor — an earlier draft of this line claimed the reader would silently drop it; the reader is better designed than my justification for the gate.)* **The gate stays as a V1 POLICY, on a corrected rationale:** a non-session entry date is never a true execution date, so writing one would inject an anomaly that every downstream session-walker must then tolerate — and the latch reader tolerating it gracefully is a reason not to manufacture it, not a licence to.
   **What this gate rejects, stated honestly** *(Codex R6 Major 3 — my earlier claim that "an execution timestamp always lands on a session, so this can only ever reject operator typos" contradicted §8.2 two pages later)*. Under the UTC-prefix convention (§8.2), a **Friday after-hours execution derives a SATURDAY date**, which this gate rejects — and that is not a typo, it is a real fill the surface then cannot correct. The two rules were written in different rounds and never read against each other. **V1 posture: the gate stays and the case is documented as UNSUPPORTED rather than silently mis-dated.** A refusal that says *"derived date 2026-08-01 is not a trading session; this is the after-hours UTC-date residue of §8.2, not a typo — route to CHARC"* is strictly better than writing a Saturday entry date that de-latches a live position. The clean fix is the one §8.2 already names — convert BOTH the auto-fill and the reconciliation guard to exchange-session dates in one change — and it is out of scope here. Discriminating test: an after-hours execution timestamp is refused with the residue named, not accepted and not silently shifted.
2. **Validate `--reason`** non-empty after `.strip()`.
3. **SELECT the trade**; refuse if absent. **Then gate on `state`.** *(Codex R2 Major 1 — the finding is accepted; its prescription is not, and the difference matters.)* Codex proposed restricting the command to `state IN ('closed','reviewed')`. **That would defeat the surface's forward purpose:** the D31 register's own words are *"EVERY future latch fill hits it,"* and a latch fill lands on a **live** position — so a closed-only guard would leave the case this arc exists to prevent permanently uncorrectable, which is the D19 gap re-created one field over. **The real defect was that the plan stated no state posture at all.** The posture:
   - `closed` / `reviewed` → permitted outright (the ruled trade-19 case).
   - `entered` / `managing` / `partial_exited` → permitted **only with an explicit `--allow-active` flag**, whose absence is a refusal naming the active-trade impact inventory (nine items; it grew in four separate rounds, so it is stated as the best inventory the review produced rather than claimed complete) *(Codex R3 Major 5 — my first list was short by two, and an acknowledgement flag that under-states what is being acknowledged is worse than no flag)*:
     1. `_recompute_aggregates` WILL move `last_fill_at` on a not-yet-exited position (§2.4 step 8);
     2. it can also move **`current_avg_cost`** on a multi-entry-fill trade (the `ORDER BY fill_datetime ASC` re-sort) — and `current_avg_cost` feeds **open-position capital heat and utilization** at `metrics/capital.py:367` and `:385`, i.e. **position sizing inputs on a live position**;
     3. the live advisory day-count and the day-3-5 window shift under the operator mid-position (`trades/advisory.py:132`);
     4. `concurrent_open_positions` (`metrics/capital.py:101`) re-windows;
     5. the MFE/MAE running anchor at `daily_management.py:546` moves for every FUTURE snapshot (past snapshots stay — §5.2);
     6. **`entry_date` is the SELL-side lookback boundary for exit auto-fill** (`exit_auto_fill.py:302/315/362` — `resolve_exit_auto_fill(..., entry_date=...)` bounds which Schwab SELL fills are candidates). Moving it FORWARD narrows that window, so a partial exit executed between the old and new dates would drop out of the exit form's candidate set. On this arc's own data that window is 07-23 → 07-31 — eight sessions in which a scale-out could have occurred. **This is the sharpest active-trade consequence and it was missing entirely.**
     7. **The LATCH surface reads `entry_date` for eligibility, ordering AND fill-terminal ranking** *(Codex R4 Major 3 — and it is the consequence most on-point, because latches are the reason this arc's forward case exists at all)*: `latches/reader.py:131-133` selects non-voided trades `ORDER BY entry_date, id`, `:143` rejects a non-trading-session `entry_date` outright, and `latches/service.py:248-259` matches a draft with `draft.anchor <= e.entry_date <= as_of` and breaks ties with `min(..., key=(entry_date, trade_id))`. So moving an ACTIVE trade's entry date can change **whether it matches a latch at all** and **which terminal wins** — the surface whose fills produce this defect is itself keyed on the field being corrected. (Corollary the guard must enforce: `--to` should be a **trading session**, or `reader.py:143` will warn and drop the trade from the latch reader. 2026-07-31 is a Friday and a session, so trade 19 is unaffected — but a correction to a weekend date would quietly de-latch a live position.)
     8. **The nightly briefing's open-position `days_open`** *(Codex R5 Major 3)*: `rendering/briefing.py:157` sits inside `_open_positions`, so it computes `(data_asof_date − entry_date).days` **for OPEN trades only** — which makes it an active-trade consequence, not the generic display item §5.1 listed it as. Correcting a live position's date changes the number the operator reads in tomorrow morning's briefing.
     9. **Live open-R, persisted heat inputs, and historical close-matching** *(Codex R6 Major 1)*: `web/view_models/dashboard.py:1579-1583` derives live `open_R` from `current_avg_cost` (which item 2 can move); `trades/daily_management.py:572-590` and `:640-645` PERSIST future open-R / heat inputs computed off the same values; and `journal/tos_import.py:1047` bounds historical close-matching with `reference_entry_date = t.entry_date` for an **active** trade, so moving it changes which TOS CLOSE fills route to history versus live allocation. The first two are the sizing-input consequence of item 2 following through to the dashboard and to persisted rows; the third is a matching-behaviour change on an open position.

     The flag is the same posture as `discrepancy resolve --force`: not a lock, a conscious acknowledgement, recorded in the correction reason.
   - Discriminating tests for **both** branches — an active trade rejected without the flag, accepted with it.
4. **No-op guard**: if `trades.entry_date == --to`, refuse; write nothing.
5. **SELECT the discrepancy, CHECK IT ACTUALLY AUTHORIZES THIS, and BIND THE EXACT FILL.** *(Codex R1 Major 4 + R2 Major 2.)* Refuse unless **all** hold:
   - the discrepancy exists and `discrepancy.trade_id == trade_id`;
   - **`discrepancy.resolution IN ('unresolved','pending_ambiguity_resolution')`** — a terminal, already-dispositioned historical finding must not authorize a fresh live mutation. Without this, any long-closed entry discrepancy on the trade is a standing warrant to rewrite its date;
   - **`discrepancy.fill_id IS NOT NULL`**, that fill's `trade_id == trade_id`, and that fill's `action == 'entry'`;
   - the discrepancy is **entry-shaped**: `discrepancy_type == 'entry_price_mismatch'` AND it is **not** an A-5 internal-consistency row (reuse the existing `_is_internal_consistency_diagnostic` predicate rather than writing a second one — a fills-vs-trades price diagnostic says nothing about a date);
   - **and it carries DATE evidence, not merely a price disagreement** *(Codex R3 Major 9)*. Without this clause an ordinary `entry_price_mismatch` — a genuine price divergence with a same-session execution — would satisfy every other clause and stand as authorization to rewrite the date, which is a real widening of what the operator is approving. **Required:** `actual_value_json` parses to a dict containing a non-empty `execution_legs` list whose leg `time` values are parseable, AND the date produced by **the same max-parsed-timestamp rule T1 uses (§8.1 case 3)** differs from the fill's current date.
   **`execution_sessions_from_fill != 0` is NOT an acceptable substitute, and my first draft wrongly offered it as an equivalent** *(Codex R4 Major 1)*. `_fill_execution_session_distance` returns **`max(distances)` across ALL legs** (`schwab_reconciliation.py:596`), so a nonzero value only proves that *some* leg differs from the fill date — a partial fill whose first leg executed on an earlier session and whose LAST leg executed on the fill date would report a nonzero distance while the date this surface would write is unchanged. Authorizing a date rewrite from an aggregate that does not describe the value being written is gotcha **#30** in its general form: **a MAX across rows is not provenance for the row you are about to use.** Compute the same date the correction will write, and compare that.

   The command's own justification must be visible in the row it cites, computed the way the correction computes it.

   **AND `--to` MUST EQUAL THAT EVIDENCE DATE — the value is SERVER-DERIVED, the operator's input only CONFIRMS it.** *(Codex R5 Critical 1, and it is the sharpest finding of the whole review.)* Every clause above validated that date evidence **exists** and that it **differs** from the fill's date; **none of them bound `--to` to it.** So an operator could pass `--to 2026-08-03` — a later trading session, satisfying the format check, the session check, the no-op check and every authorization clause — and the command would write an unsupported date **while citing discrepancy 95 as its justification**. That is worse than the defect this arc closes: the current wrong date at least came from a real Schwab field, whereas this one would come from a typo wearing an audit trail.
   **The fix is the project's own server-stamp discipline** (CLAUDE.md: *"V1 single-operator forms with hidden audit fields: SERVER-STAMP, don't trust hidden inputs"* — the general form is *don't accept an operator value when canonical state can compute it*): the service **derives** `target_date` from the discrepancy's execution evidence, then requires `--to == target_date` and refuses with both values printed otherwise. `--to` stays **required** — it is the operator's explicit confirmation of what he is about to change, and dropping it would let a single command rewrite a date he never named — but it is a **checked confirmation, never the source**. The correction, the audit row, and the derived timestamps all take the SERVER's value.
   Discriminating test: same discrepancy, `--to` one session later than the evidence → refused, nothing written.

   **The predicate's forward limitation, stated rather than discovered later:** it keys on `discrepancy_type == 'entry_price_mismatch'`, which is the only type that exists for this today (§1.3). If §5.3(5)'s `entry_date_mismatch` type is ever ruled in, **this predicate must widen to admit it in the same commit** — otherwise the honest type would be refused by the surface built to use it. Recorded here so the coupling is not rediscovered.

   The UPDATE targets **`discrepancy.fill_id` and only it** — never a re-derived "the trade's entry fill", which is ambiguous the moment a trade has more than one entry fill and whose `list_fills_for_trade` order is not a binding contract. For trade 19 this pins **fill 39**, which is what disc 95 carries, and disc 95 satisfies every clause above (verified live: `resolution='pending_ambiguity_resolution'`, `fill_id=39`, `discrepancy_type='entry_price_mismatch'`, no `internal_consistency` key).
6. **Read pre-values** for every field about to move (§2.5), **plus all THREE aggregates step 8 recomputes — `trades.current_size`, `trades.current_avg_cost`, `trades.last_fill_at`** *(Codex R2 minor: `repos/fills.py:119-145` updates three columns, not two; `current_size` is a signed sum over fills and is datetime-independent, but it is rewritten by the same statement and so belongs in the pre/post pair for a faithful audit)*.
7. **UPDATE the coupled values** (§2.5) through a **closed field enum**, never operator-supplied identifiers — see §2.6.
8. **`_recompute_aggregates(conn, trade_id)` — BEFORE the audit INSERT, not after.** *(Codex R1 Major 3.)* `swing/data/repos/fills.py:119` derives `trades.last_fill_at = MAX(fill_datetime)` **and** `current_avg_cost` from the entry fill `ORDER BY fill_datetime ASC, fill_id ASC`. Moving an entry fill's `fill_datetime` can therefore move BOTH: `last_fill_at` on any trade whose corrected entry fill is its latest fill (every open, un-exited position — precisely the forward case this surface exists for), and `current_avg_cost` on a multi-entry-fill trade where the move re-orders which entry fill sorts first. On trade 19 neither changes (the 08-04 exit fill stays `MAX`; there is one entry fill) — **but the audit row must be able to tell the truth in the cases where they do**, and an `applied_value_json` written before the recompute structurally cannot. Recompute first, then read the post-values, then insert.
9. **`insert_correction`** one `reconciliation_corrections` row: `affected_table='trades'`, `affected_row_id=trade_id`, `field_name='entry_date'`, **`correction_action='operator_resolved_ambiguity'`**, `applied_by='operator'`, `pre_correction_value_json` = the full step-6 pre-value dict, `applied_value_json` = the full **post-recompute** value dict (including all three aggregates), `operator_truth_value_json` = the same, `correction_reason=<--reason>` (prefixed with the `--allow-active` acknowledgement when that flag was used), `discrepancy_id`/`reconciliation_run_id` from step 5, `risk_policy_id_at_correction` via the existing `_maybe_get_active_risk_policy_id` helper.
9a. **Set `fills.reconciliation_status` on the corrected fill** *(Codex R10 Major 3)*. Every existing correction path performs this transition — `reconciliation_auto_correct.py:986`, `:2072`, `:2201` all `UPDATE fills SET reconciliation_status = ?` for the affected fill — and my step list mutated fill 39 without it, so the fill would have kept `reconciliation_status='unreconciled'` (its live value) after being reconciled. The later `resolve_discrepancy` call touches only the discrepancy row, so nothing else would have healed it. Use the same terminal value those paths use; assert it in the correction-service tests and read it back at the witness.

**Why `correction_action='operator_resolved_ambiguity'` and NOT `operator_overridden`** *(Codex R10 Major 2)*. The CHECK admits three values and only one of them is true here:
   - `auto_applied` — false; a human did this.
   - **`operator_overridden` — false, and my earlier draft used it.** `ReconciliationCorrection`'s own docstring (`models.py:1390-1397`) defines it as *"tier-3 (operator override of a prior tier-1 correction)"*, and `_apply_tier3_override_inner` requires an existing `correction_id` to supersede. **Discrepancy 95 has zero correction rows** — §2.7 says so itself, as the reason tier-3 is unavailable — so labelling this row `operator_overridden` asserts a supersession of nothing, in a ledger whose whole purpose here is to stop the system writing false statements. The §3.4 reason text even opens *"Journal corrected, not overridden."* The plan contradicted its own sentence one section away.
   - **`operator_resolved_ambiguity` — true.** Discrepancy 95 is `pending_ambiguity_resolution` with `ambiguity_kind='multi_match_within_window'`; the operator is resolving that ambiguity by supplying the execution truth, paired with a correction row — which is exactly the pairing `reconciliation.py:140-145` documents for this action.

   **And it carries an obligation my round-10 fix did not discharge** *(Codex R11 Major 2 — a MAJOR found inside the previous round's fix, which this wave has now produced six times)*. `models.py:1428-1430` names *`correction_action='operator_resolved_ambiguity'` paired with `correction_choice IS NULL`* as an explicit **lifecycle contradiction** — one the schema deliberately does not enforce, to be caught at the service layer — and every existing tier-2 builder populates `correction_choice`. Swapping the action without supplying a choice would have traded a false label for a malformed row. **So the correction writes `correction_choice='correct_entry_date'`**, a controlled code owned by this surface (not a member of any `get_choice_menu` list, because this correction does not come from the tier-2 operator menu), and the service asserts it non-NULL before INSERT. A discriminating test pins that the emitted row carries both the action and the choice — the pair, not either alone, is what makes the row lifecycle-valid.

   **This does NOT change §3's resolution value**, and the distinction is worth stating because a reader will ask: `reconciliation_corrections.correction_action` labels *what kind of act produced this audit row*; `reconciliation_discrepancies.resolution` records *how the finding was disposed of*. They are different columns answering different questions, with no cross-table constraint between them. The act was an operator resolving an ambiguity; the disposition is that the journal was corrected. Both statements are true, and each belongs in its own column. **Flagged for CHARC** as an audit-semantics judgment made by this plan rather than inherited from a precedent — no existing row carries this action with a `journal_corrected` sibling, because no existing surface writes a correction outside the tier machinery.

10. **Emit a `trade_events` row via the EXISTING forensic payload shape.** *(Codex R1 Minor.)* Reuse `_emit_trade_events_correction`'s `{correction_id, affected_table, affected_row_id, field_name, pre, applied}` tuple verbatim rather than inventing a payload — `pre`/`applied` carry the full multi-field dicts from steps 6/9, so a forensic replay reads the same shape here as on every other correction. `event_type='reconciliation_auto_correct'` is already in the live CHECK enum and is the type every other correction emits. Its name is imperfect for an operator action, but **widening the `trade_events` CHECK is a schema change this arc has no authorization for** — using the existing member is the SCHEMA-STOP-respecting choice. Naming debt recorded in §9.
11. COMMIT.

**`--dry-run`, specified rather than gestured at** *(Codex R3 minor)*. It runs steps 1-6 (all validation, all guards, all pre-value reads) and returns **without opening a write transaction**. Its table prints:
- the four §2.5 targets with **real before and real after** values — these are known without executing anything (`--to` is given; the two derived timestamps are `--to` plus the preserved `%H:%M:%S` component);
- the three aggregates (`current_size`, `current_avg_cost`, `last_fill_at`) with their **real before** values and their after column rendered **`(recomputed on apply)`** — NOT a simulated number. Predicting them means re-implementing `_recompute_aggregates` in the dry-run path, and a second implementation of a derivation is the two-path-divergence class (#24-#26) invited into a preview. **A dry-run may show what it knows and must say what it does not.**
- the resolved `discrepancy_id`, the bound `fill_id`, and — when `--allow-active` is in play — the full nine-item consequence list from step 3.

**Transaction discipline, checked rather than assumed:** every function called inside the `BEGIN IMMEDIATE` is repo-level, not service-level. `_recompute_aggregates` (`repos/fills.py:119`) is a bare `conn.execute` with no `with conn:`; `insert_correction` (`repos/reconciliation_corrections.py`) likewise. Neither opens or commits a transaction, so the CLAUDE.md "Service-layer `with conn:` opens its own transaction" gotcha does not fire. The new module's own `_correct_entry_date_inner` follows the same rule — it never commits.

### 2.5 The four coupled values — and the one that is a judgment call

Per §1.7, `record_entry` derives all of these from `entry_date`. The correction restores that coupling:

| target | trade-19 before | after | why |
|---|---|---|---|
| `trades.entry_date` | `2026-07-23` | `2026-07-31` | the ruled correction. |
| `fills.fill_datetime` (the trade's **entry-action** fill; fill 39) | `2026-07-23T16:00:00` | `2026-07-31T16:00:00` | **required, or discrepancy 95's cause survives.** `_fill_execution_session_distance` (`schwab_reconciliation.py:578`) measures the A2-date guard against this column and nothing else. |
| `trades.pre_trade_locked_at` | `2026-07-23T16:00:00` | `2026-07-31T16:00:00` | derived from `entry_date` at `entry.py:407`. Feeds `_capital_cycle_time_days` (`metrics/capital.py:402`), `_holding_period_trading_days` (`metrics/process.py:203`), the `concurrent_open_positions` window (`capital.py:101`) **and the funnel's "taken" counts (`metrics/funnel.py:190/200`, §5.1)**. Leaving it stale would make the trade's holding period disagree with its own entry date. |
| `trades.last_fill_at`, `trades.current_avg_cost` | unchanged on trade 19 | unchanged on trade 19 | **not set directly** — recomputed by `_recompute_aggregates` at §2.4 step 8 because `fills.fill_datetime` moved. Named here so the audit row can carry them; see step 8 for why the recompute precedes the INSERT. |
| `watchlist_archive.removed_date` (the `reason='entered'` row) | `2026-07-23` | `2026-07-31` | **CORRECTED — my earlier exclusion of this value was justified by a false statement, and a Codex round had already blessed the exclusion before a later one caught it** *(Codex R6 Major 2)*. I wrote that it "records when the watchlist row was archived, which genuinely happened at record time." `entry.py:500` writes `removed_date=req.entry_date` — **it is the same defective value as the other three**, which is exactly what §1.7 says two sections earlier. The plan contradicted itself, and the half that was wrong was the half doing the excluding. Live corroboration: row id 143 carries `removed_date='2026-07-23'` beside `last_data_asof_date='2026-07-30'` — the row disagrees with itself the same way the trade row does (§1.6). |

**Binding the `watchlist_archive` row — zero-match and multi-match are DEFINED, not assumed.** The row is located by `(ticker, reason='entered', removed_date == the trade's PRE-correction entry_date)`. **Exactly one match is required**; zero matches or more than one is a REFUSAL with the count printed, not a best-effort update. This is §7's own hop-1 lesson applied where it actually bites: `watchlist_archive` carries no unique constraint on that triple, so "the archive row for this trade" is an assumption until the query proves it. A trade whose ticker was entered twice is exactly the shape that produces two. (Live: FTRE returns one, id 143.)

**Three discriminating tests, because a stated safety rule with no test is a comment** *(Codex R7 Major 2)*: **(a)** exactly one match → the row is updated and its pre/post values appear in the audit envelope; **(b)** ZERO matches (a manually-recorded trade that never sat on the watchlist — a real and common shape) → refusal, **and nothing else in the transaction is written**, so a trade with no archive row cannot be half-corrected; **(c)** TWO matches (same ticker entered twice on the same date) → refusal naming the count. Without (b) and (c) an implementation that simply runs `UPDATE ... WHERE ticker=? AND reason='entered'` passes the happy path and silently rewrites the wrong row — or every row — in exactly the cases the rule was written for.

**The `pre_trade_locked_at` decision is a judgment, and I am flagging it as one.** Semantically, for a *resting* order the operator's pre-trade lock and the fill genuinely happen on different days — 07-23 is when he locked the plan, 07-31 is when it filled. `record_entry`'s single-`entry_iso` derivation encodes a same-day assumption that the latch posture broke. So there is a defensible design in which `pre_trade_locked_at` stays at 07-23 and only the fill moves — and it would be *more* truthful about the world.

I do not choose it, for one reason: `pre_trade_locked_at` is not stored anywhere as an independently-sourced fact. It has exactly one writer, and that writer computes it from `entry_date`. Choosing to keep 07-23 would be asserting a provenance the write path never established — CLAUDE.md **#30** in its non-timestamp form: a value derived from another field is not independent evidence about the world just because it happens to read true. If the operator's lock time is to become a first-class fact, that is a schema question and a separate arc. Until then the coherent choice is to keep the derivation intact. **Posed to RD in §5.3(d)** because it moves two of his numbers.

Use the `%H:%M:%S` component of the EXISTING value (`16:00:00`), not the Schwab execution clock time. Reason: `_normalize_trade_event_date_to_iso` produces `T16:00:00` as a *convention*, not an observation, and every existing row carries it. Substituting the real 13:30:05Z execution time would make trade 19 the only row in the table with a real clock, which downstream string-prefix comparisons (`str(fill_datetime)[:10]`, `pre_trade_locked_at[:10]`) would tolerate but which a future reader would misread as a measurement. Date-only correction, convention preserved.

### 2.6 The closed field enum — and a pre-existing hazard I am NOT inheriting

`_update_journal_field` (`reconciliation_auto_correct.py:1544`) interpolates `field_name` directly into SQL, and its own docstring says: *"Callers MUST source `field_name` from a closed enum ... never accept raw operator input here."*

That contract is **already violated** on the tier-2 path: `_handle_multi_field_correction` (line 2098) takes operator-supplied `--custom-value` keys and passes them straight through to `_update_journal_field`, and `_validate_correction_target` checks only the *values* of fields it recognises, never the *names*. So `swing journal discrepancy resolve-ambiguity ... --choice pick_schwab_record_1 --custom-value '{"<identifier>": ...}'` reaches an f-string SQL identifier slot.

**Out of scope — flagged, not fixed** (§9). It is a real finding, it is single-operator/local-only, and fixing it means touching the tier-2 handler family, which this brief does not scope.

**What binds here:** the new surface builds its UPDATE set from a module-level frozen constant, never from anything the operator typed. The operator supplies a *date*; he never supplies a *field name*.

### 2.7 Alternatives considered and rejected

| option | why rejected |
|---|---|
| **Reuse `apply_tier3_override`** | It requires an existing `correction_id` to supersede (`_select_correction_row`, then `AlreadySupersededError` if superseded). Disc 95 has **zero** correction rows (verified live). Tier-3 supersedes corrections; it cannot originate one. |
| **Reuse tier-2 `resolve-ambiguity --choice pick_schwab_record_1 --custom-value '{"fill_datetime": ...}'`** | Would work for the FILL half — `_resolve_affected_target` resolves disc 95 to `fills`/39 — and would write a proper append-only correction. But (i) it structurally cannot touch `trades.entry_date` or `pre_trade_locked_at` (wrong affected target), so the logical correction would be split across two mechanisms with no shared transaction; (ii) it drives the §2.6 identifier hazard on purpose; (iii) the parametric `pick_schwab_record_<N>` entry is constructed at CLI show-time by best-effort parsing candidate text out of `resolution_reason`, and disc 95's reason is the A2-date sentence, so the choice may not even be offerable. Rejected. |
| **A web form on the trade-detail page** | No precedent (D19 shipped CLI-only), two browser-only failure surfaces, an extra operator-witness leg, zero benefit for a once-a-quarter action. |
| **Both CLI and web** | Same, doubled, plus a second code path to keep in parity. |
| **Mint a synthetic discrepancy so the command needs no anchor (option b)** | §2.3 — it can only do so by choosing a false `discrepancy_type`. |

---

## §3 Decision 2 — what "closes honestly" means for discrepancy 95

### 3.1 The finding, restated from the row itself

Discrepancy 95 says, in its own `resolution_reason`: the Schwab execution for order `1007308870656` is **6 NYSE sessions** away from the journal fill it would otherwise match, so the auto-corrector refused to touch it and routed it to a human. The guard was right. The prices agree to four decimals (`$+0.0000`). **Nothing about the broker record was wrong and nothing about the price was wrong; the journal's date was wrong.**

### 3.2 The resolution value

**`journal_corrected`.**

Command, run AFTER the §2 correction lands:

```
swing journal discrepancy resolve 95 \
  --resolution journal_corrected \
  --reason "<see 3.4>" \
  --force
```

### 3.3 Why that sentence is true, and why each alternative is false

`journal_corrected` asserts: *the journal was corrected to agree with the source.* After §2 that is literally what happened — `fills.fill_datetime` moved from 2026-07-23T16:00:00 to 2026-07-31T16:00:00 to agree with `execution_legs[0].time = 2026-07-31T13:30:05+0000`, the exact value this discrepancy's own `actual_value_json` records.

- **`mark_unmatched` — FORBIDDEN, and correctly so.** Its menu text is *"Journal entry has no corresponding broker record."* Broker order `1007308870656` exists, filled 10 shares at $18.80 on 2026-07-31, and is cited in the discrepancy's own payload. This is the false statement RD and the operator refused. It is a tier-2 menu choice (`_handle_mark_unmatched`), so it would also mint a correction row memorialising the falsehood.
- **`source_treated_canonical` — false.** It asserts the source was accepted *without* correcting the journal. The journal was corrected.
- **`acknowledged_immaterial` — false.** `material_to_review = 1`, the finding was material, and it was acted on rather than waved through. It also permits a null reason, which loses the record of what was done.
- **`manual_override` — misleading.** It asserts the operator overrode the finding. He agreed with it.
- **`unresolved` — the status quo.** Correct *today*; false the moment the correction lands.

### 3.4 The reason text

```
Journal corrected, not overridden. Schwab order 1007308870656 executed
2026-07-31T13:30:05Z at 18.80; the journal recorded the order-ENTERED date
2026-07-23 because swing/trades/entry_auto_fill.py read enter_time instead of
executions[].time (D31). trades.entry_date, trades.pre_trade_locked_at and
fill 39's fill_datetime were corrected to 2026-07-31 under correction
<correction_id>. The 6-session A2-date guard that raised this finding was
correct; the data it measured was wrong. Prices never disagreed ($+0.0000).
```

Every clause is checkable against a row or a line of code.

**The `<correction_id>` placeholder needs an executable handoff, or the reason text is false at the moment it is written** *(Codex R6 Major 4)*. §2 and §3 are two separate commands run minutes apart; nothing carried the id between them, so a literal `<correction_id>` would land in the ledger and the sentence claiming to be checkable would cite a placeholder. **Fix:** on success, `correct-entry-date` prints the concrete correction id **and the exact ready-to-paste follow-up command**, reason text and id already substituted:

```
correction 41 applied to trade 19 (entry_date 2026-07-23 -> 2026-07-31).
Next, close the finding that motivated it:

  swing journal discrepancy resolve 95 --resolution journal_corrected --force \
    --reason "Journal corrected, not overridden. ... under correction 41. ..."
```

The operator copies one line rather than composing an audit sentence by hand under a live-ledger gate — and the step-by-step witness (§8) gets a step whose success criterion is unambiguous. A test asserts the printed command contains the real id and no `<` placeholder.

**Two reason templates, because the sentence depends on an unresolved ruling** *(Codex R6 Major 5)*. §2.5 poses `pre_trade_locked_at` to RD; if he rules it stays at 07-23, the text above — which asserts it was corrected — becomes **false in the ledger**, which is the one outcome this whole section exists to prevent. So the plan carries **two** templates, selected by RD's §5.3(4) ruling, and the executing implementer uses the one the ruling licenses:
- **(A) RD accepts the coupled move** (the plan's recommendation): the text above, verbatim.
- **(B) RD rules `pre_trade_locked_at` stays**: identical, with the middle clause replaced by *"`trades.entry_date`, the `watchlist_archive` entry row, and fill 39's `fill_datetime` were corrected to 2026-07-31; `pre_trade_locked_at` was deliberately left at 2026-07-23 per RD's ruling, so the lock time and the fill time are recorded as the distinct events they were."*

**Neither template is written until the ruling exists** — that is why §5.3(4) is a gate and not a note. The correction ledger and the discrepancy's resolution then point at each other, and both say only what happened.

### 3.5 The `--force` gate — expected, disclosed, and recorded

Disc 95 is `pending_ambiguity_resolution` with live `fill_id`/`trade_id`, so the **D22 gate** (`cli.py:3704-3746`) classifies it as `has_menu_path` and refuses a bare `discrepancy resolve`. `--force` is required. That is not a workaround:

- the gate exists to stop a silent bypass of the choice menu; here the bypass is deliberate, because **every menu option available for `multi_match_within_window` is either false (`mark_unmatched`) or audit-only-and-uninformative (`custom` → `_handle_custom_audit_only`) or unconstructible (`pick_schwab_record_N`, §2.7)**;
- the CLI **records** the bypass: `_compose_forced_bypass_reason` prepends a marker to the operator's reason, so the audit row states that the menu was consciously bypassed and why;
- `--force` still enforces the reason requirement for `journal_corrected` (`cli.py:3735`), and the TOCTOU pin (`require_current_resolution='pending_ambiguity_resolution'`) still applies;
- `resolve_discrepancy` clears `ambiguity_kind` in the same UPDATE (`reconciliation.py`, the 18-H.6.1 R2 M#1 branch) so the migration-0031 cross-column CHECK permits the transition.

**Ordering is binding: correct first (§2), resolve second (§3).** Reversed, the reason text asserts a correction that has not happened.

### 3.6 The proof that the close is real, not cosmetic

A **re-run of Schwab reconciliation after the correction must emit no successor finding for trade 19.** Pre-correction the matcher computes `execution_sessions_from_fill = 6` against `fill_datetime = 2026-07-23`; post-correction the same computation against `2026-07-31` yields **0**, prices already agree, and the good-match suppression path applies. This mirrors the D25 close, where the badge's death was witnessed by re-evaluation rather than asserted (run 78, zero discrepancies). Named as an operator-witness step in §8.

---

## §4 A-4 — the dedicated `discrepancy_type`

### 4.1 The mirror count, and the method that produced it

**Method (stated because the count is only as good as it):**

1. Grepped for **four different enum members** (`untracked_broker_position`, `entry_price_mismatch`, `close_price_mismatch`, `equity_delta`, `unmatched_close_fill`) rather than one — a single member bounds the family from below and nothing else.
2. Grepped for the **constant names** (`DISCREPANCY_TYPES`, `_DISCREPANCY_TYPES`, `MATERIAL_BY_TYPE`) — this is what catches `MATERIAL_BY_TYPE`, which contains no member token in its own name.
3. Grepped **`-B2 -A2` for `sector_tamper`** to surface *containers* rather than usages — this is what found `_SUB_CLASSIFIERS`, `_PAIRS_BUILDERS` and `_RENDER_HELPERS_BY_DISCREPANCY_TYPE`, none of which any member-token file-list would have distinguished from a mere usage.
4. **Opened and read every file** the grep named, and classified each hit as MIRROR / DECISION SITE / prose. Five of the ten files the brief lists carry **only comments and docstrings** (`cli_schwab.py:1023`, `config.py:410`, `db.py:51-53`, `metrics/discrepancies.py:15/49/83`, `view_models/reconcile.py:959-962`) — a token grep cannot tell those from a mirror.
5. Grepped `tests/` for the enum constants and for a count assertion.

**The result: 9 REQUIRED sites (R1-R9, of which R8 is a derived CATEGORY rather than a single file — see its boxed note) and 6 DECISION sites.** The comment at `reconciliation.py:44-45` names **four**; four is the count of the *required production* sites, and it is short even there (it omits `EXPECTED_SCHEMA_VERSION` and the backup gate).

**REQUIRED — omit any one and the arc is broken or wrong:**

| # | site | failure if missed |
|---|---|---|
| R1 | `swing/data/migrations/0035_*.sql` — the CHECK, by table rebuild | INSERT rejected. |
| R2 | `swing/data/db.py:67` `EXPECTED_SCHEMA_VERSION` 34 → 35 | `SchemaVersionMismatchError` on every connect; migration never applied. |
| R3 | `swing/data/db.py` — new backup gate + creator + expected-tables set + registration inside `run_migrations` | a v34 production DB crosses to v35 with no pre-migration snapshot. |
| R4 | `swing/data/models.py:1099` `_DISCREPANCY_TYPES` | `ReconciliationDiscrepancy.__post_init__` raises at `models.py:1300` — **every READ of the new row fails**, not just writes. |
| R5 | `swing/trades/reconciliation.py:46` `DISCREPANCY_TYPES` | emit guards `reconciliation.py:324` and `schwab_reconciliation.py:871` raise `ValueError`. |
| R6 | `swing/trades/reconciliation.py:99` `MATERIAL_BY_TYPE` | **`KeyError`** at `reconciliation.py:359` / `schwab_reconciliation.py:888` — the lookup is unguarded `[]`, not `.get`. |
| R7 | `tests/trades/test_reconciliation_service.py:111` `assert len(DISCREPANCY_TYPES) == 11` → `12` | red suite. (`test_material_by_type_covers_all_discrepancy_types` iterates `DISCREPANCY_TYPES`, so it self-extends and needs no edit — verified by reading it.) |
| **R8** | **The schema-HEAD-pinned test population — a DERIVATION EXECUTED IN THE WORKTREE, not a frozen list. 25 files as of authoring.** This entry has now been wrong TWICE; the boxed note below is the actual deliverable. | every one asserts the current head; all go red on the `EXPECTED_SCHEMA_VERSION` bump. |

**DECISION SITES — a default exists, so a miss is silent. Each gets an explicit answer in the plan, per gotcha #11's "audit each as manual-input-allowlist vs service-only":**

| # | site | default if untouched | decision |
|---|---|---|---|
| D1 | `swing/trades/schwab_reconciliation.py:690` `_emit_fills_trades_consistency` | keeps emitting `entry_price_mismatch` | **CHANGE** to `discrepancy_type="fills_trades_price_divergence"`. This is the whole point of A-4. |
| D2 | `swing/trades/schwab_reconciliation.py:1079` + `reconciliation_backfill.py:1531` — the shared `_is_internal_consistency_diagnostic` classify-skip | keys on the `actual_value_json` discriminator | **KEEP the discriminator, do NOT switch to a type check.** Historically-persisted rows (any A-5 row emitted before this migration) carry `entry_price_mismatch` + the discriminator; a type-keyed predicate would stop skipping them and route real rows into the tier-1 path. Keep emitting the discriminator alongside the new type so old and new rows are both covered by one predicate. **Tests must cover BOTH representations through BOTH firing sites** *(Codex R11 Major 3)*: a LEGACY-shaped row (`entry_price_mismatch` + the discriminator, planted by RAW `conn.execute` per the CLAUDE.md write-barrier technique) AND a NEW-typed row (`fills_trades_price_divergence` + the discriminator), each asserted to stay `unresolved` with NO correction row, at the pivot AND at the backfill. **A legacy-only test is satisfiable by the wrong implementation:** switching `_is_internal_consistency_diagnostic` to key on the OLD TYPE would pass it while letting every new-typed row into classification and on to a pending-ambiguity limbo — the predicate's whole job, inverted, with a green test. |
| D3 | `swing/trades/reconciliation_classifier.py:88` `_SUB_CLASSIFIERS` | `.get` → tier-2 `unsupported` | **NO ENTRY.** Both firing sites skip the row before classification (D2), so a sub-classifier would be dead code. The graceful default is also correct if a future path ever reaches it. |
| D4 | `swing/trades/reconciliation_render.py:325` `_PAIRS_BUILDERS` / `:339` `_NO_PAIRS_TYPES` | unknown type → `None`, generic display | **ADD a pair-builder** for the new type. A fills-VWAP-vs-trades-price divergence is exactly a two-column comparison, the payload already carries `entry_fill_vwap` + `trades_entry_price`, and the current emit only renders because it deliberately mirrors a `price` key into the envelope for the legacy consumers. Once the type is its own, render it as itself. |
| D5 | `swing/web/view_models/reconcile.py:549` `_RENDER_HELPERS_BY_DISCREPANCY_TYPE` | `_render_generic_fallback` | **ADD a renderer**, same reasoning as D4 — the web resolve surface should name the two sides. |

**D1/D4/D5 need DISPATCH-level tests, not builder-level ones** *(Codex R3 Major 7)*. `tests/trades/test_fills_trades_consistency_20a.py:150-168` calls the pair builder **directly** and never asserts the emitted `discrepancy_type` — so after D1 changes the emit, that file stays green while the new type could be silently falling through `build_compared_pairs`'s unknown-type → `None` path and the web VM's `_render_generic_fallback`. **A graceful default is exactly what makes a broken dispatch invisible.** Required:
- an **emitter** assertion that `_emit_fills_trades_consistency` writes `discrepancy_type='fills_trades_price_divergence'` (this is D1's own regression, and nothing asserts it today);
- a **dispatch** assertion for the CLI render — call `build_compared_pairs('fills_trades_price_divergence', expected, actual)` and assert a non-`None` pair list, so a missing `_PAIRS_BUILDERS` key fails rather than degrading;
- a **dispatch** assertion for the web pre-resolution VM — the new type resolves to its own renderer, not `_render_generic_fallback`.
| D6 | `swing/web/routes/reconcile.py:184` `_SIMPLE_ACKNOWLEDGEABLE_TYPES` | not acknowledgeable via the simple GUI branch | **DO NOT ADD.** The comment there is explicit that the allowlist is enumerated so a new type is never *silently* auto-acknowledgeable. An A-4 row means the ledger disagrees with itself; one-click acknowledgement is the wrong affordance. Recorded as a deliberate exclusion. |

> ### R8 is a derivation, because a frozen count has now been wrong twice in three rounds
>
> Round 1 caught that the plan named ONE head-pinned test when there were many. I fixed it with a
> list of **24**, produced by `grep -rn "EXPECTED_SCHEMA_VERSION == 34\|version == 34" tests/`.
> Round 3 caught that the list was still short: **`tests/data/test_migration_0010_trade_chart_pattern.py:18`**
> asserts `cur.fetchone()[0] == 34` — a head pin whose text matches neither alternative in my
> pattern. The true set is **25**.
>
> **The lesson is not "25".** I fixed an existence≠completeness finding by writing a pattern and
> trusting its output — which is the same move that caused the finding. A list frozen in a document
> is wrong the moment someone writes a head assertion in a form the author's regex did not imagine,
> and nothing in the document notices.
>
> **So R8 ships a DERIVATION plus a MECHANICAL BELT, and the executing implementer owns both:**
>
> 1. **Derive, in the worktree, at execution time** — a union of forms, not one pattern:
>    `grep -rnE "EXPECTED_SCHEMA_VERSION == 34|version == 34|\[0\] == 34|fetchone\(\) == \(34" tests/`
>    — then **read every hit** and classify it head-pin vs coincidence.
> 2. **The belt that does not depend on my imagination: the full fast suite.** Every head pin, in
>    whatever form, goes RED on the `EXPECTED_SCHEMA_VERSION` bump. The pre-review full-suite run
>    (recipe §2, which runs BEFORE the Codex loop precisely so latent global-invariant breaks surface
>    early) is therefore the authoritative enumerator, and the grep is only a head start. **A green
>    fast suite is the completion proof; the count in this document is not.**
> 3. The 25 known today, for the head start: `test_b7_failure_mode_schema` · `test_db_v8` ·
>    `test_migration_0010_trade_chart_pattern` · `test_migration_0012` · `0013` · `0015_finviz_api_calls` ·
>    `0016` · `0017` · `0018` · `0019_atomic_apply` · `0025_phase16` · `0026_broad_watch_baseline` ·
>    `0027_entry_intent` · `0028_watchlist_pin` · `0030_yfinance_calls` · `0031_untracked_broker_position` ·
>    `0032` · `0033` · `0034_h1_criteria_amendment` · `test_no_schema_change_v3` ·
>    `test_phase13_t3_sb1_prerequisite` · `test_temporal_log_migration` · `test_v20_migration` ·
>    `test_v21_migration_trade_backlinks` · `test_v23_migration` (all under `tests/data/`).

**R9 — the enum-ACCEPTANCE test, and why R8's belt cannot catch it.** *(Codex R5 Major 2.)* `tests/data/test_phase9_reconciliation_schema_verification.py:299-317` inserts each `discrepancy_type` value through the schema and asserts it lands; its docstring reads *"All 10 discrepancy_type enum values per migration §3 land cleanly."* It is **already stale at eleven** (18-H.6 widened the enum and did not update it), and it is invisible to every instrument this plan has so far named:

- **R8's grep misses it** — it pins no schema VERSION, so no `== 34` pattern touches it;
- **R7's grep misses it** — it imports no enum constant, it hard-codes the ten strings inline;
- **and, the part that matters, THE FULL SUITE MISSES IT TOO.** It is an ACCEPTANCE test: inserting ten still-valid values through a twelve-value CHECK **passes**. It goes green while asserting less than it claims. R8's belt — "the suite reds every head pin" — is sound for R8's class and **structurally cannot see this one**, because a stale acceptance test's failure mode is silence, not red.

**Fix:** update it in the T3 one-commit sweep, and while there **derive the loop from `DISCREPANCY_TYPES`** instead of re-listing the strings, so the next widening cannot leave it behind again; correct the stale docstring count. **The general lesson, which is the reason this is written up rather than just fixed:** an enumeration test that ASSERTS ACCEPTANCE of a list must derive that list from the canonical container, or it silently narrows every time the container grows — and no suite run will ever tell you. That is the same asymmetry as an arm-flag negative test and as D4/D5's graceful-default dispatch: **three instruments in this one plan whose failure mode is passing quietly.**

**Two traps inside R8, both of which a bulk edit would spring:**

- **`tests/data/test_migration_0017.py:88` reads `assert len(cols) == 34` — that is a COLUMN COUNT, not a schema version.** A `sed s/== 34/== 35/` across `tests/data/` corrupts it into a passing-looking assertion about the wrong thing. **Edit by reading each hit, never by pattern substitution** — the same discipline that produced the §4.1 enumeration, applied to the fix rather than the count.
- **`tests/data/test_no_schema_change_v3.py` is a HEAD-TRACKING CEILING GUARD, not a freeze.** Its own comment says so: *"this guard tracks the current HEAD so the schwabdev-arc invariant (it added nothing of its own) stays auditable"*, and `test_no_new_migration_file_added` asserts `versions[-1] <= 34`. Both move to 35, and the comment's migration inventory gains the 0035 entry. Updating it is the guard working as designed for an authorized migration — **but only because the migration IS authorized** (CHARC's §3 pass); an unauthorized one must still trip it, so the update belongs in the same commit as the migration and nowhere else.

**Also touched (decay, not mirrors):** `reconciliation_render.py:~356` docstring says *"One of the ten canonical discrepancy type strings"* — **already stale at eleven**; 18-H.6 widened the enum and left it. Corrected to twelve in the same commit. `db.py:51-53`'s migration comment block gets its 0035 sibling entry.

### 4.2 The migration — `0031` copied verbatim

SQLite cannot ALTER a CHECK, so `0035_fills_trades_price_divergence.sql` is `0031`'s rebuild with one value added:

- `BEGIN;` … `COMMIT;` explicit (gotcha **#9** — `executescript` autocommits; the runner's `_apply_migration` wraps it and holds `foreign_keys=OFF` so the DROP does not cascade-null `reconciliation_corrections`' FK).
- `CREATE TABLE reconciliation_discrepancies_new` reproducing **every** column, the 9-value `resolution` CHECK, the 7-value `ambiguity_kind` CHECK, and the cross-column pairing CHECK **verbatim**; only `discrepancy_type` gains `'fills_trades_price_divergence'` (11 → 12).
- Explicit-column `INSERT … SELECT`, `DROP`, `RENAME`, then **all five** indexes recreated (`_run`, `_trade`, `_unresolved`, `_material`, `_pending_ambiguity` — the last is partial; verified against `0031:105-118`).
- `UPDATE schema_version SET version = 35;` as the **FINAL** statement before COMMIT (the Phase-9 §A.0 R1 Critical #1 precedent: a truncated transaction must never leave the stamp ahead of the schema).

**Backup gate** — copy the `_h1_amendment_backup_gate` shape (`db.py:1734`) verbatim, with **STRICT equality**:

```
if target_version < 35 or current_version != 34:
    return
```

Plus `_create_pre_a4_taxonomy_migration_backup` (filename `swing-pre-a4-taxonomy-migration-<ISO>.db`), an expected-tables set derived from `H1_AMENDMENT_PRE_MIGRATION_EXPECTED_TABLES` (that chain already includes `reconciliation_discrepancies`, the table this migration rebuilds — the fail-closed property the H1 gate's comment was written to establish), and registration in `run_migrations` after `_h1_amendment_backup_gate`. A **run-migrate-twice no-op test** goes with it.

### 4.3 The one-commit boundary (gotcha #11)

R1-R9 + D1-D6 + the two decay edits land in **ONE commit**. TDD within it: the red state is R7's `== 12` plus a round-trip test inserting and reading back a `fills_trades_price_divergence` row through the production writer.

### 4.4 The type name and its materiality — posed, not chosen

- **Name: `fills_trades_price_divergence`** — ruled verbatim by RD's rider and the commissioning brief; already the module's internal vocabulary (`_INTERNAL_CONSISTENCY_FILLS_VS_TRADES`). No latitude taken.
- **`MATERIAL_BY_TYPE` value: recommended `1`.** Grounds: the A-5 emit is documented as MATERIAL and today inherits `MATERIAL_BY_TYPE['entry_price_mismatch'] = 1`, so `1` is the **no-change-in-behaviour** value and `0` would be a silent de-escalation of a live alarm riding in on a taxonomy change. The 20-A plan states the intent directly: *"The row stays `unresolved` + material (surfaces in the material-discrepancy banner — CORRECT; A4 findings SHOULD demand attention)."*
- **But materiality is a judgment about what reaches the operator, so it is RD's, and it is posed rather than taken.** Two questions for him: **(i)** confirm `1`; **(ii)** with the type now isolated, does an A-4 row belong in the topbar material banner alongside broker-vs-journal findings, or is it a separate internal-integrity signal? Today's `1` puts it in the same banner by construction.
- **Whatever RD rules, the value gets its OWN assertion** *(Codex R6 Major 7)*. `tests/trades/test_reconciliation_service.py:150-166` iterates `DISCREPANCY_TYPES` and asserts only that **a** value exists for each — so a mistaken `0` on the new type silently de-escalates a live alarm while the suite stays green. The existing test is a coverage check, not a value check, and coverage is exactly what a wrong value satisfies. Add `assert MATERIAL_BY_TYPE["fills_trades_price_divergence"] == <RD's ruling>` beside the existing per-type value assertions, and make it part of T3's acceptance gate. **This is the fourth instrument in this plan whose failure mode is passing quietly** — with R9's acceptance test, the arm-flag negative test, and D4/D5's graceful-default dispatch. The pattern is worth naming: *a test that asserts a key EXISTS cannot tell you the value is right, and on a materiality flag the wrong value is silence where an alarm belonged.*

---

## §5 Decision 3 — downstream consequences of moving a CLOSED trade's entry date eight days

Every number below was derived from live rows. **Nothing here changes H1's sample (§1.4).** Several things change numbers RD reads, which is his gate.

### 5.1 Numbers that MOVE

| consumer | mechanism | before | after |
|---|---|---|---|
| **`metrics/process.py:203 _holding_period_trading_days`** → the cohort-mean `holding_period_days` process metric (row 21) | `pre_trade_locked_at` → `last_fill_at`, Mon-Fri inclusive | 07-23 → 08-04 = **9 trading days** | 07-31 → 08-04 = **3** |
| **`metrics/capital.py:402 _capital_cycle_time_days`** — mean(`last_fill_at` − `pre_trade_locked_at`) over the closed cohort | same two columns, calendar days | trade 19 contributes **12.0 d** | **4.0 d** |
| **`journal/analyze.py:108 _fetch_recommendations`** → `pct_above_pivot`, `stop_dev_pct`, `days_rec_to_entry` | picks the latest useful-bucket (`aplus`/`watch`/`skip`) candidate with `run_ts < entry_date+1d` | candidate **11551** (run 125, 07-23; pivot 20.19, initial_stop 16.515) | candidate **11852** (run 130, 07-30; pivot 21.39, initial_stop 16.554) |
| ⤷ `pct_above_pivot` = (18.8 − pivot)/pivot | | **−6.88 %** | **−12.11 %** |
| ⤷ `days_rec_to_entry` | | 0 | 1 |
| **`trades/review_auto_fill.py` MFE/MAE (review-form default)** | a SOURCE LADDER, not a plain slice: `compute_mfe_mae_from_ohlcv_cache` tries active `daily_management_records` snapshots FIRST (`:53-114`) and only falls back to OHLCV, where `_ohlcv_mfe_mae` skips every bar with `d < entry_dt` (`:183-184`) | **snapshot branch: does NOT move** — and trade 19 HAS 3 active snapshots, so its form default is unchanged. **OHLCV-fallback branch: moves**, by DROPPING the 07-23..07-30 bars from the post-entry window | *(Codex R9 Major.)* My earlier wording — "8 extra sessions of pre-entry bars" — was wrong twice over: the slice is post-entry-only in both branches, so those bars were never "pre-entry" inclusions, and the ladder means the branch that moves is not the branch trade 19 uses. **The executing implementer verifies which branch fires before the witness rather than asserting either.** |
| **`metrics/funnel.py:190/200`** — the A+/watch "taken" funnel counts | `substr(pre_trade_locked_at,1,10) = run_session_date` | trade 19 (`trade_origin='pipeline_watch_manual'`, a `WATCH_TRADE_ORIGINS` member) counts in the **07-23** session's funnel | counts in the **07-31** session's funnel |
| **`journal/flags.py:39`** — the behavioral holding-days flag | `(last exit − entry_date).days` | 12 | 4 |
| **`journal/flags.py:50 _caution_market_entries`** | `weather_by_date.get(t.entry_date)` — the flag fires on ≥2 entries made in Caution/Bearish weather | reads the **07-23** weather row | reads the **07-31** weather row. **The regime does NOT change:** live `weather_runs` id 65 (`asof_date 2026-07-23`, SPY) and id 71 (`2026-07-31`, SPY) both read `status='Caution'`, so trade 19 stays in the flag's sample. **The lookup key moves; the classification does not.** *(Codex R2 minor — my first pass left this as "verify at execution"; it is verifiable now, so it is verified now.)* |
| **`web/view_models/journal.py:334-341`** — the journal row's displayed `days_open` | `(exit_date − entry_date).days` | 12 | 4 |
| **`web/trade_charts.py:76 / :100`** — the position-detail chart and its thumbnail | `entry_date` anchors a PADDED window: `window_start = entry_date - PAD_BEFORE_DAYS` (30) (`:28`, `:56`) | padded window opens ~06-23; the **entry marker** sits at 07-23 | window opens ~07-01; the entry marker moves to 07-31 (both renderers) *(Codex R9 minor — my "window opens 07-23" ignored the 30-day pad; the window SHIFTS with the date, it does not start on it)* |
| **`journal/tos_import.py:1006 _matches_closed_trade`** | matches a TOS statement fill by `(ticker, date, qty, price)` | a re-imported statement row dated 07-31 would NOT match trade 19 and would be reported `unmatched_open` | matches → `already_reconciled` |
| **`web/view_models/trades.py:2032`** → `templates/trades/detail.html.j2` | displays `pre_trade_locked_at` verbatim on the trade-detail page | shows `2026-07-23T16:00:00` | shows `2026-07-31T16:00:00`. Display-only, no derivation — but it is the field the operator will look at first at the witness, so it is listed rather than left implicit *(Codex R4 minor)*. |
> **Two rows moved OUT of this table** *(Codex R7 Major 1)*. `rendering/briefing.py:157` (inside `_open_positions`, driven by `inputs.open_trades`) and `trades/advisory.py:132` (reached via `dashboard.py:1365 compute_all_suggestions`, the open-positions VM) fire on **OPEN positions only**. Trade 19 is CLOSED, so **neither moves for this correction** — they are FORWARD-case consequences and they belong in the `--allow-active` inventory (items 8 and 3), where they now are. I had listed them here as trade-19 changes because the register names them among D31's four symptoms — true of the defect while the position was open, false of the correction applied today. **A symptom the defect caused is not automatically a number the fix moves.**
| **`data/repos/trades.py:834 list_trades_with_activity_in_period`** → `web/view_models/trades.py` (the cadence-review surface) | `was_opened_in_period: entry_date >= ps AND entry_date <= pe`, and `entry_date` is the fallback activity timestamp for ordering | trade 19 appears as `[OPENED]` in the period containing **07-23** | appears in the period containing **07-31**. On a weekly cadence those are different reviews — the week that reported "no new trades" while a live fill sat invisible (the register's fourth symptom) is the week this row moves it INTO. |
| **`latches/reader.py:131` + `latches/service.py:248-259`** — the latch surface, on a **CLOSED** trade too | `_entries_by_ticker` selects trades **with NO state filter** (only the voided exclusion), `ORDER BY entry_date, id`; `service.py` then matches `draft.anchor <= e.entry_date <= as_of` and breaks ties with `min(..., key=(entry_date, trade_id))` | trade 19 participates at 07-23 | participates at 07-31 | *(Codex R10 Major 1.)* I had confined this to the ACTIVE inventory on the assumption that latches only see open positions. **They do not** — the reader loads every non-voided trade regardless of state, so a CLOSED trade's date still feeds latch eligibility and terminal ranking, including any historical `as_of` replay. **Requires an explicit witness step:** run the latch panel before and after and confirm no latch resolution changed, rather than asserting it. FTRE has no open position, so no change is EXPECTED — expected is not verified. |
| **`metrics/capital.py:428 _count_open_at_run`** — the HISTORICAL `concurrent_open_positions` trend | `pre_trade_locked_at <= started_ts` decides whether a trade was open at a PAST run instant | trade 19 counts as open for every run started on/after 07-23 | counts only from 07-31 — **the trend points for the runs in between change retroactively** | *(Codex R11 Major 1.)* §5.1 already listed `capital.py:101`'s current-window use; this is the historical replay of the same predicate, and it rewrites past points on a chart the operator reads as history. The executing implementer QUANTIFIES the affected runs (live: those started 2026-07-23..07-30) and the witness includes the trend before and after. |
| **`metrics/cohort.py:89`** | `ORDER BY entry_date, ticker, id` | trade 19 sorts by 07-23 | sorts by 07-31. **Membership is unchanged (§5.2); the ORDER is not** — a cohort listing's row sequence changes even where its contents do not. |
| **`trades/daily_management.py:546`** — the MFE/MAE running anchor | `date.fromisoformat(trade.pre_trade_locked_at[:10])` | future snapshots would anchor at 07-23 | anchor at 07-31. **Past snapshots are persisted and do not move** (§5.2) — so trade 19's stored MFE/MAE keep the old anchor while any new snapshot would use the new one. Trade 19 is closed, so no new snapshot will be taken; on an ACTIVE trade this is one of the `--allow-active` consequences named at §2.4 step 3. |

*(The funnel, both flags entries, and the four rows above are Codex R1 Major 2 + R2 Major 4. My first pass missed all of them, and the reason is worth stating because it is reusable: the grep that produced §5.1 keyed on `entry_date` / `pre_trade_locked_at` as **Python attributes**, which does not see a column name inside a SQL string (`substr(pre_trade_locked_at, 1, 10)`), a dict lookup (`weather_by_date.get(t.entry_date)`), or a value passed positionally into a matcher (`date=f.date` against a closed-trade predicate). **An attribute grep under-counts a data-flow question.**)*

> **This table grew in EVERY review round — 7 rows, then 11, then 13, then 16 — and I claimed it complete twice before it was.** Rounds 3 and 4 each found consumers a fresh read of the `grep -rln` sets had supposedly already covered (the cadence-period reader, the cohort ordering, the latch reader/service, the detail VM). **So this section makes no completeness claim.** It is the best inventory four adversarial passes produced, it is what RD's §5.3 gate is asked to accept, and the executing implementer re-derives it against the merged head before the witness. The honest statement about an enumeration this document cannot mechanically verify is *"here is what was found and how"* — not *"this is all of it."*

**`tos_import` is the one with a direction worth naming.** It is the only consumer where the correction changes a **future** behaviour rather than a displayed number: after the fix, re-importing a TOS statement covering 2026-07-31 recognises FTRE as already reconciled instead of reporting a phantom unmatched open fill. That is the correction paying for itself, and it belongs in the witness only as an explanation — no re-import is required.

The `analyze.py` move is worth naming as a *positive*: candidate 11852 is `trades.candidate_id` (§1.6). Post-correction the journal's recommendation attach agrees with the trade row's own backlink. Two independent paths that currently disagree begin to agree — and that is the strongest single piece of evidence that 07-31 is the true date.

**A caution on the same line.** The 07-31 evaluation run (131) buckets FTRE as `excluded` (the standard open-position exclusion). `_USEFUL_BUCKETS` filters `excluded` out, so the attach lands on the 07-30 `watch` row rather than a same-day `excluded` one. The behaviour is correct here, but it is correct *because* of a bucket filter rather than by design, and any future change to `_USEFUL_BUCKETS` would move this trade's deviation metrics again. Recorded, not acted on.

### 5.2 Numbers that DO NOT move — checked, not assumed

- **R-multiples and realized P&L.** `derived_metrics` contains no `entry_date` reference (grepped: zero hits). R is a function of `entry_price`, `initial_stop`, exit price and shares. **Unchanged.**
- **The process-metrics card's `mfe_R` / `mae_R` cells.** *(Codex R1 Major 2, second half — and this one corrects a directional error, not an omission.)* `metrics/process.py:299 _read_latest_mfe_mae` reads the **persisted** `daily_management_records.open_MFE_R_to_date` / `open_MAE_R_to_date` for the latest non-superseded `daily_snapshot`. It does **not** recompute from `entry_date`. Trade 19 has 3 such snapshot rows (latest `review_date` 2026-08-05), so its persisted MFE/MAE **do not move**, and the correction will NOT retroactively re-anchor them. That is the right V1 behaviour — those rows are dated observations of what was true on the day, not derived values — but it means the card keeps MFE/MAE measured from a window that began on a date the ledger no longer claims. **Stated as a known residue, not silently left:** re-deriving historical daily-management snapshots is out of scope and would be a separate arc. The `review_auto_fill.compute_mfe_mae` path in §5.1 is a *different* consumer — a form default computed live at review time — and it does move. Two paths, opposite answers; the plan's first pass conflated them.
- **H1 (`A+ baseline`) sample, 2/20.** Trade 19's label matches H5. **Unchanged** — and `swing/metrics/cohort_intent.py`'s H1 clause predicates on `entry_intent`, which this arc does not touch.
- **H5 (`Broad-watch baseline`) sample count.** Membership is `_label_matches_hypothesis` + `trade_counts_toward_cohort`; neither reads `entry_date`. **Unchanged.**
- **H5 tripwire streak.** `compute_tripwire_status` (`hypothesis.py:542`) sorts matched trades by `(entry_date DESC, id DESC)`. Trade 19 is the only H5-matched closed trade in the live registry, and it is also the highest id — so the sort is stable under the move. **Unchanged in fact, order-dependent in principle**; a discriminating test pins the ordering rather than the count.
- **Cumulative P&L / absolute-loss tripwire.** Sums over `realized_pnl`. **Unchanged.**
- **`trades.candidate_id` / `pattern_evaluation_id`.** Stored backlinks, not recomputed. **Unchanged** (§1.6 — they are already right).
- **Reconciliation run 93's counters.** Historical run rows are not rewritten; the discrepancy's own `resolution` moves, and `resolve_discrepancy`'s counter decrement only fires on a prior state of `unresolved` (disc 95 is `pending_ambiguity_resolution`), so **run 93's counters are untouched**. Verified by reading the branch.

### 5.3 What RD is being asked to rule

1. **Confirm the §1.4 correction** — trade 19 is H5, not H1; the arc changes no H1 number. His gate stands on §5.1, not on an H1 sample change.
2. **Accept the §5.1 moves**, particularly `holding_period_days` 9 → 3 and the cohort-mean cycle time, both of which are cohort aggregates on a live dashboard.
3. **A-4 materiality** (§4.4) — confirm `1`, and rule on banner placement.
4. **`pre_trade_locked_at`** (§2.5) — the plan moves it with `entry_date` because that is its only derivation. If RD wants lock-time and fill-time to become independent facts, that is schema and a separate arc; if he wants it left at 07-23 *without* schema, say so and the plan drops it from the update set (and `holding_period_days` then reads 9 against an entry date of 07-31, which is self-contradictory — stated so the choice is made with its consequence visible).
5. **The second-type question** (from §1.3): the taxonomy still has no word for a broker-vs-journal **date** divergence. The 12-value enum after A-4 does not gain one. Adding `entry_date_mismatch` in the same rebuild would be mechanically free but is **new ruled content**, so it is **posed, not built**. It is also what would let §2.3's option (b) close the unanchored half of D19 honestly.

**RD's sequencing note holds and is unaffected:** item 5 and D29 are order-independent; both precede any H1-consuming read in September.

---

## §6 Rider 1 — the legless-order skip (`mappers.py:285`)

**RD-ruled minimum: COUNT-AND-SURFACE, not stop-skipping.** Verified on disk: `map_orders_to_fill_candidates` has **two** silent `continue` branches, not one — line **294** (missing/empty `orderLegCollection`) and line **303** (non-dict `orderLegCollection[0]`). Both `log.warning` and drop the order. Nothing counts them; nothing reaches `warnings_json`. The consumer chain is `get_account_orders` → `integrations/schwab/pipeline_steps.py` → nightly reconciliation Pass 2, where a dropped order is a **false negative on a fill**: reconciliation sees nothing, raises nothing, reports clean. Gotcha **#27** in a mapper rather than a pipeline step.

**The out-parameter design in this plan's first draft was UNIMPLEMENTABLE, and the reason is a seam I had not read.** *(Codex R2 Major 3.)* `map_orders_to_fill_candidates` is never called directly by the wrappers — it is passed as a **value** into the shared `_call_endpoint`, which invokes it **positionally with exactly one argument**:

```
swing/integrations/schwab/trader.py:660      mapped = mapper(payload)
```

A `skips=` keyword cannot reach it through that seam. And there are **two** wrappers, not one: `get_account_orders` (`trader.py:329`, `mapper=` at `:374`) and `get_account_orders_audited` (`trader.py:379`, `mapper=` at `:431`) — the audited variant feeding the Pass-2 backfill (`reconciliation_backfill.py:652`). A design that threaded only the first would leave the backfill path exactly as blind as it is today, which is the half the register cares about.

**Revised design — a `functools.partial` bound accumulator, so the seam does not change:**

- `map_orders_to_fill_candidates(response, *, skips: list[dict] | None = None)` gains the keyword, default `None`, preserving every existing caller byte-identically;
- each wrapper allocates its own `skips: list[dict] = []` and passes `mapper=functools.partial(map_orders_to_fill_candidates, skips=skips)`. `_call_endpoint` still calls `mapper(payload)` positionally and needs **no change at all** — the accumulator rides in the closure. This is strictly better than widening `_call_endpoint`'s contract, which is shared by every Schwab endpoint and has no business knowing about order legs;
- each skipped order appends `{"order_id": ..., "index": i, "reason": "missing_or_empty_leg_collection" | "non_dict_leg_0"}` — **both** silent branches (`mappers.py:294` and `:303`), not just the one the register named;
- **ONE contract, stated once** *(Codex R3 Major 10 — my previous draft said both "wrappers return the skip list alongside their result" AND "an optional caller-supplied out-parameter", which are different return shapes; a plan that specifies two contracts specifies none)*: **return shapes NEVER change.** Both wrappers gain `skips: list[dict] | None = None`; when a caller passes a list, the wrapper binds it into the partial and it fills. Callers that do not pass one get today's behaviour byte-for-byte. That is the single contract at all three layers — mapper, wrapper, caller;

- **the Pass-1 caller is `pipeline_steps.py`, NOT `schwab_reconciliation.py`** *(Codex R3 Critical 2 — my previous draft wired it to the wrong layer, so the accumulator would have been allocated somewhere that never calls the fetch and the whole rider would have been inert on the nightly path)*. The real chain, read: `swing/integrations/schwab/pipeline_steps.py:523` calls `get_account_orders(...)` and passes the returned orders into `run_schwab_reconciliation(...)` at `:589`; **`schwab_reconciliation.py` never calls `get_account_orders` at all**. So:
  - **Pass 1:** `pipeline_steps.py` allocates the list, passes it to `get_account_orders` at `:523`, and merges a non-empty result into the step's warning envelope alongside the reconciliation run's own warnings — **on EVERY return path after the fetch, not only the success one** *(Codex R4 Major 2)*. `_step_schwab_orders` has three post-fetch early returns that carry no warnings today: the Trader-API failure dict (`:554`), the sandbox short-circuit (`:567`, `status='sandbox_audit_only'`), and the reconciliation-raised failure (`:609`). A skip recorded at `:523` and then dropped by any of them is **a silent skip inside the fix for silent skips** — gotcha #27 reproduced in its own remedy. Every one of those dicts gains the warning entry, and **at least one failure path and the sandbox path get discriminating tests**, because the success path alone cannot show the difference;
  - Pass 1 emits `{"step": "schwab_orders", "reason": "legless_orders_skipped", "skipped_count": N, "order_ids": [...]}` — the envelope already carries per-step warning dicts of exactly this shape (verified against live run 93's `summary_json`);
  - **Pass 2 has NO such envelope, and my previous draft asserted one it does not have** *(Codex R8 Major)*. The backfill is a CLI, not a pipeline step: `get_account_orders_audited` returns `(call_id, orders)` (`trader.py:379-434`), `_pass_2_dispatch` returns `(reclassification, call_id, failure_reason)` (`:599-621`), and **`BackfillSummary` (`:170-234`) is a flat set of integer counters with no warnings field at all** — I had generalized "the run's warning envelope" from Pass 1 to a surface that has none, which would have left the Pass-2 half collecting skips and dropping them. **That is the rider's own failure mode, one layer down, for the second time in this review** (round 4 caught it on Pass 1's early returns). **Transport, specified concretely:**
    - `BackfillSummary` gains **`legless_orders_skipped: int = 0`** and **`legless_order_ids: list[str] = field(default_factory=list)`** — additive, defaulted, matching the counter-plus-detail shape its neighbours already use;
    - `_pass_2_dispatch` returns the skip list alongside its existing tuple (or fills a caller-passed accumulator, mirroring the wrapper contract above), and `run_backfill` folds it into the summary;
    - **`format_summary_block` renders a line when the count is non-zero** — that is the actual "surface" half, and without it the counter is just a quieter silence;
    - the partial/interrupted summary path renders it too, so an aborted backfill still reports what it dropped;
    - **a discriminating Pass-2 test** plants a legless order in the fetched payload and asserts the count, the ids, AND the rendered line — not merely the counter, since a counter nobody prints is exactly the gap this rider exists to close.
- **an absence renders as a labelled gap, not a clean pass.** Both branches count, on both paths.

**Both-modes test requirement applies** (recipe §2A, RD's attached rule): the negative test — "a well-formed orders payload produces an empty skip list" — asserts the **counterfactual fields** (skip list empty AND the returned order count equals the input count), and the founding case runs both with and without the `skips` accumulator supplied, so a test cannot pass merely because the feature was not exercised.

**RD is explicitly not asserting an incidence rate**; the ruling rests on the asymmetry. The plan asserts none either — no "this happens N times a night" claim appears in the code comments or the tests.

---

## §7 Rider 2 — the D-2b framing correction

Item 4 deferred the cancel→place attribution chain here, and the dispatch brief already retracts the phrase it travelled with. **Verified independently against `0033_latch_order_intents.sql`:** the migration declares exactly two UNIQUE constraints — `(candidate_id, view_session_date, surface)` and `(idempotency_key)` — and **neither is on `actual_broker_order_id`**. So "every hop is schema-guaranteed" is false. The LAST hop is guaranteed by `(idempotency_key)`; the FIRST is not, and can match **zero or several** `latch_order_intents` rows.

**Disposition: not designed here.** The attribution chain is not in this arc's scope (D31 + A-4 + the two riders' *minimum* fixes), and a design that needs defined zero-match and multi-match semantics is a design task, not plumbing. **Carried forward with the corrected framing attached** so the false premise dies here rather than propagating into a third brief:

- **hop 1** (cancel → the intent row): NOT unique-constrained. Any design must define zero-match (no intent row — an out-of-band cancel) and multi-match (several intents share a broker order id).
- **hop 2** (intent → the placement): guaranteed by `(idempotency_key)`.

Flagged in §9 for the Phase-22 scoping deliverable.

---

## §8 Task order, gates, and the operator witness

| # | commit | contents |
|---|---|---|
| **T1** | `fix(trades): D31 — entry auto-fill takes the execution timestamp` | `entry_auto_fill.py:438` reads the execution grain via a new `_execution_date(chosen)`. **The algorithm, stated here exactly as §8.1 specifies it** *(Codex R4 Major 4 — this row previously said "the latest leg" and "falls back only when executions are absent", both of which contradict §8.1; an implementer working from the task table would have written `[-1]` and accepted malformed legs)*: **parse EVERY leg's `time` and take `max()` over the parsed datetimes**, then emit that datetime's naive `[:10]` prefix (§8.2). Fall back to the `enter_time` date when `executions` is absent/empty (the legacy-mapper rule-1 path) **OR when ANY leg's `time` is unparseable** — never rank a malformed value. `schwab_source_value_json` gains `entry_date_source: "execution_leg" \| "enter_time"` (envelope only — `EntryAutoFillResult` gains no field) so the envelope records **which** it used: per-row provenance at write time (**#30**). Tests per §8.1. |
| **T2** | `feat(trades): the audited entry-date correction surface` | new `swing/trades/entry_date_correction.py` + `swing/data/repos/trades.py::update_entry_date_fields` (a narrow closed-enum updater modelled on `update_entry_intent`) + the CLI command + `--dry-run`. No schema. |
| **T3** | `feat(data): migration 0035 — the fills_trades_price_divergence type` | **the #11 one-commit sweep**: R1-R9 + D1-D6 + the two decay edits (§4) — R8's head-pin updates and R9's derived acceptance test are migration-sweep changes, not follow-ups (Codex R6 Major 6). |
| **T4** | `fix(schwab): rider 1 — count and surface skipped legless orders` | §6. |
| **T5** | `docs(harness): rider 2 — the corrected D-2b framing` | §7; carried, not built. |

**Sequencing rationale.** T1 before T2 so the surface is not the only thing standing between the operator and a repeat. T3 is independent of T1/T2 and could be first; it is placed third so the migration is not in flight while the correction semantics are still settling.

### 8.1 T1's test spec — the vacuous-test trap is already baked into the fixtures

*(Codex R1 Major 5.)* "Frozen-clock tests" was not a sufficient specification, and the reason is concrete: **`tests/trades/test_entry_auto_fill.py:106-117` builds its `SchwabExecutionLeg` with `time=enter_time`** — the fixture forces the two timestamps EQUAL. Every existing test in that file therefore passes identically under the pre-fix and the post-fix code. A T1 that shipped with only the existing fixtures green would be a textbook vacuous regression: the suite would prove nothing about the line that changed.

T1's tests must therefore include, at minimum:

**Where `entry_date_source` lives — one answer, not two.** *(Codex R3 Major 8.)* `EntryAutoFillResult` (`entry_auto_fill.py:147-155`) has **no such field**, and adding one would ripple through every consumer of the dataclass plus its `__post_init__`. The provenance stamp therefore goes **only** into the existing `schwab_source_value_json` envelope (which already carries `entry_date`, `entry_price`, `shares`, `schwab_order_id`, `schwab_instrument_symbol`), as a new key `entry_date_source`. **Tests assert it by parsing that JSON — `json.loads(result.schwab_source_value_json)["entry_date_source"]` — never as a dataclass attribute.** My earlier draft asserted a nonexistent attribute in §8.1 while T1 said the value lived in the envelope; that contradiction is resolved in favour of the envelope.

1. **The discriminating case.** `enter_time = "2026-07-23T14:30:00.000Z"`, execution leg `time = "2026-07-31T13:30:05+0000"` (the real live shape from disc 95's payload, `+0000` offset and all — derived from the emitter, not invented). Assert `result.entry_date == "2026-07-31"` **and** the envelope's `entry_date_source == "execution_leg"`. **Computed under both paths:** pre-fix this returns `"2026-07-23"`, post-fix `"2026-07-31"` — the test distinguishes.
2. **The fallback case.** An order with `executions=None` (the legacy-mapper rule-1 path). Assert the result falls back to the `enter_time` date **and** that the envelope stamps `entry_date_source == "enter_time"`. The date assertion passes pre-fix too — that is the point: it pins that the fix did NOT break the legacy path.
3. **The multi-leg case, and "latest" must be DEFINED — with a fixture that actually defeats both indices.** *(Codex R2 Major 5, sharpened by R3 Major 3.)* `_extract_executions_from_order_raw` builds its list with a plain `collected.append(leg)` (`mappers.py:532`) — **API order, never sorted**. So `executions[-1]` is "whatever Schwab listed last," not "the latest execution," and the two coincide only by luck. `_execution_date` must **parse each leg's `time` and take `max()` over the parsed values**, never index the list.
   **The two-leg reverse-order fixture I first specified was NOT discriminating:** with legs `[2026-08-03, 2026-07-31]`, `max()` and `legs[0]` both return `2026-08-03`, so a `[0]`-based implementation passes. **Use THREE legs with the maximum in the MIDDLE** — `[2026-07-31, 2026-08-03, 2026-08-01]`, expected `2026-08-03`. `legs[0]` yields `2026-07-31` (fails), `legs[-1]` yields `2026-08-01` (fails), `max()` yields `2026-08-03` (passes). One fixture, both wrong implementations excluded. *(This is the regression-test-arithmetic discipline: compute the expected value under every implementation you are trying to exclude, not just the one you are trying to confirm — I got it wrong once in this very section.)*
   **Parsing note:** the live shape is `2026-07-31T13:30:05+0000`, whose `+0000` offset `datetime.fromisoformat` accepts on Python 3.11+. Compare parsed datetimes. If ANY leg's `time` is unparseable, do **not** silently rank a malformed value — take the `enter_time` fallback and stamp `entry_date_source="enter_time"`, so a parse failure is visible in the envelope rather than absorbed. The DATE finally emitted is still the naive `[:10]` prefix — §8.2.
4. **The malformed-leg case — the one the fallback rule exists for, and it was unwritten.** *(Codex R5 Major 4.)* `SchwabExecutionLeg.time` is validated as *non-empty*, not as *parseable*, so any non-empty string reaches `_execution_date`. Plant **two legs, one valid and one malformed** (`time="not-a-timestamp"`); assert the result falls back to the `enter_time` date **and** stamps `entry_date_source == "enter_time"` in the envelope. Without this, the "if ANY leg is unparseable, fall back" rule is a sentence no test enforces — and the tempting wrong implementation (skip the bad leg, `max()` the rest) passes every other case in this list while silently dating the trade from a partial view of its own fills.
5. **The existing-fixture sweep.** The `time=enter_time` default in the fixture builder stays (it is the common real shape) so the file's other ~20 tests keep passing unchanged — evidence the fix is behaviour-preserving where the two timestamps agree.

Frozen clock throughout; no test reads `datetime.now()`.

### 8.2 The timezone convention — deliberately matched, not silently inherited

`_execution_date` emits the **naive `[:10]` prefix of the execution timestamp**, i.e. the UTC calendar date, with **no conversion to America/New_York**. That is a decision, not an oversight, and the reason is the two-path-divergence class (**#24-#26**): the reconciliation side already does exactly this —

```
swing/trades/schwab_reconciliation.py:588      leg_date = _date.fromisoformat(str(raw_time)[:10])
```

— so an auto-fill that converted to ET while the A2-date guard did not would manufacture a permanent one-session disagreement on every post-20:00-ET execution, which is precisely the shape of the finding this arc is closing. **Two paths reading one fact must read it the same way.**

The residue, stated precisely *(Codex R3 minor — my first phrasing said "13:30Z-01:00Z", which describes the residue as starting an hour late)*: **the divergence begins at 00:00Z**, i.e. 20:00 ET on the previous local date (19:00 ET under EST). A US-equity execution in the 20:00-24:00 ET after-hours block lands on the NEXT UTC date, so both paths would agree on a date one day later than the operator's calendar. Regular US equity hours are 13:30Z-20:00Z (EDT), entirely within one UTC day, and trade 19's own 13:30:05Z is the market open — so the live case is unaffected. **Named as a known limitation with the correct fix stated — convert BOTH sites in one change — rather than fixed on one side here.**

**Gates, in order:**

1. **Pre-review full fast suite to GREEN** (recipe §2 — before Codex, not after).
2. **Codex §3 at the `strong` tier** to `NO_NEW_CRITICAL_MAJOR`, all four per-round assertions recorded (model, `model_reasoning_effort: high`, anchored `grep -c '^ERROR'`, `tokens used` footer) **plus a non-empty redirect target**. *(This plan-stage review runs at `fast` per the recipe's writing-plans tier and the dispatch; `strong` is the executing tier.)*
3. **`codex-auto-review` via the cold-audit form** — `codex exec review` is unusable from a worktree (`Not inside a trusted directory`, no `--skip-git-repo-check` on that subcommand). Switch forms; never skip. Report which form ran.
4. **Post-convergence suite + trailer audit filtered on the trailer KEY.**
5. **Orchestrator QA on disk.**
6. **RD merge-blocking** — §5.3's five items.
7. **Operator witness, step-by-step** (his standing preference — one step, wait for his result, then the next):
   - a. `--dry-run` on trade 19: the before/after table, nothing written;
   - b. the live correction; he reads the `reconciliation_corrections` row and the four moved values;
   - c. `swing journal discrepancy resolve 95 ... --force`; he reads the resolution + the recorded bypass marker;
   - d. **a Schwab reconciliation re-run producing no successor finding for trade 19** (§3.6 — the D25 badge-death precedent: witness the silence, do not assert it);
   - e. the trade-detail page and the process-metrics card, so the moved numbers in §5.1 are seen rather than described;
   - f. **the latch panel, before and after** — the latch reader loads CLOSED trades too (§5.1), so "no latch changed" is a thing to SEE, not to assume.

**Convergence attaches to the tree that ships:** any post-verdict change re-runs the loop.

**Pre-migration backup is the operator's, taken before step 7b** — the §4.2 gate fires automatically at v34 → v35, but the gate is a belt, not a substitute for his own copy.

---

## §9 Flagged, not fixed

1. **The exit side carries the identical D31 defect** (`exit_auto_fill.py:695`), with **live evidence** that it fired: fill 40's `schwab_source_value_json` says `exit_date: 2026-08-03` and the operator's `operator_corrected_value_json` says `2026-08-04`. Out of scope (D31 as ruled is the entry side); the fix additionally perturbs `_compute_signature_hash` (`exit_auto_fill.py:713`), which folds `date` into the exit-candidate dedupe key. **Recommend a follow-on arc.**
2. **Operator-supplied SQL identifiers reach an f-string.** `_handle_multi_field_correction` (`reconciliation_auto_correct.py:2098`) passes `--custom-value` keys to `_update_journal_field` (`:1544`), whose own docstring forbids exactly that; `_validate_correction_target` validates values, never names. Single-operator/local, but it is a live contradiction between a contract and its caller.
3. **`reconciliation_render.py`'s docstring said "ten canonical discrepancy type strings" while the enum held eleven** — stale since 18-H.6. Fixed in T3 as a decay edit; recorded because it is the second time a per-type container drifted from the enum without a test noticing.
4. **`trade_events.event_type` has no member for an operator-initiated correction.** T2 uses `reconciliation_auto_correct`, which is the honest available choice but is named for the wrong actor. Widening that CHECK is schema this arc has no authorization for — **naming debt, not a defect.**
5. **The unanchored half of D19 stays open** (§2.3): an entry-date error with no reconciliation finding has no supported correction path. Closing it wants either the §5.3(5) second type or a design for a synthetic finding that does not lie.
6. **Rider 2's attribution chain is carried, not designed** (§7), with the corrected hop-1/hop-2 framing attached.
7. **Persisted `daily_management_records` MFE/MAE are not re-derived** (§5.2). After the correction the process card's `mfe_R`/`mae_R` for trade 19 remain measured from a window anchored on a date the ledger no longer claims. Correct for V1 — those rows are dated observations, not derived values — but it is a real residue, and re-deriving historical snapshots is a separate arc.
8. **Harness observation, for CHARC — the `tokens used` footer assertion needs the same anchor the ERROR grep got.** Polling this round's output with a bare `grep -q "tokens used"` returned TRUE within ten seconds of launch, while the round had ~210 seconds left to run: the phrase appears in `CLAUDE.md`'s own line 3 (which Codex echoes when it reads the repo) **and in this plan's §8**, because both document the assertion. That is the identical false-positive mechanism CLAUDE.md already records for `grep -c ERROR` → 5-on-a-clean-round, arriving one layer up at the *completion* check rather than the *error* check — and it is worse there, because a false-positive footer invites reading a transcript that is still being written, which is exactly the truncation window the footer exists to close. The anchored form (`grep -E '^tokens used'`) reads correctly. Recorded, not self-applied: the recipe is CHARC-owned.
9. **Composition risk with wave item 6 (D32).** D32 defaults *"the arc-mirror pre-migration backup destination to the BACKUPS directory."* T3 adds a new backup gate whose `backup_dir=None` default resolves to `src_path.parent`. If both land, the merge-integration step is where the composition is caught — **name it as a gate, not mechanics** (harness-architecture §5.1; three composition-class instances in Phase 21).

---

## §10 Files touched, with justification

**`swing/data/` and `swing/trades/` carve-outs are in scope for this arc** (commissioning brief §5 + dispatch brief §4) — unavoidably, since it is a ledger correction plus a migration. Every file, and why:

| file | change | justification |
|---|---|---|
| `swing/data/migrations/0035_*.sql` | NEW | the A-4 CHECK widening; table rebuild per `0031`. |
| `swing/data/db.py` | `EXPECTED_SCHEMA_VERSION`, backup gate + creator + expected-tables set + registration, migration comment | a migration without its backup gate is an ungated schema jump. |
| `swing/data/models.py` | `_DISCREPANCY_TYPES` + 1 | #11; without it every READ of the new row raises. |
| `swing/data/repos/trades.py` | NEW `update_entry_date_fields` | the only place a `trades` UPDATE belongs; modelled on `update_entry_intent`; closed field enum. |
| `swing/data/repos/watchlist.py` (or the module owning `watchlist_archive` writes) | NEW narrow `update_archive_removed_date`, exactly-one-match-or-refuse | the fourth `entry_date` fan-out (§2.5) carries the same defective value; the exclusion in an earlier draft rested on a false claim. |
| `swing/trades/reconciliation.py` | `DISCREPANCY_TYPES` + 1, `MATERIAL_BY_TYPE` + 1, the `:41-45` comment | #11. |
| `swing/trades/schwab_reconciliation.py` | D1 emit type; D2 comment | A-4's substance. |
| `swing/trades/reconciliation_render.py` | D4 pair-builder + stale docstring | the new type renders as itself. |
| `swing/trades/entry_auto_fill.py` | D31 (T1) | the defect's actual site (§1.2). |
| `swing/trades/entry_date_correction.py` | NEW | the correction service; own module so the tx contract is unambiguous. |
| `swing/integrations/schwab/mappers.py` | rider 1 skip accumulator, **both** silent branches (`:294`, `:303`) (T4) | additive keyword, default-`None`, callers byte-identical. |
| `swing/integrations/schwab/trader.py` | `functools.partial`-bound accumulator at **both** `mapper=` sites (`:374` `get_account_orders`, `:431` `get_account_orders_audited`) + an optional `skips` out-parameter on each wrapper | `_call_endpoint:660` calls `mapper(payload)` positionally, so the accumulator must ride in a closure; **`_call_endpoint` itself is NOT modified** (shared by every Schwab endpoint). |
| `swing/integrations/schwab/pipeline_steps.py` (**Pass 1 — the actual caller**, `:523`) | allocate the accumulator, pass it to `get_account_orders`, fold a non-empty result into the step warning envelope | #27 — a skip must reach an audit surface. `schwab_reconciliation.py` never calls `get_account_orders`; wiring it there would have left the rider inert on the nightly path. |
| `swing/trades/reconciliation_backfill.py` (Pass 2, `:652`) | 2 new `BackfillSummary` fields (`:170`), the `_pass_2_dispatch` return (`:599`), the `run_backfill` fold, and a rendered line in `format_summary_block` (`:1717`) + the partial-summary path | the backfill is the half the register's false-negative argument is about, and it has NO warning envelope of its own — a counter nobody prints is a quieter silence, not a fix. |
| `swing/web/view_models/reconcile.py` | D5 renderer | the resolve surface names both sides. |
| `swing/cli.py` | the new command | the operator's entry point. |
| `tests/data/test_phase9_reconciliation_schema_verification.py:299-317` (**R9**) | loop derived from `DISCREPANCY_TYPES`; stale "All 10" docstring corrected | an ACCEPTANCE test that hard-codes the list narrows silently on every widening and NEVER goes red. |
| `tests/data/` — the R8 head-pin set (25 at authoring; **re-derived at execution**) | `34` → `35`, edited by reading each hit | a schema bump reds every head assertion; `test_migration_0017.py:88`'s `len(cols) == 34` is a column count and must NOT be touched. |
| `tests/data/test_no_schema_change_v3.py` | head + ceiling both → 35, comment inventory gains 0035 | a HEAD-tracking guard, updated only because the migration is authorized. |
| `tests/trades/test_entry_auto_fill.py` | the four §8.1 cases | the existing fixtures set `time=enter_time` and cannot distinguish the fix. |
| `tests/**` (remaining) | the enum count pin, the A-4 round-trip + the three D4/D5 dispatch assertions, the legacy-shape classify-skip test (raw-INSERT planted), the correction-service tests (including the archive zero/one/multi trio, the active-state both-branches pair, the server-derived-date mismatch refusal, and the after-hours non-session refusal), both-modes rider tests | — |

**NOT touched:** `swing/web/routes/reconcile.py` (D6 is a deliberate non-change), `swing/trades/reconciliation_classifier.py` (D3), `swing/trades/exit_auto_fill.py` (§9.1).

**Frozen-clock convention binds every new date-touching test** — this arc is entirely about dates, and a live-clock test here is a false green waiting for a DST boundary.
