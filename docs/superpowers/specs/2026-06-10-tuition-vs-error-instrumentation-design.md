# Tuition-vs-Error Instrumentation (`entry_intent`) — Design Spec

**Date:** 2026-06-10 · **Phase:** research-director P0 (commissioned 2026-06-10; standing P0 from
[`docs/research-director-context.md`](../../research-director-context.md) §6).
**Brief:** [`docs/p0-tuition-vs-error-instrumentation-brainstorming-dispatch-brief.md`](../../p0-tuition-vs-error-instrumentation-brainstorming-dispatch-brief.md)
**Status:** brainstorming design spec (NO code; the writing-plans phase derives the plan).
**Branch base:** main HEAD `b1f9e88b` (schema v26).
**Skill posture:** `copowers:brainstorming` — adversarial Codex review run to `NO_NEW_CRITICAL_MAJOR` (5-round cap suspended).

---

## §0 The problem, precisely

`process_grade` and `mistake_tags` measure **execution quality against the operator's plan**. But the plan for
most of the 16 live trades was a *pre-registered, designed-to-probably-lose hypothesis probe* (H3 et al., frozen in
migration 0008). So the record shows "A-grade process, negative expectancy" — which is CORRECT (the probes were
executed as designed) but reads as self-delusion or strategy failure to anyone who doesn't already know the design
intent. It misled the research director himself (session 1, 2026-06-08). Meanwhile genuine discipline violations
(VIR carried `NO_STOP` + `STOP_NOT_PLACED`) sit in the same tag pool, visually indistinguishable from tuition.

The conflation is visible **inside the tags themselves**: the by-design Sub-A+ trades carry `CHASED` / `NO_SETUP` /
`EARLY_ENTRY` — tags that read as slips but largely reflect the *deliberately sub-optimal setup the operator chose to
probe*, not an execution failure.

**The missing dimension is trade-level DESIGN INTENT — orthogonal to execution quality:**

| | executed cleanly | executed with slips |
|---|---|---|
| **standard entry** | the goal | the real problem to surface |
| **deliberate probe (by design)** | tuition working as intended | STILL a real problem (VIR) |

The fix gives every trade an explicit intent attribute and **facets** the process surfaces by it. It does NOT weaken
slip-detection on designed trades (the bottom-right cell stays a violation), and it does NOT regrade history.

---

## §1 Live-record verification (the §3.8 standing mandate)

Pulled read-only (`mode=ro`) from `~/swing-data/swing.db` at design time (2026-06-10). The same query reported
(separately from the per-row table below): schema **v26**; `entry_intent` column **absent** (confirmed via
`PRAGMA table_info(trades)`); **16 trades**, entries 2026-04-20 → 2026-06-01. The per-row table below is the ground
truth Codex must audit every row-level claim in this spec against (the `feedback_adversarial_review_verify_data_shapes`
discipline).

| id | ticker | state | hypothesis_label (verbatim) | pg | e/m/x | disq | mistake_tags | proposed intent |
|---|---|---|---|---|---|---|---|---|
| 1 | VIR | reviewed | `inaugural trade test` | B | C/A/A | 0 | `CHASED, NO_SETUP, NO_STOP, STOP_NOT_PLACED` | by_design* (operator) |
| 2 | DHC | reviewed | `sub-A+ VCP-not-formed test (proximity_20ma + tightness fails)` | A | A/A/A | 0 | `none_observed` | by_design |
| 3 | CC | reviewed | `Sub-A+ VCP-not-formed (watch); failed: proximity_20ma, tightness` | A | A/A/A | 0 | `EVENT_IGNORED` | by_design |
| 4 | YOU | reviewed | `A+ baseline (aplus)` | A | B/A/A | 0 | `CHASED` | standard |
| 5 | VSAT | reviewed | `<NULL>` | A | A/A/C | 0 | `SOLD_TOO_EARLY, STOP_TOO_TIGHT` | standard / operator |
| 6 | SGML | reviewed | `Sub-A+ VCP-not-formed (watch); failed: proximity_20ma, tightness` | B | B/A/B | 0 | `CHASED, GAP_RISK_IGNORED, NO_SETUP, STOP_TOO_WIDE` | by_design |
| 7 | CVGI | reviewed | `Sub-A+ VCP-not-formed (watch); failed: proximity_20ma, tightness` | A | A/A/A | 0 | `none_observed` | by_design |
| 8 | LAR | reviewed | `Sub-A+ VCP-not-formed (watch); failed: proximity_20ma, tightness` | A | B/A/A | 0 | `CHASED, NO_SETUP` | by_design |
| 9 | LION | reviewed | `Sub-A+ VCP-not-formed (watch); failed: tightness, vcp_volume_contraction` | A | A/A/A | 0 | `CHASED, NO_SETUP` | by_design |
| 10 | PTEN | reviewed | `<NULL>` | A | A/A/A | 0 | `CHASED` | standard / operator |
| 11 | SATL | reviewed | `Sub-A+ VCP-not-formed (watch); failed: proximity_20ma, tightness` | A | A/A/A | 0 | `CHASED, EARLY_ENTRY, NO_SETUP` | by_design |
| 12 | SATL | reviewed | `Sub-A+ VCP-not-formed (watch); failed: proximity_20ma, tightness` | A | A/A/A | 0 | `CHASED, EARLY_ENTRY, NO_SETUP` | by_design |
| 13 | PL | reviewed | `Sub-A+ VCP-not-formed (watch); failed: proximity_20ma, tightness` | A | A/A/A | 0 | `CHASED` | by_design |
| 14 | BULZ | reviewed | `Near-A+ defensible: extension test (watch); failed: proximity_20ma` | A | A/A/A | 0 | `none_observed` | by_design |
| 15 | SKYT | **closed** | `Sub-A+ VCP-not-formed (watch); failed: TT8_rs_rank, proximity_20ma, tightness` | NULL | NULL | NULL | NULL | by_design |
| 16 | DFTX | reviewed | `Sub-A+ VCP-not-formed (watch); failed: proximity_20ma, tightness` | A | A/A/A | 0 | `NO_SETUP` | by_design |

**Verified claims (Codex must confirm each against the table above):**
1. **VIR (`STOP_NOT_PLACED`) is real** — id 1 carries both `NO_STOP` and `STOP_NOT_PLACED`. CONFIRMED.
2. **~13 A-grades** — exactly **13 A** + **2 B** (VIR id 1, SGML id 6) + **1 NULL** (SKYT id 15, closed-not-reviewed).
   CONFIRMED.
3. **`disqualifying_process_violation` does no separating work today** — **all 15 reviewed rows are `disq=0`**
   (including VIR id 1 with `NO_STOP`); the 1 closed-not-reviewed row (SKYT id 15) is `disq=NULL`. So the existing
   disqualifying flag is NOT a substitute for `entry_intent`. CONFIRMED + load-bearing.
4. **Hypothesis spread:** 11 H3-family (`Sub-A+ VCP-not-formed`), 1 H1 (`A+ baseline (aplus)`, YOU), 1 H2
   (`Near-A+ ... extension test`, BULZ), **0 H4**, 2 NULL-label manual (VSAT, PTEN), 1 `inaugural trade test` (VIR).
5. **No `Broad-watch baseline` labels yet** — the 5th hypothesis is matched MANUALLY on live trades and none of the 16
   carry it. The charter-containment statement "the entry-form prefill never suggests it" refers to the
   *hypothesis-label recommendation* prefill (`lookup_active_recommendation_label`, `include_baseline=False`) — a
   DIFFERENT surface from this spec's `suggest_entry_intent` (§5), which WOULD map a hand-entered `Broad-watch baseline`
   label to `standard`. The two prefills are independent; no current trade triggers either for Broad-watch.

\* VIR's `inaugural trade test` label maps to no frozen hypothesis; the prefill helper emits **no confident
suggestion** for it (§5.2). The operator classified it `by_design` (a deliberate first learning probe) — its `NO_STOP`/
`STOP_NOT_PLACED` slips remain unconditionally visible via the always-on cross-intent execution-discipline panel
(§7.1), which is the orthogonality the instrument exists to preserve (the intent *facet* alone would not show them
when viewing "Standard").

---

## §2 Resolved decisions (operator, 2026-06-10) + LOCKs (L1–L7, BINDING)

The four §3 forks plus two layout questions were resolved with the operator before this spec was written:

- **D1 — Semantic line: "by setup quality / probe-vs-practice."** `hypothesis_test_by_design` = a deliberate
  pre-registered probe of a setup the operator would not normally trade (H2 near-A+, H3 sub-A+). `standard` = the
  operator's genuine intended practice (H1 A+, H4 capital-blocked-but-A+-setup, **Broad-watch baseline**, clean manual).
- **D2 — Vocabulary: two values + NULL.** `{'standard', 'hypothesis_test_by_design'}`, NULL = unclassified. No third
  value (YAGNI — nothing in the record needs `forced`/`event`/`learning`).
- **D3 — Backfill: one-shot CLI walk** (`swing trade backfill-intent`), idempotent + auditable.
- **D4 — PGT trend: annotate markers only** (rolling lines stay global/unchanged).
- **D5 — Review-form correction: YES** (the review is the natural place to reconsider intent).
- **D6 — Card facet on the 'All' aggregate** (no combinatorial intent×hypothesis matrix).

- **L1 — Measurement-chain isolation (HARD).** The hypothesis registry rows, the matcher
  (`swing/recommendations/hypothesis.py:match_candidate_to_hypotheses`), tripwires, progress counters, the shadow
  engine (`research/harness/`), and the v22 temporal log are **UNTOUCHED**. `entry_intent` is a process-quality
  instrument, NEVER a measurement input. The prefill helper *reads* `hypothesis_label` one-directionally (advisory)
  and writes nothing back. If any design step appears to need a measurement-chain change, STOP and re-justify.
- **L2 — Grade/tag semantics unchanged (faceting only).** `compute_process_grade`, `validate_mistake_tags`,
  `canonicalize_mistake_tags`, the `MISTAKE_TAGS` vocabulary, the `process_grade` CHECK, and the
  `disqualifying_process_violation` semantics are NOT modified. No regrading engine; no historical grade is rewritten
  at backfill.
- **L3 — One additive migration `0027` (v26→v27).** Nullable column only; no rewriting of existing rows in the
  migration (backfill is operator-driven, post-migration); strict backup gate `current==26 AND target>=27`.
- **L4 — `entry_intent` is set-at-entry / correctable-at-review / backfillable-by-CLI.** Persisted value is ALWAYS the
  operator's explicit choice (server-stamp). NULL is never coerced to `standard`; three honest states render everywhere.
- **L5 — `#22` PGT inline-SVG-only lock preserved.** The marker-annotation change stays hand-rolled inline SVG; the
  `test_..._does_not_use_matplotlib_or_external_chart_lib` guard stays green; every existing #22 route-test hook
  (`data-series=...`, `data-panel=...`, `A=4`/`F=0`, `<polyline`, `<circle`) is preserved.
- **L6 — Phase-isolation carve-out (state it).** In scope: `swing/data/migrations/0027_*.sql`; `swing/data/db.py`
  (gate + `EXPECTED_SCHEMA_VERSION`); the Trade model + repo column plumbing (`swing/data/models.py`,
  `swing/data/repos/trades.py`); a new `swing/trades/intent.py`; `swing/trades/entry.py` + `swing/trades/review.py`;
  the entry/review web routes + templates + VMs; the CLI entry/review/backfill commands; `swing/metrics/process.py`
  + `swing/metrics/cohort.py` + the trade-process-card VM/template; `swing/metrics/process_grade_trend.py` (marker
  field only) + its VM/template (marker annotation only); tests. Default read-only posture holds for everything else.
- **L7 — V1 small.** One field, prefill, backfill, faceted card, annotated PGT markers, set/correct surfaces. No
  review-flow redesign, no historical-regrading engine, no new metric inventions, no intent×hypothesis cross-matrix.

---

## §3 The semantic contract for `process_grade` (the §3.2 deliverable — write it down)

> **`process_grade` measures execution quality *given the trade's design intent*** — "did the operator execute the
> entry / management / exit cleanly relative to what this trade was *supposed to be*?" A pre-registered probe
> (`hypothesis_test_by_design`) executed exactly as designed correctly earns a high grade; its negative R is the
> hypothesis *succeeding by design* (H3's decision criterion is a NEGATIVE mean R), not an execution failure.
> Therefore the historical "A-grade on designed losers" grades are **CORRECT and STAND**. The fix is **display
> faceting**, not regrading.

Corollaries (all BINDING):

1. **Orthogonality holds — and slips are structurally protected from disappearing.** A `hypothesis_test_by_design`
   trade with a genuine slip (VIR: `NO_STOP` / `STOP_NOT_PLACED`) STILL surfaces those slips via `mistake_tags`, and a
   slip STILL belongs in the entry/risk stage grade. The intent flag **never excuses a slip** — it only labels *what
   the trade was for*. The brief's bottom-right cell stays a violation. Critically, the intent *facet* alone is NOT
   relied on to surface slips: selecting "Standard" excludes by-design trades like VIR, and the "By-design" facet would
   otherwise bury `NO_STOP` among tuition-like `CHASED`/`NO_SETUP` tags. The **always-on cross-intent
   execution-discipline panel** (§7.1) is the structural guarantee — it shows risk/reconciliation-category tags over
   *all* trades regardless of the intent selector, so a genuine slip can never be hidden by a facet choice.
2. **No historical regrade.** Backfilling `entry_intent` writes ONLY the new column. It does not touch
   `process_grade`, `entry_grade`, `management_grade`, `exit_grade`, `disqualifying_process_violation`, or
   `mistake_tags` on any row. Existing grades stand as-is (they were correct under the contract above).
3. **NULL ≠ standard.** Unclassified trades render as a distinct third facet ("Unclassified"), never folded into
   `standard`. Coercion would re-introduce the very conflation this instrument removes.
4. **Intent is set at entry, not derived at read time.** The intent is the operator's stated purpose for the entry;
   it is persisted, not recomputed from the label on every render (the label is free-text and mutable; the persisted
   intent is the audit record). Prefill from the label is advisory only (§5).

---

## §4 Field shape, vocabulary, and column plumbing (the §3.1 deliverable)

### §4.1 Vocabulary + constants (placement matches the existing schema-enum discipline)

**The CHECK-enum constant lives in `swing/data/models.py`, NOT a new module** — colocated with `FAILURE_MODES`
(`models.py`), which is deliberately placed in the data layer to avoid an import cycle (the `Trade` dataclass
`__post_init__` must validate against it; `models.py` cannot import upward from `swing/trades/`). Mirror that exactly:

```python
# swing/data/models.py — alongside FAILURE_MODES (the schema-CHECK enum home).
ENTRY_INTENTS: frozenset[str] = frozenset({"standard", "hypothesis_test_by_design"})
```

The new `swing/trades/intent.py` module is the **presentation + prefill** layer only — it `import`s `ENTRY_INTENTS`
from `swing.data.models` (downward dependency, no cycle) and owns the display/advisory helpers:

```python
# swing/trades/intent.py
from swing.data.models import ENTRY_INTENTS

# Ordered (value, label) for the form <select>/radio + display (mirrors
# review.FAILURE_MODE_DISPLAY). ASCII-only labels (#16 stdout/cp1252 + parity).
ENTRY_INTENT_DISPLAY: tuple[tuple[str, str], ...] = (
    ("standard", "Standard entry"),
    ("hypothesis_test_by_design", "Hypothesis test (by design)"),
)
```

- `entry_intent_label(value)` → display label; `None` → `None`; unknown → itself (mirrors `failure_mode_label`).
- `entry_intent_display_choices()` → the ordered tuple for the form `<select>` + VM.
- `suggest_entry_intent(hypothesis_label)` → the advisory prefill (§5).
- A test asserts `{v for v, _ in ENTRY_INTENT_DISPLAY} == ENTRY_INTENTS` (the display/constant no-drift guard,
  copying the `FAILURE_MODE_DISPLAY` discipline). This module is pure (no I/O) and importable by entry/review/metrics.

### §4.2 Schema (`0027`, v26→v27)

Mirror the B-7 `0024` nullable-`failure_mode` migration verbatim in shape:

```sql
ALTER TABLE trades ADD COLUMN entry_intent TEXT
    CHECK (entry_intent IS NULL OR entry_intent IN ('standard','hypothesis_test_by_design'));
```

- SQLite `ALTER TABLE ... ADD COLUMN` permits a column-level `CHECK` when the column is nullable and all existing
  rows satisfy it (NULL does); `0024` did exactly this for `failure_mode` — copy that pattern. No table rebuild.
- Migration runner uses explicit `BEGIN`/`executescript`/`COMMIT` with rollback-on-exception (gotcha #9; handled by
  the existing `_apply_migration` path — no special handling needed).
- **No row rewrites in the migration.** Backfill is a separate operator-driven CLI pass (§6).

### §4.3 Trade dataclass (`swing/data/models.py`)

Add `entry_intent: str | None = None` to `Trade`, and extend `__post_init__` to validate against the same-module
`ENTRY_INTENTS` frozenset (§4.1; no import needed — both live in `models.py`, exactly as `FAILURE_MODES` does;
`Literal` is not runtime-enforced — gotcha):

```python
if self.entry_intent is not None and self.entry_intent not in ENTRY_INTENTS:
    raise ValueError(f"Trade.entry_intent must be None or one of {sorted(ENTRY_INTENTS)}; got {self.entry_intent!r}")
```

**#11 atomicity LOCK:** the schema CHECK (§4.2), the Python constant `ENTRY_INTENTS` (§4.1), and this dataclass
validator MUST land in the SAME task.

### §4.4 Repo plumbing (`swing/data/repos/trades.py`)

The repo has three schema-version-aware SELECT projections (`_TRADE_SELECT_COLS` v24+, `_..._V21_TO_V23`,
`_..._PRE_V21`) chosen by `_trade_select_cols(conn)` via `PRAGMA table_info`. `entry_intent` exists only at v27+, so:

1. **`_trade_select_cols(conn)`** — detect `entry_intent` presence via `PRAGMA table_info(trades)` (mirroring the v24
   `failure_mode` PRAGMA-aware branch) and project the real `entry_intent` column when present, else `NULL AS
   entry_intent`. This makes the floored pin merge-safe and keeps pre-v27 reads valid.
2. **`_row_to_trade`** — map `entry_intent` at a NEW trailing positional index (append at the end, after
   `failure_mode` at index 54 — exactly how `failure_mode` was appended in B-7).
3. **`insert_trade_with_event`** — write `entry_intent` at entry creation, PRAGMA/version-aware (only include the
   column at v27+), mirroring how `hypothesis_label` flows through the INSERT column lists.
4. **New `update_entry_intent(conn, *, trade_id, entry_intent)`** — a dedicated, focused repo function for
   review-time correction AND the backfill walk. It does a plain `UPDATE trades SET entry_intent = ? WHERE id = ?`
   (PRAGMA-guarded at v27+), `... or None` nullability respected. It does **not** touch any review field and does
   **not** transition state (intent is an entry attribute, independent of review state — note SKYT id 15 is
   closed-not-reviewed yet still has a deliberate entry intent). Keeping it separate from the 11-field
   `update_trade_review_fields` preserves that writer's focus and the repo-vs-service asymmetry.

**#11 sweep LOCK:** the schema-version-pin family (~40 grep hits across migration-test files asserting
`EXPECTED_SCHEMA_VERSION == 26` / `== 25` / etc.) moves to **27** in the same task family; grep ALL of `swing/` +
`tests/` for hardcoded `26`/`v26` schema pins and the `_TRADE_SELECT_COLS` index assumptions before landing.

---

## §5 Prefill (the §3.3 deliverable — advisory only)

### §5.1 Mapping (per D1, "probe-vs-practice")

| hypothesis_label family (keyword, case-insensitive on the canonicalized label) | suggested intent |
|---|---|
| contains `a+ baseline` or `aplus` | `standard` |
| contains `capital-blocked` | `standard` |
| contains `broad-watch baseline` | `standard` |
| contains `sub-a+` or `vcp-not-formed` | `hypothesis_test_by_design` |
| contains `near-a+` or `extension test` | `hypothesis_test_by_design` |
| NULL / empty / no keyword match (manual, `inaugural trade test`, unknown) | `None` (no suggestion) |

```python
def suggest_entry_intent(hypothesis_label: str | None) -> str | None:
    """Advisory default ONLY — seeds the visible form control; never read by the service/persist layer."""
```

- **Pure function**, in `swing/trades/intent.py`. Operates on the lowercased canonicalized label.
- **THE SINGLE PREFILL RULE (resolves the web-vs-CLI ambiguity):** the persisted `entry_intent` is **always exactly
  the value of the visible form control at submit time**; `suggest_entry_intent` only seeds that control's *default*.
  - **Web (entry + review):** the control is rendered pre-selected to the suggestion; the operator SEES it and can
    change it, and **submitting the form is the confirmation** (a visible, reviewable default is a deliberate choice —
    this is ordinary single-operator form UX). The POST persists the submitted control value (server-stamp — never a
    trusted hidden input).
  - **CLI:** there is no visible control to review, so an **omitted `--entry-intent` flag persists `NULL`** (no
    suggestion applied); the operator must pass the flag to set a value.
  - **The service/persist layer (`record_entry`, `update_entry_intent`) NEVER derives intent from the label** and
    never consults the matcher/registry (L1). `suggest_entry_intent` is called ONLY in the GET/render path.
- **`Broad-watch baseline → standard`** is the one debatable mapping (watch-grade yet operator-classified standard,
  because it is his real practice, not a probe). Operator-confirmed 2026-06-10; advisory, so a miss costs one radio
  click. There are zero Broad-watch trades in the record to test it.
- **V2 robustness candidate (noted, not built):** replace keyword matching with a registry-prefix match via the
  existing `canonicalize_hypothesis_label` / cohort 3-rule matcher, keyed by a `{registry_name: intent}` table. V1
  keyword heuristic is sufficient because the value is advisory and every trade is operator-confirmed at entry or in
  the backfill walk.

### §5.2 Where the suggestion renders

- **Web entry form:** the `<select>` is rendered pre-selected to `suggest_entry_intent(<current hypothesis_label>)`;
  if `None`, it renders unselected (→ persists NULL unless the operator picks). Submit = confirmation.
- **CLI entry:** no default applied — omit `--entry-intent` → NULL; pass it to set a value (the suggestion is shown
  in `--help`/docs as guidance only, never auto-applied).
- **Web review form:** the `<select>` is pre-populated with the **persisted** `entry_intent`; if NULL, falls back to
  the suggestion as the rendered default (operator confirms/corrects on submit).
- **Backfill walk:** prints the suggestion next to each trade's label/grade/tags as the prompt default; the operator
  types the choice (or `skip` → leaves NULL).

---

## §6 Backfill mechanism (the §3.4 deliverable)

`swing trade backfill-intent` — a new CLI command (in the `trade` group):

- **Scope:** walks ALL trades (every `state`, including `closed`-not-reviewed like SKYT id 15 — intent is an entry
  attribute, not a review attribute) where `entry_intent IS NULL`. **Idempotent:** already-set rows are skipped unless
  `--trade-id <id>` (re-target a single trade) or `--force` (re-prompt set rows) is passed — this also serves as the
  correction path for trades mislabeled at entry.
- **Per-trade prompt:** prints `id | ticker | entry_date | hypothesis_label | process_grade | mistake_tags` plus the
  `suggest_entry_intent` suggestion as the default; operator chooses `standard` / `hypothesis_test_by_design` / `skip`.
- **Write:** via `update_entry_intent` (§4.4) — single-column UPDATE, no state transition, no review-field touch.
- **Audit trail:** the command prints a final summary (`N set, N skipped-already-set, N skipped-by-operator`) and is
  re-runnable; the column value itself is the record. **No separate provenance table for V1** (YAGNI — the brief asked;
  the answer is "the idempotent re-runnable command + its summary is the audit"). A `trade_events`-style provenance
  row is a noted V2 candidate if intent edits ever need a history.
- **Trades left NULL:** render honestly as "Unclassified" on every faceted surface (L4); they are not coerced and not
  hidden.
- **Form-safety:** the CLI prompt validates the choice against `ENTRY_INTENTS` (+ a `skip`/blank → leave NULL);
  service-layer `ValueError` wrapped at the CLI boundary as `click.ClickException` (gotcha). ASCII-only output (#16;
  the CLI is a cp1252 stdout path).

---

## §7 Surface-by-surface disposition (the §3.5 deliverable — exhaustive)

Derived from a `process_grade|mistake_tags|hypothesis_label|entry_intent` sweep over `swing/`. Each surface:
**CHANGE** (and how) / **DISPLAY-ONLY** / **LEAVE UNCHANGED**. NULL renders as "Unclassified" wherever intent appears.

### §7.1 Core fix — faceted process surfaces (CHANGE)

| Surface | file:line | Disposition |
|---|---|---|
| `compute_trade_process_metrics` | `swing/metrics/process.py:546` | Add optional `entry_intent` filter param (sentinel default = no filter; `'standard'` / `'hypothesis_test_by_design'` / `'__unclassified__'` filter the cohort). All 22 metrics + `process_grade_distribution` + `mistake_tag_frequency` then compute over the intent-filtered set. |
| `list_closed_trades_for_cohort` / `list_trades_for_cohort` | `swing/metrics/cohort.py:32,84` | Add an optional `entry_intent` predicate (SQL `entry_intent = ?`, or `entry_intent IS NULL` for `__unclassified__`), composed with the existing hypothesis-label match. |
| Trade-process-card VM | `swing/web/view_models/metrics/trade_process_card.py:49,163` | Add an **intent facet on the "All closed trades" aggregate** (D6): a selector `All / Standard / Hypothesis-test-by-design / Unclassified`. Existing hypothesis cohort tabs UNCHANGED. This is the primary surface that makes "execution quality + which tags occur on *standard* entries" readable in isolation. |
| Trade-process-card template | `swing/web/templates/metrics/trade_process_card.html.j2` | Render the intent selector + the filtered card body. `mistake_tag_frequency` inherits the filter (the core CHASED-as-tuition vs STOP_NOT_PLACED-as-error separation). |
| Trade-process route | `swing/web/routes/metrics.py` | Accept the intent facet param (query-string), pass to the VM factory. No HTMX OOB/redirect concerns (server-rendered page). |
| **Cross-intent execution-discipline panel** (NEW, intent-independent) | `swing/metrics/process.py` (`compute_trade_process_metrics` + `TradeProcessMetricsResult`) + card VM + template | An always-on panel keeping genuine slips unconditionally visible. **Contract (specified so writing-plans does not invent it):** a new result field `execution_discipline_tag_frequency: dict[str, MetricCellA]` on `TradeProcessMetricsResult`, computed by **reusing the existing `mistake_tag_frequency` loop** ([`process.py:747`](../../../swing/metrics/process.py)) restricted to the tag set `MISTAKE_TAGS["risk"] ∪ MISTAKE_TAGS["reconciliation"]` (e.g. `NO_STOP`, `STOP_NOT_PLACED`, `OVERSIZED`, `SIZE_MISCOUNTED`, `STOP_TOO_WIDE`, `FILL_NOT_LOGGED`, …). **Source set:** the cohort's closed-reviewed trades **WITHOUT the intent filter applied** (intent-independent within the active hypothesis cohort; for the headline "All closed trades" view that is every closed-reviewed trade). **Denominator:** a SEPARATE new field `execution_discipline_n_reviewed: int` = the intent-**unfiltered** reviewed count for the cohort. The panel's `MetricCellA.sample_n` MUST use `execution_discipline_n_reviewed`, **NOT** `TradeProcessMetricsResult.n_reviewed` (which becomes the *intent-filtered* reviewed count once an intent filter is active — reusing it would shrink the panel's denominator and silently change the panel when the operator toggles the facet, defeating the guarantee). **Rendering:** Class A rates via the existing `_render_class_a_cell` + honesty/suppression machinery. **Malformed JSON:** skipped per the existing per-row isolation in the tag loop. Because it bypasses the intent filter, selecting "Standard" or "By-design" never removes a slip from this panel; because it lists only risk/reconciliation tags, slips are never buried among tuition-like entry tags. This is the structural answer to the orthogonality requirement (R1-Major-4 / R2-Major-1): the intent facet protects the *standard execution-quality read*; this panel keeps *slips* visible. |

### §7.2 PGT trend (#22) — annotate markers only (CHANGE, additive)

| Surface | file:line | Disposition |
|---|---|---|
| `ProcessGradeTrendPoint` + `compute_process_grade_trend` | `swing/metrics/process_grade_trend.py:79,524` | Add an `entry_intent: str \| None` field to the per-trade marker dataclass (read-only consume of the new column via `trade.entry_intent`). The **7 rolling series are UNTOUCHED** (rolling lines stay global — D4). The `rolling_series` keyset invariant in `ProcessGradeTrendResult.__post_init__` is unchanged. |
| PGT VM | `swing/web/view_models/metrics/process_grade_trend.py` | Thread `entry_intent` onto the rendered marker view-object; expose a per-marker CSS class hook (`standard` / `by-design` / `unclassified`). |
| PGT template | `swing/web/templates/metrics/process_grade_trend.html.j2:64` | Render `process_grade` `<circle>` markers in the GRADES panel with an intent-distinct shape/colour + a small ASCII legend entry (`standard / by-design / unclassified`). **L5: preserve every existing #22 hook** (`data-series`, `data-panel`, `A=4`/`F=0`, `<polyline`, `<circle`); the no-matplotlib test stays green. Rolling lines and the RATE/COST panels are untouched. |

Rationale for annotate-not-split (D4): only ~2-3 trades are `standard`-intent; a `standard`-only rolling line is
perpetually suppressed (<5 effective samples) and would re-open the #22 incommensurability the redesign just closed.

### §7.3 Set / correct surfaces (CHANGE)

| Surface | file:line | Disposition |
|---|---|---|
| Web entry form route + template | `swing/web/routes/trades.py:330,565` · `templates/partials/trade_entry_form.html.j2:147` | Add an `entry_intent` `<select>` (default = `suggest_entry_intent(hypothesis_label)`). POST re-reads the explicit selection (server-stamp); `... or None` → NULL when unselected. Round-trip through any soft-warn `form_values` dict so a `force=true` resubmit does not drop it. `record_entry` / `EntryRequest` thread the value to the INSERT. |
| `EntryRequest` + `record_entry` | `swing/trades/entry.py:98,224` | Add `entry_intent: str \| None = None`; validate against `ENTRY_INTENTS`; pass to `insert_trade_with_event`. |
| CLI entry | `swing/cli.py:699` | Add `--entry-intent` option (choice-validated); default from `suggest_entry_intent` when omitted-and-label-present is **not** auto-applied (advisory) — explicit value or NULL. |
| Web review form route + template + VM | `swing/web/routes/trades.py:2620,2669` · `templates/partials/review_form.html.j2` · `view_models/trades.py` (ReviewVM) | D5: add an intent `<select>` pre-populated with the persisted value (NULL → suggestion default). POST persists via `update_entry_intent` (separate from `complete_trade_review`'s field write; same request). Form-safety: 4-tier rejection ladder on the value; `... or None`; server-stamp. |
| CLI review | `swing/cli.py:1364` | Add `--entry-intent` correction option (optional; when omitted, leaves the persisted value). |

### §7.4 Display-only (CHANGE, read-only render)

| Surface | file:line | Disposition |
|---|---|---|
| CLI single-trade analysis | `swing/cli.py:1098` (`_render_trade_analysis`) | Print the trade's `entry_intent` (label via `entry_intent_label`; `Unclassified` for NULL). ASCII-only. |

### §7.5 Leave UNCHANGED (stated explicitly, with reason)

| Surface | file:line | Why unchanged |
|---|---|---|
| Metrics index / overview | `swing/web/view_models/metrics/index.py:27,203` | Surfaces the `process_grade_rolling_N` headline trend metric; intent is a faceting concern on the detail surfaces, not the overview headline. V1-small. |
| `hypothesis_progress_card` | `swing/web/view_models/metrics/hypothesis_progress_card.py:317` | **Measurement-adjacent (L1).** It tracks hypothesis *sample progress* toward frozen targets — intent is not a measurement input and must not enter it. |
| Dashboard open-trade hypothesis counts | `swing/web/view_models/dashboard.py:283` | Not a process-quality surface (open-position framing). |
| Journal aggregate hypothesis breakdown | `swing/journal/stats.py:245` · `cli.py:1595` | **Leave unchanged — explicitly accepted V1 blind spot.** NOT because the label captures intent: the live record *disproves* that (VIR is by-design under an unregistered `inaugural trade test` label; VSAT/PTEN are standard under `NULL` labels — §1). The honest rationale is scope: the **faceted trade-process card (§7.1) is the V1 intent-separated surface**, and the journal breakdown is a P&L/expectancy-by-hypothesis view, not a process-quality view. Adding an intent column/breakdown to the journal is a noted **V2**. Documented as a blind spot, not justified by a false "label≈intent" claim. |
| Web journal row VM | `swing/web/view_models/journal.py:174` | Shows `hypothesis_label` per row; an intent column is V2 display polish. |
| `trade_chronology._review_entry` | `swing/web/view_models/trade_chronology.py:157` | Per-trade timeline; surfacing intent on the entry event is V2 display polish. |
| `sparkline.py` | `swing/web/view_models/metrics/sparkline.py` | Pure rendering helper; reads no trade fields. |

### §7.6 Conflation-leak surfaces — review priors + cadence aggregates (explicitly adjudicated)

Two surfaces read `mistake_tags` / `process_grade` into *operator-facing review defaults/aggregates* and were missing
from the original sweep. They ARE conflation-leak points (a by-design `CHASED`/`NO_SETUP` can seed a future default or
a period total). Both are **V1 LEAVE-UNCHANGED with an explicit accepted-blind-spot rationale** (not silent):

| Surface | file:line | Disposition + rationale |
|---|---|---|
| `get_priors_for_ticker` (review-form priors: same-ticker recent `mistake_tag_candidates` + `process_grade_baseline`) | `swing/trades/review.py:372` (consumed by `build_review_vm`, `swing/web/view_models/trades.py`) | **Leave unchanged (accepted).** These are *advisory defaults the operator reviews and edits on every review submit*, not an analytical claim about the record. A leaked tag costs one edit. Intent-filtering the priors (`AND entry_intent = <this trade's intent>`) is a clean **V2** once intents are populated. Documented, not hidden. |
| `get_period_mistake_tag_aggregate` (cadence weekly/monthly review "most_common_mistake_tags") | `swing/trades/review.py:487` (consumed at `swing/web/view_models/trades.py:~1580`) | **Leave unchanged (accepted).** This is the operator's *periodic-review* aggregate, a distinct surface from the analytical trade-process card. The faceted card `mistake_tag_frequency` (§7.1) + the cross-intent execution-discipline panel ARE the V1 analytical surfaces for "tuition vs error". An intent-split cadence aggregate is a noted **V2**. The conflation here is the operator's own retrospective, where he already knows which trades were probes. |

This makes the sweep genuinely exhaustive: every surface reading `mistake_tags`/`process_grade`/`hypothesis_label`/
`entry_intent` is now classified CHANGE / DISPLAY-ONLY / LEAVE-UNCHANGED-with-reason, NULL-rendering decided.

---

## §8 Form-safety compliance (the §3.7 deliverable)

Every new form field walks the CLAUDE.md web-form gotcha family:

- **Server-stamp, don't trust hidden inputs.** `entry_intent` is a visible `<select>` the operator submits; the POST
  reads the explicit selection and persists it. The prefill suggestion is a display-default only, never a trusted
  hidden value resubmitted blindly.
- **`... or None` for the nullable CHECK column.** An unselected/empty intent persists as SQL `NULL`, not `""` (which
  the CHECK would reject and which is truthy — the `... or ""` vs `... or None` gotcha).
- **4-tier rejection ladder** on the POST value: malformed / non-member / empty handled → 400 + clear, or coerced to
  NULL for the legitimate "unselected" case; the recovery form must not trap the operator on a bad value.
- **Soft-warn `form_values` round-trip:** if the entry/review POST has a soft-warn confirm path, `entry_intent`
  round-trips through `form_values` so a `force=true` resubmit does not silently drop it.
- **HTMX (if the form fragment is HTMX-submitted):** preserve the embedded-form `hx-headers '{"HX-Request":"true"}'`
  and the `204 + HX-Redirect` success contract — but this is existing entry/review-form wiring, not new; the new
  field rides the existing submit. Operator-witnessed browser verification is BINDING for any HTMX form change.
- **CLI:** service-layer `ValueError` wrapped as `click.ClickException` at the boundary; ASCII-only output (#16).

---

## §9 Migration + backup-gate discipline (hard constraints)

- **`EXPECTED_SCHEMA_VERSION` 26 → 27** (`swing/data/db.py`).
- **New `_entry_intent_backup_gate`** mirroring `_broad_watch_baseline_backup_gate` **verbatim** in shape, with strict
  equality `target_version >= 27 and current_version == 26` (NOT `<=`; multi-version jumps bypass by design — the
  `pre_version == (target - 1)` gotcha). New `_create_pre_entry_intent_migration_backup` +
  `ENTRY_INTENT_PRE_MIGRATION_EXPECTED_TABLES` (= the v26 expected-tables set, which must already include
  `pipeline_step_timings` per the v25 Arc-1 family and the broad-watch registry seed). Register the gate in
  `run_migrations` immediately after `_broad_watch_baseline_backup_gate`.
- **Migrate-twice no-op test** (running migrations twice does not double-apply / does not clobber).
- **`#11` sweep** (LOCK, one coordinated task family): schema CHECK + `ENTRY_INTENTS` constant + dataclass
  `__post_init__` validator land together; the schema-version-pin family across migration-test files moves to 27; the
  three `_TRADE_SELECT_COLS` projections + `_trade_select_cols` PRAGMA branch + `_row_to_trade` index + INSERT path
  are widened in the same task as the read-path mapper.
- **The live v26→v27 migration fires on the operator's next write-path touch, backup-gated** (the live DB is read-only
  during this design; the implementer works against fixtures + a test DB). This is a post-merge operator gate, like
  every prior schema arc.

---

## §10 Test strategy

- **Migration:** `0027` applies on a v26 fixture; `entry_intent` column present + CHECK enforced (rejects
  `'foo'`, accepts NULL / `'standard'` / `'hypothesis_test_by_design'`); migrate-twice no-op; backup-gate strict-equality
  test (fires at 26→27, not at a 25→27 jump).
- **Model/repo:** `Trade.__post_init__` rejects a bad `entry_intent`; round-trip insert→read preserves it; pre-v27
  projection yields `NULL AS entry_intent`; `update_entry_intent` writes the single column without touching review
  fields or state; `_row_to_trade` index correct.
- **Prefill:** `suggest_entry_intent` table-driven test over the §5.1 keyword families + the live labels (assert YOU→
  `standard`, the Sub-A+/Near-A+ labels→`by_design`, VIR `inaugural trade test`→`None`, NULL→`None`).
- **Faceting:** `compute_trade_process_metrics(entry_intent='standard')` over a fixture with mixed intents returns the
  standard-only cohort; `mistake_tag_frequency` reflects only standard-intent tags; `__unclassified__` isolates NULL;
  no-filter equals today's behaviour (regression-arithmetic: distinguish filtered vs unfiltered counts).
- **Execution-discipline panel (the orthogonality guarantee):** a fixture with a `hypothesis_test_by_design` VIR-like
  trade carrying `NO_STOP`/`STOP_NOT_PLACED` plus `standard` trades — assert `execution_discipline_tag_frequency`
  includes `NO_STOP`/`STOP_NOT_PLACED` and that those entries are **identical whether the intent filter is `'standard'`,
  `'hypothesis_test_by_design'`, or unset** (the panel is intent-independent — the slip never disappears when "Standard"
  is selected); assert tuition-only entry tags (`CHASED`) do NOT appear in the panel (it lists only risk/reconciliation
  categories).
- **PGT marker:** the per-trade marker carries `entry_intent`; the template emits the intent CSS-class hook; the 7
  rolling series + every existing #22 route-test hook are byte-stable (no-matplotlib test green).
- **Form-safety:** entry/review POST with an empty intent persists NULL (not `""`); a bad value is rejected; the
  soft-warn `form_values` round-trip preserves the selection on `force=true`.
- **Backfill CLI:** idempotent (second run sets nothing); `--trade-id`/`--force` re-target; summary counts correct;
  bad input raises `ClickException`; ASCII-only output (subprocess-through-PowerShell encoding test).
- **Live-record regression:** a fixture mirroring the §1 table (real emitter shape) verifies the prefill suggestions
  and the standard-vs-by-design split match the proposed-intent column.

### §10.1 Operator browser/CLI gate (BINDING, like #22)
TestClient asserts structure only. The operator witnesses: (1) the trade-process card intent facet renders + the
`standard`-only view isolates real execution quality (and the under-populated states render honestly, not blank —
the seeded-gate-masks lesson) **AND the always-on execution-discipline panel keeps risk/reconciliation slips visible
unchanged as the intent facet is toggled**; (2) the PGT GRADES panel shows intent-distinct markers + legend in light AND dark
mode; (3) the entry + review forms set/correct intent and persist; (4) the backfill walk classifies all 16 + the
NULL→Unclassified rendering is honest. Merge blocked until confirmed.

---

## §11 V1 simplifications + V2 candidates

**V1 INCLUDES (load-bearing, not optional):** the `entry_intent` column + migration; set/correct surfaces
(entry+review web/CLI); the idempotent backfill walk; the faceted trade-process card + `mistake_tag_frequency`; **the
always-on cross-intent execution-discipline panel (§7.1) — this carries the orthogonality guarantee and must ship in
V1, not be deferred**; the annotated PGT markers.

**V1 simplifications:** two-value enum (no `forced`/`event`/`learning`); keyword prefill (not registry-prefix);
backfill audit = idempotent re-runnable command + summary (no provenance table); intent facet on the "All" aggregate
only (no intent×hypothesis matrix); PGT markers annotated (lines not split); display-only on the single-trade CLI
view; journal/chronology/index left unchanged.

**V2 candidates (noted, not built):** registry-prefix prefill via `canonicalize_hypothesis_label`; an intent-edit
provenance/audit row; intent breakdown in the journal aggregate + a journal-row intent column; **intent-filtered
review priors** (`get_priors_for_ticker`); **intent-split cadence mistake-tag aggregate**
(`get_period_mistake_tag_aggregate`); intent on the trade chronology entry event; per-intent rolling lines on PGT once
the standard cohort exceeds the suppression floor; a third intent value if forced/closing-event entries ever appear.

---

## §12 Cumulative-discipline compliance

- **Migration gotchas:** #9 explicit BEGIN/COMMIT (runner); strict backup-gate equality; #11 schema/constant/validator
  atomicity + the hardcoded-version + SELECT-col sweep.
- **Web-form gotchas:** server-stamp; `... or None` nullability with the CHECK; 4-tier rejection ladder; soft-warn
  `form_values` round-trip; HTMX submit contracts preserved (existing wiring); operator-witnessed browser gate binding.
- **`Literal` not runtime-enforced** → frozenset `__post_init__` validation.
- **Service `ValueError` wrapped at the CLI boundary** as `ClickException`.
- **#16 ASCII** — all CLI/form rendered strings ASCII (cp1252 stdout path + the matplotlib-N/A inline-SVG legend).
- **Synthetic-fixture-vs-real-emitter drift** — fixtures derive from the §1 live-record shapes; the prefill +
  faceting tests exercise the real label strings, not idealized ones.
- **Measurement-chain isolation (L1)** — registry / matcher / tripwires / progress / shadow engine / temporal log
  untouched; `entry_intent` never a measurement input; `hypothesis_progress_card` explicitly left unchanged.
- **Commits:** conventional; NO `Co-Authored-By`; NO `--no-verify`; final `-m` paragraph plain prose; verify
  `git log -1 --format='%(trailers)'` is `[]` before any push (trailer-parse-hazard).

---

## §13 Position note

P0 instrument. NO measurement-chain change; NO regrading; one additive nullable column; faceting + annotation + an
always-on cross-intent execution-discipline panel that keeps genuine slips unconditionally visible.
It resolves the tuition-vs-error conflation that misled the research director on the 16-trade record (§0–§1) by adding
the orthogonal design-intent axis the surfaces were missing, while preserving every existing grade/tag semantic and
the #22 PGT redesign. Output of this brainstorming phase: this design spec → writing-plans → executing-plans as
separate dispatches.

---

*End of design spec. `entry_intent` nullable enum (`standard` | `hypothesis_test_by_design` | NULL), migration 0027
(v26→v27, strict backup gate), set-at-entry / correctable-at-review / CLI-backfilled, prefill advisory-only, faceted
trade-process card + mistake_tag_frequency + an always-on cross-intent execution-discipline panel, annotated PGT
markers — measurement chain and grade/tag semantics untouched.*
