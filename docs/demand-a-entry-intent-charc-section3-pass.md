# DEMAND A — §3 architecture pass (CHARC), `entry_intent` third value

**Verdict: GO on the schema tripwire, with ONE finding that changes the design and must be
resolved by RD before dispatch.** The operator concurred on the value name `unintended_execution`
2026-08-12. This pass verified every claim below against the code and the live DB rather than
against the design conversation; where a fact came from a colleague's account it is marked.

---

## 1. WHAT IS BEING NAMED — corrected from the row itself

Both directors were carrying a secondhand characterization ("an operator-initiated entry outside
the mandate"). **Trade 20's own record contradicts it:**

- `notes` — *"Stale A+ latch order fired after A+ condition disappeared. This happened as we were
  working on the latch removal code."*
- `why_now` — *"Accidental entry while working on latch/unlatch mechanism."*
- `thesis` — *"Old A+ setup, high likelihood of loss"* · `emotional_state_pre_trade` — `["distracted"]`

**It is not discretionary and not off-mandate-by-choice. It is an entry NOBODY DECIDED TO MAKE,
produced by a mechanism that outlived its own premise while that mechanism was being repaired.**
`trade_origin = 'manual_off_pipeline'` makes "manual" or "discretionary" look correct from the
column alone — which is why the wrong name would have survived review.

**Naming consequence:** the value names the CLASS (an execution nobody intended), not the
MECHANISM (`stale_order_fill` would describe this instance and under-cover the next). It must also
be unmistakable from `NULL`, which means *not yet classified* — `unintended_execution` asserts;
`no_intent`/`unclassified` would read as an absence and get conflated.

## 2. THE TRIPWIRE — schema, and it is a `trades` TABLE REBUILD

SQLite cannot ALTER a CHECK. Widening `entry_intent` requires the `_new` + INSERT-SELECT + DROP +
RENAME pattern. **The precedent named in prior planning notes is 0031, and that citation needs
qualifying: 0031 rebuilds `reconciliation_discrepancies`, NOT `trades`.** The PATTERN transfers;
the BLAST RADIUS does not. Measured on the live DB:

| | `trades` |
|---|---|
| columns | **57** |
| CHECK constraints | **13** — every one must survive verbatim |
| indexes | 3, incl. the **UNIQUE partial** `ux_trades_one_open_per_ticker` |
| child tables with FKs REFERENCING it | **4** — `fills`, `daily_management_records`, `trade_events`, `reconciliation_discrepancies` |

**This is the D30 class by construction** (a paired CHECK nearly lost in 0033's rebuild). Required:
explicit `BEGIN`/`COMMIT` per gotcha #9; the runner's `foreign_keys=OFF` is what prevents the child
tables cascading on the DROP, so a **`PRAGMA foreign_key_check` after RENAME is mandatory, not
optional**; and the accept must diff pre/post `sqlite_master` DDL for `trades` and show the ONLY
delta is the one enum token.

## 3. WHAT IS SAFE BY CONSTRUCTION — the finding that de-risks the arc

I expected the contamination hazard to be a silent `else`-branch coercing an unknown intent into
`standard`. **It is not there. The codebase is already shaped defensively against exactly this
widening:**

- **`swing/metrics/cohort_intent.py` partitions by POSITIVE ALLOWLIST** (`entry_intent = 'standard'`
  for H1), and documents NULL as *"a DISTINCT third facet ... never coerced to 'standard'."* **A new
  value therefore lands in NO cohort automatically. No cohort code changes.**
- **`swing/data/models.py:356` raises `ValueError`** against the `ENTRY_INTENTS` frozenset — loud,
  and explicitly written to mirror the 0027 CHECK.
- **Both display maps default CONSERVATIVELY.** `process_grade_trend.py:561` is
  `.get(intent, "unclassified")` — an unmapped value renders as *unclassified*, never as *standard*.
  `intent.py:34` is `.get(value, value)` — renders the raw token: ugly, but visible and
  self-announcing rather than silently mislabelled.

**Consequence for scope: the arc is a migration plus a mirror sweep. It is not a cohort-semantics
change**, and any brief claiming otherwise has widened it.

## 4. THE MIRROR MANIFEST — all six land in ONE commit (#11)

Established by READING each site, not by a token grep (a grep bounds the family from below):

1. `swing/data/migrations/00XX_*.sql` — the CHECK, via table rebuild
2. `swing/data/models.py:243` — `ENTRY_INTENTS` frozenset
3. `swing/trades/intent.py:17` — `ENTRY_INTENT_DISPLAY` tuple (feeds `_ENTRY_INTENT_LABELS`)
4. `swing/web/view_models/metrics/process_grade_trend.py:78` — `_INTENT_CSS_CLASS` (**needs a CSS
   class to exist for the new token, or it silently inherits the unclassified style**)
5. `swing/web/view_models/metrics/trade_process_card.py:52` — the filter-option tuple
6. `swing/cli.py` — **3 sites**, `click.Choice` lists

`swing/trades/intent.py:54` (`by_design_keywords` inference) is deliberately NOT extended — the new
value is never INFERRED from text, only asserted with evidence. See §5.

## 5. THE FINDING THAT CHANGES THE DESIGN — the admission rule I proposed is UNREACHABLE for the first instance

I recommended to the operator that `unintended_execution` require a **structural citation to the
mechanism that fired** — the `latch_order_intents` row — on the reasoning that a discretionary trade
that went badly is trivially relabelled as "didn't mean to," and would be indistinguishable from
diligence. That reasoning stands. **The mechanism does not.**

**Live check: `latch_order_intents` holds THREE rows — OII (intents 1, 2) and CADL (intent 3). NONE
for AMN. The earliest `recorded_ts` is 2026-08-08T20:01:08; trade 20 entered 2026-08-07.** The
instrument post-dates the event it would have to certify. **A structural-citation rule keyed to that
table makes trade 20 — the only row the demand exists for — unlabelable.**

Two disposals are refused outright: **synthesizing a `latch_order_intents` row for AMN is minting
evidence**, and this project already refused exactly that when item 5 declined to mint a synthetic
discrepancy to carry a correction. Dropping the citation requirement reintroduces the curation risk.

**Proposed shape — RD'S CALL, because it is his evidence rule and it is the same rule Demand C turns
on:** a TWO-TIER admission with **the tier RECORDED on the row**. Structural citation where the
instrument existed; contemporaneous-operator-record attestation where it provably did not, with the
row stating that the instrument post-dates the event. That is the house style already — 0034
preserved the original criterion in a new column rather than overwriting, and the parity ledger
records provenance rather than assuming uniformity.

**The question for RD, posed and not answered here:** his Demand C rule says *"the framework's OWN
CONTEMPORANEOUS RECORD."* Trade 20's `notes` and `why_now` are operator-AUTHORED but
framework-CAPTURED at entry, and they describe the mechanism precisely. **Does operator-authored,
contemporaneously-captured text satisfy a rule written to exclude later judgment?** It is genuinely
contemporaneous and genuinely not framework-derived. **Do NOT lean on `pre_trade_locked_at` as
corroboration — it equals `entry_date + T16:00:00` on 20/20 trades and is a synthetic restatement of
the column it appears to support.**

## 6. DISCRIMINATING TESTS THE BRIEF MUST NAME

- **The one that actually distinguishes:** an `unintended_execution` row is absent from EVERY cohort
  read — computed, not asserted. A test that only proves the value is WRITABLE passes while the row
  contaminates. §3 says the allowlist already prevents this; the test PINS it against a future
  refactor to an `else`-branch.
- Migration applied twice is a no-op; all 13 CHECKs and all 3 indexes present post-rebuild;
  `PRAGMA foreign_key_check` clean; child-table row counts unchanged across the rebuild.
- The model validator REJECTS a fourth unknown value (the frozenset still bites).
- Every display surface renders the new token without falling back to `standard` styling.

## 7. SEQUENCING

**Demand C still goes first.** A's name is now settled but A is gated on RD's evidence-tier ruling
(§5), and A's migration is a 57-column/13-CHECK `trades` rebuild against C's additive surface. C is
buildable today, needs no vocabulary decision, and carries the only external deadline (monthly read
#3, first trading week of September).

**NOT ratification.** The operator concurred on a WORD. §VII.F ratifies SPECIFIC AMENDED TEXT in the
0034 shape — hash-pinned and independently derived — and none exists yet. **No amended text is
implied by this pass.**
