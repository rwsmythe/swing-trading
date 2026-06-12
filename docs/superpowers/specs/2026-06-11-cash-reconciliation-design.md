# Phase 16 / Arc 4 (4b+4c) — Routine Cash Reconciliation + Equity Coherence: Design Spec

**Date:** 2026-06-11 · **Cycle:** copowers:brainstorming (LOCKED on operator approval + Codex convergence)
**Brief:** `docs/arc4-cash-reconciliation-brainstorming-dispatch-brief.md` · **Investigation:** `docs/phase16-todo.md` §Arc 4
**Branch-from:** main `ca739672` · **Schema:** migration at executing-branch time (expect `0029`, v28→v29)

---

## 1. Mandate

Make the journal cash ledger UNABLE to silently drift from the broker: (4b) routine auto-ingestion
of Schwab cash transactions into `cash_movements` + a real ledger-vs-NLV equity-coherence check
with tolerance + surfacing; (4c) the cash-vs-NLV `basis` discriminator on `account_equity_snapshots`,
the `kind` vocabulary widening (interest/dividend/fee), and the `cash_movements` date normalization —
under the project's reconciliation philosophy (append-only audit, tiered corrections, sandbox
containment).

## 2. Grounding corrections to the dispatch brief (verified against code + live DB, 2026-06-11)

The brainstorm grounding pass OVERTURNED four load-bearing claims in the brief. These corrections
are themselves part of the locked design record:

1. **The Schwab transactions wrapper ALREADY EXISTS.** `get_account_transactions`
   (`swing/integrations/schwab/trader.py:437`, audit label `accounts.transactions.list`) is called
   NIGHTLY by `_step_schwab_orders` (`swing/integrations/schwab/pipeline_steps.py:531`) with all 15
   `TRANSACTION_TYPES_ALL` types over the configured 30-day lookback (`user-config.toml
   lookback_days = 30`). The brief's "no wrapper exists" claim grepped `client.py`; the wrapper
   lives in `trader.py`. **Consequence: NO new Schwab REST endpoint is needed — see §10 (L2).**
2. **The systemic gap is the match DIRECTION, not missing machinery.** The nightly
   `cash_movement_mismatch` scan (`swing/trades/schwab_reconciliation.py:1040-1107`) is
   journal→source only; the source-without-journal direction (the missing-deposit class) is the
   explicitly deferred "V2 widening" (code comment at :1046-1049). This spec builds that widening.
3. **Exact-date matching is brittle — live evidence.** Reconciliation runs 48/49 emitted
   `cash_movement_mismatch` (discrepancies 66/67, both `pending_ambiguity_resolution`) for the
   operator's own 4a fix row (`2026-05-28` $100 deposit): the journal row found NO match among the
   22 Schwab transactions in-period because `tx.transaction_date != cm.date` requires exact
   equality and Schwab books the transfer on a neighboring date. The two pendings sat unnoticed —
   surfaced only via the account-snapshot-page banner.
4. **The existing `equity_delta` check is blind to ledger drift.** It compares
   `get_latest_snapshot_on_or_before(period_end)` (now nightly broker NLV) against fresh broker
   NLV — broker-vs-broker, delta ≈ 0 by construction. (The 4 historical `equity_delta` rows date
   from the manual-snapshot era.) The journal-computed `current_equity` is compared against the
   broker NOWHERE today.

Additional live-DB facts the design depends on (Codex MUST re-verify against the live DB —
the shadow-engine lesson, memory `feedback_adversarial_review_verify_data_shapes`):

- `cash_movements` = 4 rows: rows 1-3 dated `M/D/YY` (`3/30/26`, `4/29/26`, `5/10/26`) with Schwab
  transactionIds in `ref` (row 1's ref carries a stray leading quote: `"115520131470`); row 4
  (`2026-05-28`, $100 deposit) is ISO with `ref=NULL` (manual 4a entry).
- The `M/D/YY` rows are LEXICALLY INCOMPARABLE with the ISO period bounds in the in-period filter
  (`period_start <= cm.date <= period_end`, string comparison) — they are permanently invisible to
  reconciliation until normalized.
- `account_equity_snapshots` = 22 rows (19 `schwab_api` = NLV from
  `currentBalances.liquidationValue`; 3 `manual` from the early era). Schema v28
  (`schema_version` table; `PRAGMA user_version` is unused/0).
- `swing/data/repos/cash.py:find_by_ref` exists (the ref-dedup primitive).
- The discrepancy CHECK vocabulary already contains `cash_movement_mismatch` + `equity_delta`;
  resolution vocabulary contains `auto_corrected_from_schwab` + `pending_ambiguity_resolution`.
  **No discrepancy-vocabulary migration is needed.**
- schwabdev v3 `Client.transactions` signature (pinned live via `inspect.signature`):
  `(accountHash: str, startDate: datetime|str, endDate: datetime|str, types: str, symbol: str|None = None)`.
  The existing wrapper + its signature-pin tests already cover it; no wrapper change.

## 3. Resolved operator questions (binding)

| OQ | Decision (operator, 2026-06-11) |
|---|---|
| OQ-1 ingestion posture | **Auto-ingest ALL cash types** (deposits, withdrawals, interest, dividends; fees per §4 table). Idempotent by transactionId-in-`ref`, append-only, provenance in `note`. |
| OQ-2 cadence + surfacing | Cadence = the EXISTING nightly `_step_schwab_orders` (no new step). Surfacing = **#27 warnings_json + pipeline.log every run, plus a dashboard ACCOUNT-tile badge** for pendings/coherence breaches, linking to the reconcile surface. No new CLI writer in V1. |
| OQ-3 equity coherence | **Ledger primary + NLV alongside** on the ACCOUNT tile; coherence check tolerance `max($5, 0.5% of NLV)`; full-strength check ONLY at zero open trades (§6). Sizing denominator + risk floor untouched. |
| OQ-4 discriminator | **`basis` column** on `account_equity_snapshots` (`'net_liq'`/`'cash'`), **backfill ALL 22 existing rows `'net_liq'`** (schwab_api rows definitionally NLV; the 3 manual rows were account-value readings). |
| OQ-5 date normalization | **Normalize + CHECK + validator**: migration normalizes rows 1-3 to ISO + strips row 1's stray-quote ref (the one-time sanctioned UPDATE-in-place); ISO `date` CHECK in the table rebuild; `__post_init__` + CLI validation mirror it (#11). |
| OQ-6 kind vocabulary | **Five kinds: `deposit`/`withdraw`/`interest`/`dividend`/`fee`.** interest+dividend ADD to net cash; fee SUBTRACTS; amounts stay `>= 0` with kind carrying direction. The `net_cash_movements` wiring lands in the SAME task as the CHECK widening. |
| OQ-7 NOT list | Confirmed as briefed (§11). |
| Match window | **±4 calendar days** for the no-ref fallback match AND the existing journal→source matcher (one shared predicate). Primary dedup = transactionId exact. Ambiguity (2+ candidates) → tier-2 flag, never a guess. |
| Architecture | **Ingest phase INSIDE `run_schwab_reconciliation`'s existing BEGIN IMMEDIATE transaction**, before the journal→source scan — the "V2 widening" the code anticipated. One atomic transaction, one run row, sandbox containment inherited. |

## 4. Ingestion design (4b core)

### 4.1 Classification table

A pure function (no DB, no Schwab calls — the Phase-12 classifier discipline) in
`swing/trades/schwab_reconciliation.py` maps each `SchwabTransactionResponse` to a disposition:

| Schwab `type` | Disposition |
|---|---|
| `ACH_RECEIPT`, `WIRE_IN`, `CASH_RECEIPT` | candidate `kind='deposit'` |
| `ACH_DISBURSEMENT`, `WIRE_OUT`, `CASH_DISBURSEMENT` | candidate `kind='withdraw'` |
| `ELECTRONIC_FUND`, `JOURNAL` | sign of `net_amount`: > 0 → `deposit`; < 0 → `withdraw`; == 0 → skip (zero-amount is not a cash movement) |
| `DIVIDEND_OR_INTEREST` | description-keyed: dividend-marker substring → `dividend`; interest-marker substring → `interest`; **unrecognized description → tier-2 flag (never guess)**; `net_amount < 0` (reversal/fee-shaped) → tier-2 flag |
| `TRADE`, `RECEIVE_AND_DELIVER` | **skip — BY DESIGN.** Trade cash effects already enter the ledger via realized P&L from fills; ingesting them would double-count. |
| `MEMORANDUM`, `MARGIN_CALL`, `MONEY_MARKET`, `SMA_ADJUSTMENT` | skip; if `net_amount != 0`, emit one `warnings_json` note (visibility without guessing) |

The description marker lists (dividend/interest) are module-level frozensets of UPPERCASED
substrings, matched case-insensitively. **BINDING precondition (Codex R1 minor, elevated):** the
initial markers MUST be derived from real Schwab `DIVIDEND_OR_INTEREST` payload descriptions
captured from the live account (a supervised `swing schwab fetch` inspection during executing) —
NOT invented. If the account history contains NO such transactions yet, the lists ship MINIMAL
(or empty) and every `DIVIDEND_OR_INTEREST` flags tier-2 — the safe default; markers are then
added from the first real flagged payloads. A description matching NEITHER list flags tier-2.

**Standalone fees:** Schwab books most fees inside TRADE net amounts — those stay OUT (documented
as the $0.44-class residual; see §6 tolerance). The `fee` kind exists in the vocabulary (§7) for
operator manual entry and future widening; V1 auto-ingest never writes `kind='fee'` (fee-shaped
transactions flag tier-2 instead).

### 4.2 Dedup ladder (per candidate, in order)

1. **Primary — transactionId:** `find_by_ref(conn, ref=str(transaction_id))` (exact). Hit → already
   ingested/imported; skip silently (counted as `matched_by_ref`).
2. **Fallback — ref-less journal rows** (covers manually-entered rows like live row 4): match among
   journal `cash_movements` rows with `ref IS NULL`, same `kind`, `abs(amount)` equal within the
   existing `price_tolerance` ($0.01), and `date` within **±4 calendar days INCLUSIVE**
   (`abs(journal_date − tx_date) <= 4 days`) of the transaction date — excluding rows already claimed by an earlier candidate THIS run (in-memory claimed-set).
   - Exactly ONE candidate → matched; skip, NO write, **NO ref backfill** (ledger rows are never
     UPDATEd in place — lock §10; the match re-derives each nightly run until the Schwab
     transaction ages out of the 30-day lookback, then naturally stops being evaluated).
     **Accepted tradeoff (Codex R1 minor, operator-posture-consistent):** the manual row never
     acquires a durable broker identity; repeated same-amount events rely on the ±4d window +
     multi-candidate flagging rather than a ref link. Accepted because the exposure window is
     bounded by the lookback, ambiguity always flags rather than guesses, and the alternative
     (runtime UPDATE of ledger rows) breaks the append-only lock.
   - TWO-PLUS candidates → **tier-2 flag** (§4.3), no write.
3. **No match → INSERT** via `insert_cash`:
   - `date` = the mapper's ISO `transaction_date` (already normalized to `YYYY-MM-DD` at the mapper).
   - `kind` = classified kind; `amount` = `abs(net_amount)`.
   - `ref` = `str(transaction_id)` — the idempotency key (next night, rule 1 catches it).
   - `note` = `"auto-ingested from Schwab: {description} [reconciliation run {run_id}]"`
     (description may be None → omit gracefully).

Idempotency is by construction: re-running the same night's reconciliation re-matches by ref and
writes nothing. Append-only is by construction: ingestion only INSERTs.

### 4.3 Tier-2 flags from ingestion

Ambiguous cases (fallback multi-match; unrecognized `DIVIDEND_OR_INTEREST` description; negative
DIVIDEND_OR_INTEREST) emit a `cash_movement_mismatch` discrepancy in the source→journal direction:
`field_name='missing_journal_row'` (a NEW field_name value, NOT a new discrepancy_type — no CHECK
widening needed; `field_name` is un-CHECKed TEXT), `cash_movement_id=NULL`,
`expected_value_json` = the Schwab transaction envelope (transactionId, ISO date, type, net_amount,
redaction-safe description, plus a `flag_reason` string enum:
`'fallback_multi_match' | 'unrecognized_income_description' | 'negative_income_amount'`;
`fallback_multi_match` envelopes ADDITIONALLY carry `candidate_cash_movement_ids` — the list of
matching ref-less journal row ids, consumed by resolve choice (c)),
`actual_value_json` = **exactly `{"matched": null}`** — the sole-key shape is LOAD-BEARING
(Codex R1 Major #2): `_extract_source_payload` maps `{"matched": null}` to `source_payload=None`
ONLY when it is the sole key; any extra key turns it into a mapping and the sub-classifier would
mis-route to `unsupported/stale` instead of tier-2 `schwab_returned_no_match`. The `flag_reason`
therefore lives in the `expected_value_json` envelope, never in `actual_value_json`. A
discriminating test pins the classifier routing (`schwab_returned_no_match`, NOT
`unsupported`) for a source-direction row.

**Within-run dedup key (Codex R2 Major #1):** `_emit`'s default payload-key for rows with both
`fill_id` and `cash_movement_id` NULL is `actual_value_json` — which is now the CONSTANT
`{"matched": null}` for every source-direction row, so two different unmatched Schwab
transactions in one run would collide and only the first would insert. Source-direction emits
therefore use an EXPLICIT dedup key of `(discrepancy_type, field_name, transactionId)` (an
`_emit` dedup-key override or a source-direction emit helper — writing-plans picks the shape).
Discriminating test: two unmatched transactions in one run → two discrepancy rows.

**Resolution path for FK-less rows (Codex R2 Major #2 + R4 Majors #2/#3):** the existing tier-2
resolve handlers call `_resolve_affected_target`, which RAISES when `fill_id`, `trade_id`, and
`cash_movement_id` are all NULL — source-direction pendings would be un-dispositionable through
the promised web/CLI flow. The design adds a no-FK-safe resolution branch for
`field_name='missing_journal_row'` rows with a THREE-choice menu (none touches
`_resolve_affected_target`; all terminal choices are durable via the suppression predicate above):

- (a) **acknowledge/not-a-journal-event** — terminal, no journal mutation; for transactions that
  genuinely should not be in the ledger.
- (b) **record-journal-row** — VERIFYING, not trust-based (Codex R3 Major #2, strengthened per
  R4 Major #3): terminal resolution permitted ONLY when `find_by_ref(transactionId)` returns a
  row AND that row's fields match the envelope: `kind` equals the envelope's determinate kind;
  when the kind is indeterminate (`unrecognized_income_description`), the matched row's kind
  must still be DIRECTION-COMPATIBLE with the envelope (Codex R5 Major #1): positive
  `net_amount` on `DIVIDEND_OR_INTEREST` admits only `{'interest','dividend'}`; negative admits
  only `{'fee','withdraw'}`; the general sign rule is positive → `{'deposit','interest',
  'dividend'}`, negative → `{'withdraw','fee'}`. The operator's classification within the
  admitted set is captured into `resolution_reason`; a direction-incompatible kind REJECTS (no
  override path in V1 — a genuinely contrary case goes through choice (a) with the rationale in
  notes). Additionally `abs(amount − abs(net_amount)) <= $0.01`, and `date` within the shared
  ±4d window of the envelope date. Any
  field mismatch REJECTS with a specific message; a missing row REJECTS with the
  kind-appropriate instructional command (`swing journal cash --<kind-flag> <amt> --date <iso>
  --ref <transactionId>` — NOT hardcoded `--deposit`). The pending stays open until the ledger
  actually carries a verified matching row. V1 does NOT auto-create from the resolve flow.
- (c) **matched-existing-row acknowledge** — the clean disposition for `fallback_multi_match`
  (R4 Major #2): the operator declares the transaction is already represented by an existing
  ref-less journal row, identified via a `requires_custom_value` row-id input that MUST refer to
  one of the candidate rows recorded in the envelope (validated at resolve time: the id is in
  the envelope's candidate list AND the row still exists with matching kind/amount). No journal
  mutation, no duplicate row pressure; the linkage is recorded in `resolution_reason`
  (`matched_existing_cash_movement_id=<id>`); terminal + durable. (The fallback-multi-match
  envelope therefore MUST carry the candidate journal row ids — added to the §4.3 envelope
  contract.)

The choice-menu wiring follows the per-choice `requires_custom_value` discipline; writing-plans
pins the exact `get_choice_menu` additions. Discriminating tests: a `cash_movement_id=NULL`
pending resolves through all three choices without raising; (b) rejects on wrong-amount /
wrong-kind / out-of-window / missing rows; (c) rejects a row id outside the envelope's candidate
list; an acknowledged transactionId neither re-flags NOR auto-ingests on the next run. The writing-plans phase additionally confirms the
classifier's journal_row=None path for `cash_movement_id=NULL` rows and adds a guard if needed.

**Cross-run suppression (Codex R1 Major #4 + R4 Major #1):** the live DB already shows the
re-emission failure (discrepancies 66/67 = the SAME journal row flagged by runs 48 AND 49).
Emit-time suppression predicates:
- source→journal — **pending OR terminal, keyed on transactionId (durable):** skip the emit when
  ANY row exists with `discrepancy_type='cash_movement_mismatch' AND
  field_name='missing_journal_row' AND json_extract(expected_value_json, '$.transactionId') =
  :tx_id AND resolution IN ('pending_ambiguity_resolution', 'operator_resolved_ambiguity',
  'operator_overridden', 'acknowledged_immaterial')`. A terminal disposition of a broker
  transaction is FINAL for that transactionId — an acknowledged not-a-journal-event must not
  re-flag nightly until it ages out (that would make the terminal choice non-terminal in
  practice). The dedup ladder ALSO consults this suppression BEFORE rule 3 — a terminally
  dispositioned transactionId is never auto-ingested either.
- journal→source — **pending-only, keyed on cash_movement_id:** skip the emit when an OPEN
  pending row exists with `discrepancy_type='cash_movement_mismatch' AND cash_movement_id =
  :cm_id AND resolution='pending_ambiguity_resolution'`. (Terminal re-emission semantics on the
  journal direction are the PRE-EXISTING Phase-12 behavior, unchanged in this arc; the ±4d
  widening removes the live 66/67 class at the matcher level.)
Suppressed emits are COUNTED (`cash_pending_suppressed_count` in the run summary + #27 envelope)
so the run record still shows the condition persists.

### 4.4 Placement + transaction semantics

The ingest phase runs INSIDE `run_schwab_reconciliation`, as a new step **6.5** (after fill
matching, BEFORE the existing step-7 journal→source cash scan), within the same `BEGIN IMMEDIATE`:

- The journal cash list is RE-READ (or appended in-memory) after ingestion so step 7 scans the
  updated ledger — freshly-ingested rows match their own source transaction by ref and emit nothing.
- Failure semantics inherit the run's existing contract (partial-preserving `state='failed'` UPDATE).
- The run summary (`summary_json`) gains: `cash_ingested_count`, `cash_matched_by_ref_count`,
  `cash_matched_by_fallback_count`, `cash_flagged_count`, `cash_skipped_trade_count`,
  `cash_pending_suppressed_count` (Codex R2 minor #1 — the §4.3 suppression counter is part of
  the canonical list).
- `run_schwab_reconciliation` is invoked by `_step_schwab_orders` ONLY under
  `environment == 'production'` — **sandbox containment (audit rows only) is inherited by
  construction**; no new gate code.

### 4.5 Coverage guarantee + the lookback boundary (Codex R1 Major #3)

The ingestion guarantee is explicitly **"no silent drift WITHIN fetched lookback coverage"** —
a broker transaction can age out of the 30-day window if the pipeline doesn't run (auth broken,
machine off, Schwab outage) for longer than `lookback_days`. Two compensating controls make the
out-of-window case LOUD rather than silent:

1. **Coverage-gap warning:** at ingest time, read the most-recent COMPLETED `schwab_api`
   reconciliation run's `period_end` (the two-read `pipeline_runs` pattern analog); if it is
   OLDER than the current run's `period_start`, a window of transactions was never scanned —
   emit a `warnings_json` entry + pipeline.log WARN naming the uncovered span
   (`coverage_gap: <prev_period_end> .. <period_start>`). First-ever run (no prior completed
   run) emits an informational note, not a warning.
2. **The §6 equity-coherence check is the out-of-window backstop:** any cash the ingest never
   saw eventually surfaces as ledger≠NLV on the next flat night (badge + discrepancy).

V1 does NOT auto-widen the fetch window on gap detection (the schwabdev endpoint supports up to
1 year; a manual catch-up is `lookback_days` bump + the on-demand CLI fetch — an operator
runbook note, not code).

## 5. Journal→source matcher fix (the brittleness)

The existing step-7 scan's exact-date predicate (`tx.transaction_date != cm.date`,
schwab_reconciliation.py:1079) widens to the same **±4 calendar days** via ONE shared date-window
predicate helper used by BOTH directions (the Arc-6 `_full_refresh_due` shared-predicate lesson:
two implementations WILL diverge). Kind→type-set mapping extends to the new kinds:
`interest`/`dividend` → `{DIVIDEND_OR_INTEREST}` (sign > 0), `fee` → `{DIVIDEND_OR_INTEREST}`
(sign < 0) — so operator-entered income/fee rows can match their broker counterparts.

**The two live stale pendings** (discrepancies 66/67): the operator dispositions them ONCE via the
existing web tier-2 resolve flow. They are real audit history — no bulk edit, no migration touch.
After the ±4d widening ships, the 2026-05-28 row matches its Schwab transaction and no new
mismatch is emitted for it.

## 6. Equity coherence (4b) + the ACCOUNT tile

### 6.1 The check

Inside `run_schwab_reconciliation` (same transaction, after ingestion so the ledger is current):

- `ledger_equity = current_equity(starting_equity=cfg.account.starting_equity, exits=<fills-adapter>, cash_movements=list_cash(conn))`
  — the SAME function + inputs the dashboard tile uses (`swing/trades/equity.py:current_equity`;
  the exits adapter mirrors the dashboard's fills-sourced `_list_all_exitshape_via_fills` shape —
  the writing-plans phase lifts/shares that adapter rather than duplicating it).
- Compare against the FRESH `schwab_account.net_liquidating_value` from the same step (NOT the
  stale snapshot — this REPLACES the broker-vs-broker compare; `journal_equity` sourced from
  `get_latest_snapshot_on_or_before` is dropped from the equity_delta path).
- **Flat-state gate (Codex R1 Major #5):** the full-strength check requires BOTH zero journal
  open trades AND an empty broker positions list (read from the SAME `schwab_account` payload the
  step already fetched — the field the `position_qty_mismatch` scan consumes; writing-plans pins
  the exact attribute). A broker-only orphan position would otherwise pollute NLV with unrealized
  P&L and misclassify a position problem as cash drift. When journal-flat but broker-positions
  non-empty, the check is suppressed AND a `warnings_json` note records the orphan-position
  condition (it is itself a reconciliation smell).
- **Flat (both sides):** `|ledger − NLV| > max($5.00, 0.5% × NLV)` → emit `equity_delta` discrepancy
  (`expected_value_json` = `{"equity_dollars": ledger, "basis": "ledger"}`, `actual_value_json` =
  `{"equity_dollars": nlv, "basis": "net_liq"}`, delta_text unchanged format). The existing
  `EQUITY_DELTA_EMIT_THRESHOLD_DOLLARS` constant is superseded by the new tolerance function.
- **Not flat (open journal trades, or broker positions present):** NO discrepancy, NO badge — the
  spread includes unrealized P&L and is not cleanly attributable (operator-confirmed; no
  position-level decomposition in V1). Auto-ingest guards the drift class during holding periods;
  the check re-arms on the next flat night.

### 6.2 The tile

`DashboardVM`/ACCOUNT tile (dashboard.py + template):

- Headline: ledger `current_equity` (UNCHANGED formula — `starting + realized + net cash`, with
  net cash now 5-kind per §7).
- Secondary line: latest `account_equity_snapshots` row with `basis='net_liq'` —
  "Schwab NLV $X,XXX.XX (MM-DD)". Renders "no snapshot" state gracefully.
- Badge: renders when EITHER exact predicate holds (Codex R1 Major #6 — the state set is pinned,
  not prose):
  1. `SELECT COUNT(*) FROM reconciliation_discrepancies WHERE discrepancy_type =
     'cash_movement_mismatch' AND resolution = 'pending_ambiguity_resolution'` > 0 (any run —
     a pending stays visible until dispositioned), OR
  2. the MOST-RECENT completed (`state='completed'`) `source='schwab_api'` reconciliation run has
     `SELECT COUNT(*) FROM reconciliation_discrepancies WHERE run_id = :latest_run_id AND
     discrepancy_type = 'equity_delta' AND resolution = 'unresolved'` > 0 — i.e., exactly the
     `'unresolved'` state; `acknowledged_immaterial` and every operator-resolved state CLEAR the
     badge, and older runs' deltas never re-trigger it.
  Links to the reconcile surface. Computed at render time from the DB (no schema; no new VM-wide
  field on OTHER base-layout VMs — the badge is a DashboardVM-only field, so the `base.html.j2`
  shared-VM gotcha is NOT triggered; the writing-plans phase verifies placement stays inside the
  dashboard-only template region).
  **Intentionally OFF the badge (Codex R2 minor #2, accepted):** the §6.1 orphan-position
  suppression warning surfaces in `warnings_json` + pipeline.log only — it is a
  position-reconciliation smell, not a cash-coherence breach, and broker-positions-without-any-
  journal-trade is an exotic state for this single-operator account; promoting it to a tile badge
  is deferred until it ever fires in practice.
- Sizing denominator (`resolve_live_capital_denominator_dollars`) + the `max($7500, actual)` floor:
  **untouched** (the resolver additionally filters `basis='net_liq'` per §7.2 — semantics identical
  today since all rows are net_liq).

## 7. Schema — migration 0029 (v28→v29) + the #11 sweep (4c)

Numbered at executing-branch time (expect `0029_cash_reconciliation.sql`). In-file `BEGIN;` …
`COMMIT;` + in-file version bump (#9 — `executescript` autocommit). Strict-equality backup gate
`pre_version == 28` (the Phase-9 clause shape). Migrate-twice no-op test. DB-outside-Drive invariant
unchanged.

### 7.1 `cash_movements` — 12-step rebuild

CHECK changes require a rebuild (SQLite cannot ALTER a CHECK):

```sql
CREATE TABLE cash_movements_new (
  id INTEGER PRIMARY KEY,
  date TEXT NOT NULL CHECK (date GLOB '[0-9][0-9][0-9][0-9]-[0-9][0-9]-[0-9][0-9]'),
  kind TEXT NOT NULL CHECK (kind IN ('deposit','withdraw','interest','dividend','fee')),
  amount REAL NOT NULL CHECK (amount >= 0),
  ref TEXT,
  note TEXT
);
```

The copy normalizes IN TRANSIT (the one-time sanctioned data fix; ids preserved by explicit-column
copy so the `reconciliation_discrepancies.cash_movement_id` FK survives — the migration runner
holds `foreign_keys=OFF`):

- Date: `M/D/YY` and `MM/DD/YY` forms → ISO via CASE/substr logic pinned to the three known rows'
  shapes, with a defensive general transform (the writing-plans phase writes the exact SQL; the
  spec pins the EXPECTED post-states: row 1 `2026-03-30`, row 2 `2026-04-29`, row 3 `2026-05-10`,
  row 4 unchanged `2026-05-28`).
- Ref: strip a single leading `"` (row 1: `"115520131470` → `115520131470`); other refs unchanged.
- A migration-internal sanity SELECT asserts zero rows violating the new date GLOB before the
  rename-swap (defense against an unexpected fifth row shape on some future DB).
- **Index recreation is an explicit post-rename step (Codex R1 Major #1):** migration `0003`
  created `CREATE UNIQUE INDEX ux_cash_ref ON cash_movements(ref) WHERE ref IS NOT NULL`
  (0003:85) — the rebuild MUST recreate it verbatim, and a test asserts both its existence
  post-migration AND that a duplicate-ref INSERT raises `IntegrityError`. The partial unique
  index is the DB-level idempotency belt under the §4.2 ref-dedup ladder.

### 7.2 `account_equity_snapshots` — basis column

```sql
ALTER TABLE account_equity_snapshots
  ADD COLUMN basis TEXT NOT NULL DEFAULT 'net_liq'
  CHECK (basis IN ('net_liq','cash'));
```

The DEFAULT backfills all 22 existing rows `'net_liq'` (operator-confirmed for the 3 manual rows).
New writers must stamp basis explicitly (the model validator makes it required; the SQL DEFAULT is
the migration-backfill vehicle, not a writer crutch).

**Uniqueness model widens with the discriminator (Codex R3 Major #1):** the existing
`ux_account_equity_snapshots_date_source` on `(snapshot_date, source)` (0017:339) would forbid
storing a `net_liq` AND a `cash` snapshot for the same date/source — defeating the
discriminator's purpose. The migration DROPs and recreates it as
`ux_account_equity_snapshots_date_source_basis` on `(snapshot_date, source, basis)` (index-only
change, no table rebuild), and `repos/account_equity_snapshots.py:upsert_snapshot`'s conflict
key widens to match in the same task. All V1 writers stamp `'net_liq'`, so behavior is identical
on current data; a future cash-basis writer slots in without schema work. Reads that must be
NLV-only (`equity_resolver`, the §6.2 tile line, the reconciliation's snapshot read) filter
`basis='net_liq'` explicitly. Test: same-date `net_liq` + `cash` rows coexist; same-date
same-basis upsert still replaces.

### 7.3 The #11 sweep (CHECK + constant + validator in ONE task, every mirror)

| Mirror | Change |
|---|---|
| `reconciliation_validators._CASH_MOVEMENT_KINDS` | → 5-kind tuple |
| `swing/data/models.py:CashMovement` | add `__post_init__`: kind ∈ frozenset(5), date matches ISO shape (`Literal`/comment hints are not runtime-enforced) |
| `swing/trades/equity.py:net_cash_movements` | `deposit`/`interest`/`dividend` ADD; `withdraw`/`fee` SUBTRACT; **unknown kind now raises** (today's silent-ignore is the drift hazard) — SAME task as the CHECK widening |
| `swing/cli.py journal cash` | `--interest` / `--dividend` / `--fee` options (exactly-one-of with the existing pair); ISO date validation (reject non-`YYYY-MM-DD` with a clear ClickException) |
| `schwab_reconciliation` kind→type-set mapping | extended per §5 |
| `swing/data/models.py:AccountEquitySnapshot` | `basis` field + `__post_init__` ∈ {'net_liq','cash'} |
| `swing/data/repos/account_equity_snapshots.py` | INSERT column list + `_row_to_*` widened in the SAME task (schema-version-aware fixtures bumped) |
| Snapshot writers (pipeline `_step_schwab_snapshot` mapper path, web manual form, tos_csv path) | stamp `basis='net_liq'` explicitly (all three sources are account-value readings today) |
| `swing/metrics/equity_resolver.py` | the denominator read filters `basis='net_liq'` (definitionally NLV; behavior identical on current data) |

A grep-sweep task in writing-plans enumerates ALL hardcoded `('deposit','withdraw')` copies across
`swing/` + `tests/` (the #11 multiple-Python-mirrors discipline) and audits each as
manual-input-allowlist vs service-wide.

## 8. Audit + surfacing

- **#27 plumbing (Codex R2 Major #3):** the pipeline runner owns `run_warnings` and persists it
  via `lease.release(warnings_json=...)`; `_step_schwab_orders` currently has NO warnings channel
  and the runner ignores its return dict. The step's result dict gains a `warnings` list; the
  runner's `_step_schwab_orders` call site appends those entries to `run_warnings` (the
  established #27 pattern). `swing/pipeline/runner.py` is added to the touched-surfaces list
  (§10) for exactly this plumbing. Test: a run with cash activity persists the entries into
  `pipeline_runs.warnings_json` end-to-end.
- **#27 discipline:** the ingest phase emits a `warnings_json` entry EVERY run — when work
  happened: `cash_ingested_count` + per-row `(date, kind, amount)` (NO descriptions in
  warnings_json — they can carry bank-account prose; full detail lives in the discrepancy
  envelopes + pipeline.log post-redaction); when zero work: the expected-vs-actual envelope
  (`transactions_checked`, `candidates`, `matched_by_ref`, `matched_by_fallback`, `ingested`,
  `flagged`, `skipped_trade`) so a silent no-op is distinguishable from a dead path.
- **pipeline.log:** one INFO summary line mirroring the counters (rides the Arc-1/Arc-2 logging
  seam; redaction is already installed on that surface — descriptions in log lines pass through
  the two-belt redactor).
- **Dashboard badge:** per §6.2.
- **Existing surfaces:** the account-page banner + reconcile pages continue to work (the tier-2
  resolve flow is reused as-is; `_render_pre_resolution_context_cash_movement_mismatch` is checked
  in writing-plans for the `cash_movement_id=NULL` source-direction rows and extended if it assumes
  a journal row exists).

## 9. Testing posture (binding directions to writing-plans)

- **Fixtures from REAL emitter output** — `SchwabTransactionResponse` fixtures derived from the
  live mapper's actual emissions (shape: ISO-normalized `transaction_date`, str `transaction_id`,
  float `net_amount`, optional description); ledger fixtures mirror the REAL 4-row state including
  the `M/D/YY` mix and the stray-quote ref (pre-migration tests) — the shadow-engine lesson.
  Codex is explicitly directed to verify the §2 data claims against the live DB.
- **Regression arithmetic verified both ways** (memory `feedback_regression_test_arithmetic`):
  the ±4d matcher test pins the run-48/49 scenario — journal `2026-05-28` vs Schwab tx on a
  neighboring date: pre-fix emits `cash_movement_mismatch`, post-fix matches. The fallback-dedup
  test pins row 4: pre-design auto-ingest would write a duplicate $100 row; the ladder must NOT.
- Discriminators: run-twice idempotency (zero new rows on the second pass); TRADE/RECEIVE_AND_DELIVER
  exclusion (a TRADE with nonzero netAmount must NOT create a row); zero-`net_amount`
  ELECTRONIC_FUND skip; multi-candidate fallback → tier-2 + no write; 5-kind `net_cash_movements`
  arithmetic incl. the unknown-kind raise; migrate-twice no-op; backup-gate strict equality;
  migration data post-states (the §7.1 pinned values) + the GLOB sanity gate; coherence check fires
  at zero open trades / suppressed with an open trade; tile renders both numbers + the badge states;
  snapshot writers stamp basis; resolver filters basis. Round-1 additions: `ux_cash_ref`
  recreated + duplicate-ref INSERT raises; the source-direction classifier routing pin
  (`schwab_returned_no_match`, not `unsupported`); cross-run suppression (source-direction: pending OR
  terminal states durably suppress by transactionId, incl. the no-auto-ingest belt;
  journal-direction: pending-only suppresses by cash_movement_id); the coverage-gap warning
  fires on a synthetic period gap; the flat-state gate (journal-flat + broker-position-present → suppressed + warned).
- Suite baseline 7869 green; ruff clean; the 3 banked `-n0` schwab-route flakes are pre-existing.

## 10. Locks / invariants (held)

- **L2 LOCK: NOT TRIGGERED.** Zero new Schwab REST endpoints. The design reuses
  `get_account_transactions` → `accounts.transactions.list` = row 4 of
  `docs/schwab-v3-endpoint-diff.md`, in the endpoint set since Phase 9 and fetched nightly since
  the Phase-15 wiring. The brief's L2 flag arose from the §2.1 grounding error. No baseline
  re-anchor, no endpoint-diff update needed.
- **Schwab discipline:** no wrapper changes; the existing signature-pin tests, typed
  `SchwabApiError` audit-row close, redaction install, and sandbox→audit-only behavior all
  continue to apply unchanged. No new CLI writer in V1 → no new `SchwabPipelineActiveError`
  surface.
- **`reconciliation_corrections` APPEND-ONLY** — untouched (ingestion INSERTs `cash_movements`
  directly; it is not modeled as a correction).
- **`cash_movements` rows are NEVER UPDATEd in place** except the one-time §7.1 migration
  normalization. No runtime ref backfill (§4.2 rule 2).
- **Risk floor `max($7500, actual)` + denominator resolution semantics intact** (§6.2).
- **Phase-isolation carve-out (spec-scoped):** `swing/trades/schwab_reconciliation.py` (extend) +
  `swing/trades/equity.py` (the `net_cash_movements` 5-kind arithmetic ONLY); `swing/data/`:
  migration `0029` + `models.py` (CashMovement/AccountEquitySnapshot validators) +
  `repos/cash.py` (read helpers if needed) + `repos/account_equity_snapshots.py` (basis column).
  Also touched (non-carve-out surfaces): `swing/integrations/schwab/pipeline_steps.py` (the
  step's `warnings` result-dict channel), `swing/pipeline/runner.py` (the `_step_schwab_orders`
  call-site append into `run_warnings` — the §8 #27 plumbing; Codex R2 Major #3),
  `swing/web/view_models/dashboard.py` + the dashboard template (tile),
  `swing/trades/reconciliation_ambiguity_choices.py` + `swing/trades/reconciliation_auto_correct.py`
  and the web/CLI resolve paths (the no-FK-safe resolve branch + choice menu, per §4.3 —
  real file names per Codex R3 minor #1),
  `swing/cli.py` (kind options), `swing/metrics/equity_resolver.py` (basis filter),
  `swing/trades/reconciliation_validators.py`, `swing/trades/reconciliation_render.py` /
  `swing/web/view_models/reconcile.py` (NULL-cash_movement_id rendering, if needed).
- Conventional commits; zero `Co-Authored-By`; no `--no-verify`.

## 11. What V1 does NOT do (operator-confirmed)

- NO Schwab-statement parsing (the banked since-inception statement ingestion stays banked).
- NO intraday sync — nightly + the existing on-demand `swing schwab fetch` cadence.
- NO position-level NLV decomposition — the coherence check treats spread at the dollar level only
  and only at zero open trades.
- NO auto-ingest of `fee` rows (vocabulary present; auto-write deferred — fee-shaped transactions
  flag tier-2).
- NO trade/fill reconciliation changes (Phase 12 machinery untouched beyond the §4.3/§8 cash wiring).
- NO risk-policy change; NO Arc 9 content.
- NO ref backfill onto existing ledger rows (matching re-derives nightly within the lookback).

## 12. Open items deferred to writing-plans

- Exact migration SQL (rebuild steps, the date-CASE transform, the GLOB sanity gate).
- The dividend/interest description-marker frozensets (derived from real Schwab payload
  descriptions — possibly via one supervised live `swing schwab fetch` inspection).
- The shared exits-adapter lift for §6.1 (reuse vs extract of `_list_all_exitshape_via_fills`).
- Classifier/render-path NULL-`cash_movement_id` handling confirmation (§4.3, §8).
- The `equity_delta` render/pairs path (`reconciliation_render.py`) tolerance of the new
  `basis` keys in the §6.1 envelopes (additive keys; confirm no strict-shape parse breaks).
- The #11 grep-sweep inventory of `('deposit','withdraw')` hardcodes.
- Task decomposition + TDD sequencing.
