# P0 Tuition-vs-Error (`entry_intent`) — Post-Merge Operator Gate

**Status:** authored by the executing instance at the end of copowers:executing-plans. This is the
binding operator witness list per spec §10.1 (TestClient asserts STRUCTURE only — these are the
browser/CLI observations the operator must make). **Merge is blocked until the operator confirms.**

**Pre-gate (research-director owns, post-merge):**
1. Re-run the full fast suite on the *merged* head (main moved to `0ff853e9` during execution — see the
   return report; the suite was green on the branch base `0f8d4610`). Per `feedback_no_false_green_claim`,
   read the merged-head summary line; do not carry the branch count forward.
2. Apply the live `v26 → v27` migration by touching any write-path (it is backup-gated; the
   `_entry_intent_backup_gate` fires `current==26 AND target>=27` and snapshots
   `swing-pre-entry-intent-migration-<ISO>.db`). Confirm `schema_version == 27`, `entry_intent` column
   present, all 16 trades intact, and the backup file written.

## Operator witness list (spec §10.1)

### 1. Trade-process card intent facet (the core fix)
- Navigate to `/metrics/trade-process`. On the **All** cohort tab, confirm the **intent-facet selector**
  renders (`All / Standard / Hypothesis test (by design) / Unclassified`), server-rendered links carrying
  `?cohort=__all__&intent=<value>`.
- Select **Standard** — confirm the card body (grade distribution, mistake-tag frequency) re-faces to the
  standard-only cohort, isolating real execution quality from the by-design experiments.
- **Honest under-populated states:** with the current tiny cohort, confirm the standard / by-design /
  unclassified facets render truthfully when a facet has few or zero reviewed trades (no fabricated
  fullness — the seeded-gate-masks lesson: witness the *real* sparse state, not a seeded one).
- **Always-on execution-discipline panel:** confirm the panel (risk + reconciliation slips:
  `NO_STOP`, `STOP_NOT_PLACED`, `OVERSIZED`, `SIZE_MISCOUNTED`, etc.) renders, and that its rows +
  denominator are **byte-identical as you toggle the intent facet** (Standard ↔ By-design ↔ Unclassified ↔
  All). A genuine risk/reconciliation slip on a by-design trade (e.g. VIR's `NO_STOP`/`STOP_NOT_PLACED`)
  must stay visible regardless of facet. The entry-category tuition tag `CHASED` must NOT appear in this
  panel. (Route test `test_trade_process_panel_byte_identical_across_intent_facet` asserts the HTML byte-
  identity; the operator confirms the rendered UI matches.)
- Per-cohort hypothesis tabs (non-All) do NOT show the facet selector (D6 — facet only on All).

### 2. PGT per-trade markers (#22 preserved)
- Navigate to `/metrics/process-grade-trend`. In the **GRADES** panel, confirm the per-trade `<circle>`
  markers carry intent-distinct styling (`data-entry-intent="standard|by-design|unclassified"` +
  `intent-<class>` CSS class) and that the legend names `standard / by-design / unclassified` (ASCII).
- Confirm the three panels (grades / rate / cost), the rolling polylines, and the grade-axis encoding
  (`A=4 ... F=0`) are unchanged from the #22 redesign (the 7 rolling series are byte-stable).
- Witness the markers in **both light AND dark mode** (the intent classes must be visually distinct in both).

### 3. Entry + review forms set/correct intent
- New-trade entry form: confirm the **Design intent** `<select>` (`(unclassified) / Standard entry /
  Hypothesis test (by design)`) renders, pre-seeded to the advisory suggestion for a recognized label.
  Submit a trade with an explicit intent → confirm it persists (visible on the trade analysis / review).
- Soft-warn path: trip the missing-pre-trade-fields (or cap) soft-warn with an explicit **(unclassified)**
  selected; on the re-render + force resubmit, confirm the selection stays `(unclassified)` (NOT re-suggested).
- Review form on a closed trade: confirm the intent `<select>` pre-populates the persisted value (or the
  suggestion when NULL); change it → confirm the correction persists (and the grades persist too).
- A bad intent value is rejected (400 + re-render with the bad anchor cleared — not trapped).

### 4. Backfill walk + NULL→Unclassified rendering
- Run `swing trade backfill-intent`. Confirm it walks all 16 trades with `entry_intent IS NULL`, shows the
  per-trade summary line (`#id ticker date | label=... | grade=... | tags=... | current=... | suggested=...`),
  accepts the suggestion-as-default on Enter, and `skip` leaves a row NULL.
- Confirm the final summary line `N set, N skipped-already-set, N skipped-by-operator` and that a second
  run reports `0 set` for rows already classified (idempotent).
- Confirm a still-NULL trade renders as **Unclassified** (CLI `swing trade analyze`: `Intent: Unclassified`;
  the trade-process Unclassified facet) — honest, never coerced to `standard`.
- Note: VIR (`inaugural trade test`) gets **no** advisory suggestion (`suggested=(no suggestion)`) — the
  operator classifies it manually as by-design; its `NO_STOP`/`STOP_NOT_PLACED` slips remain visible in the
  execution-discipline panel regardless. SKYT (id 15) is closed-not-reviewed yet can carry a deliberate
  intent (intent ≠ review attribute).

**Confirm all four blocks before merging.**
