# B-7 Operator Failure-Mode Classification — Design Spec

**Date:** 2026-06-03
**Phase:** 15 (second commissioned arc; the schwabdev-v3 + Fernet arc SHIPPED+CLOSED `77d2747e`).
**Brief:** [`docs/b7-operator-failure-mode-brainstorming-dispatch-brief.md`](../../b7-operator-failure-mode-brainstorming-dispatch-brief.md) (dispatch HEAD `edbbd5d8`).
**Status:** Brainstorming design spec — capture-only V1. NOT a plan; the writing-plans phase derives the task plan from this.
**Schema verdict:** v23 → **v24** — the FIRST schema migration since the schwabdev arc (which made NO swing-DB schema change; the last bump was v22→v23 at SB3 `edd098d`).

---

## §1 Architecture overview

B-7 adds ONE new column of state — `trades.failure_mode` — and threads it through the existing
CR.1 post-trade review surface so the operator can record **why a closed trade failed** for later
outcome-attribution analysis. Nothing else in the system grows: there is no new table, no new
route, no new service module. The feature is a thin capture surface layered on machinery that
already exists.

The five touch-points, all on the established Phase-6/Phase-7 review path:

1. **Schema** — migration `0024` adds the nullable, CHECK-constrained `failure_mode` TEXT column to
   `trades`; `EXPECTED_SCHEMA_VERSION` 23 → 24; a strict `_b7_backup_gate` mirrors the
   `_phase14_sb3_backup_gate` shape.
2. **Model + read mapper** — `Trade.failure_mode` field + `__post_init__` frozenset validation
   ([`swing/data/models.py`](../../../swing/data/models.py)); `_row_to_trade` + `_TRADE_SELECT_COLS`
   widened, with a `_TRADE_SELECT_COLS_PRE_V24` legacy projection for pre-v24 fixtures
   ([`swing/data/repos/trades.py:478-550`, `:57-119`](../../../swing/data/repos/trades.py)).
3. **Persistence** — `update_trade_review_fields` (repo, `:553-595`) + `complete_trade_review`
   (service, [`swing/trades/review.py:550-618`](../../../swing/trades/review.py)) each gain a
   keyword-only `failure_mode: str | None = None` parameter.
4. **Web form** — a new `<select name="failure_mode">` fieldset on
   [`review_form.html.j2`](../../../swing/web/templates/partials/review_form.html.j2); the POST
   handler ([`swing/web/routes/trades.py:2669-2799`](../../../swing/web/routes/trades.py)) parses,
   validates, and threads it; the GET VM (`build_review_vm`, view_models/trades.py:1224) surfaces
   the choice list.
5. **Read-back** — `_review_entry`
   ([`swing/web/view_models/trade_chronology.py:157-187`](../../../swing/web/view_models/trade_chronology.py))
   folds `failure_mode` into the per-trade chronology review entry's detail string.

The vocabulary itself (§3) is the single substantive design question; everything else is mechanical
wiring against a well-trodden path.

---

## §2 Pre-locked decisions + L1–L6 (BINDING, from the brief)

- **L1 — Capture-only V1.** Scope = the column, the review-form control, persistence through
  `complete_trade_review`, and the read-back display. The downstream failure-mode
  distribution/analysis surface is a follow-on (OQ-5), explicitly OUT of V1. No change to grading or
  the mistake-tags vocabulary.
- **L2 — Orthogonal to process-grade AND mistake-tags.** `failure_mode` answers *why the trade
  failed* (thesis / market / execution / event), NOT *how well the operator executed* (grades) NOR
  *what process mistakes occurred* (`mistake_tags`). Fully spelled out in §6, with a test that proves
  the separation.
- **L3 — Phase-isolation carve-out (EXPLICIT).** B-7 writes into the normally-read-only
  `swing/trades/review.py` and `swing/data/` trees: a new nullable `trades` column, migration `0024`,
  the `Trade` dataclass field + validator, the `_row_to_trade`/`_TRADE_SELECT_COLS` read path, and the
  `complete_trade_review` / `update_trade_review_fields` signatures. This carve-out is scoped exactly
  as Phase 6 scoped the original review carve-out (per the Invariants block: "6 added
  `swing/trades/review.py` … + 10 nullable trade-row fields"). Default read-only posture holds
  everywhere else.
- **L4 — Schema is the design's center.** New nullable `failure_mode` column on `trades` →
  migration `0024` / v24, with the strict backup-gate and gotcha-#11 atomic-consistency discipline
  (§4). Alternatives formally weighed and rejected in §4.2.
- **L5 — Nullable + outcome-scoped.** A winning trade has no failure mode → the column is nullable;
  `NULL` is the canonical "no failure attributed" state. Persistence uses `... or None` (NOT
  `... or ""`) for the CHECK-constrained column (§4.3). Solicitation scope = OQ-2 (§11), recommended
  resolution in §5.2.
- **L6 — Preserve every review-form gotcha.** `hx-headers HX-Request`; `204` + `HX-Redirect` on
  success; `400` + re-render on validation failure; the server-stamped
  `auto_populated_field_keys_json` audit envelope round-trips untouched; `... or None` persistence;
  the binding gate is an **operator-witnessed browser submit** (HTMX surfaces TestClient cannot
  catch). Detailed in §5 + §7.

---

## §3 The failure-mode vocabulary (the core)

### §3.1 Design intent

A **tight, single-select, CHECK-constrained enum** of *proximate loss causes* — the operator's own
attribution language for "why did this trade fail." It is grounded in the project's source
frameworks (Minervini TLSMW sell-side rules; the Disciplined-Swing-Trader / Qullamaggie exit-rule
corpus in the `qullamaggie` MCP). The axes the brief names — **market / thesis / execution /
risk-event** — map cleanly onto a small set; I add two more the framework corpus repeatedly
surfaces (a volatility-shakeout axis and a time/opportunity axis), plus an `other` escape valve.

### §3.2 The recommended V1 set (7 values)

| Value | Axis | Meaning (the operator's attribution) | Framework anchor |
|-------|------|--------------------------------------|------------------|
| `thesis_invalidated` | thesis | The entry thesis broke on its own merits — pattern failed, key support / moving-average lost, leadership/fundamental premise no longer held. The archetypal **"good loss"** when paired with clean process. | Minervini M.3/M.6 (violated-MA, volume-confirmed breakdown); Qulla "lost the 10/20 EMA → sell". |
| `normal_volatility_stop` | volatility | Stopped out by routine noise / a shakeout while the broader thesis arguably remained intact (stop too tight, minimal-margin stop-out). Distinct from a genuine thesis break. | Qulla ROKU lesson: "tightened stop too aggressively … stopped out by minimal margin"; "don't tighten stops too early". |
| `market_regime_shift` | market | A broad-market or sector breakdown drove the exit (risk-off, sector leader broke, correlation event), independent of the stock's own merits. | Qulla "if the sector leader breaks down, sell the laggards"; "market too strong/weak". |
| `adverse_event_shock` | risk-event | An exogenous news / earnings / gap event caused the loss (gap-down on news, earnings miss). Event-driven, not chart-driven. | Minervini M.7 (gap-down on news); the entry-side `event_risk_present` / `gap_risk_present` premortem fields. |
| `execution_error` | execution | The adverse outcome was driven by an operational/execution problem — slippage, a late or missed exit, wrong order or size, slow to act — rather than the thesis being wrong. | Qulla "speed of execution … cost $100K"; "don't hold weak positions overnight". |
| `failed_to_advance` | time / opportunity | Dead money: the position never worked, didn't advance within the expected window; a scratch or small loss taken on a time-stop / opportunity-cost basis. | Qulla Q.1 "if it doesn't go anywhere in 3-5 days, sell it"; "scale out of positions that haven't gone anywhere". |
| `other` | — | None of the above; an idiosyncratic cause. The escape valve so the operator is never trapped. Narrative detail lives in the existing `lesson_learned` free-text. | — |

`NULL` (the absence of any value) means **"no failure attributed"** — the natural state of a winning
trade, or a losing trade the operator chose not to classify. `NULL` is NOT a vocabulary value; it is
the column's default and the winner state (see §5.2, and the rejected `not_a_loss` sentinel in
§5.2.1).

### §3.3 Why these are mutually distinguishable

Each value sits on a different causal axis, and the discriminating question for each is disjoint:
- *Did the chart/thesis itself break?* → `thesis_invalidated`
- *Did a noise wick take you out while the thesis held?* → `normal_volatility_stop`
- *Was it the market/sector, not the stock?* → `market_regime_shift`
- *Was it an exogenous news/earnings/gap event?* → `adverse_event_shock`
- *Was it how you executed, not what you picked?* → `execution_error`
- *Did it simply never move?* → `failed_to_advance`

The one pair that can blur — `thesis_invalidated` vs `normal_volatility_stop` — is precisely the
distinction the framework corpus treats as load-bearing (a real breakdown vs a premature shakeout),
so keeping both is doctrine-faithful, not redundant.

### §3.4 The exact frozenset (the canonical Python mirror)

```python
# swing/trades/review.py
FAILURE_MODES: frozenset[str] = frozenset({
    "thesis_invalidated",
    "normal_volatility_stop",
    "market_regime_shift",
    "adverse_event_shock",
    "execution_error",
    "failed_to_advance",
    "other",
})
```

Display labels (form `<option>` text) are title-cased prose ("Thesis invalidated", "Normal-volatility
stop", "Market / sector regime shift", "Adverse event shock", "Execution error", "Failed to advance
(dead money)", "Other"). The stored value is always the snake_case token.

**OQ-4 (operator-binding):** the exact value set and labels are the operator's own attribution
language. The set above is the recommendation; the operator confirms / edits at writing-plans.

---

## §4 Schema design (L4 + gotcha #11)

### §4.1 Recommended: a new nullable CHECK-constrained column → migration 0024 / v24

```sql
-- swing/data/migrations/0024_phase15_b7_failure_mode.sql
-- gotcha #9: explicit BEGIN; … COMMIT; (executescript implicit-COMMIT discipline).
BEGIN;
ALTER TABLE trades ADD COLUMN failure_mode TEXT
    CHECK (failure_mode IS NULL OR failure_mode IN (
        'thesis_invalidated', 'normal_volatility_stop', 'market_regime_shift',
        'adverse_event_shock', 'execution_error', 'failed_to_advance', 'other'
    ));
UPDATE schema_version SET version = 24;
COMMIT;
```

`ALTER TABLE … ADD COLUMN` with a nullable column + a CHECK referencing only the new column is a
cheap, non-rebuild migration (no table copy needed — contrast SB3's `chart_renders` rebuild, which
was forced only by an enum-VALUE rename of an existing column). The existing-row backfill is
implicit: every pre-v24 trade row reads `failure_mode = NULL` (OQ-6 forward-only; §11).

### §4.2 Alternatives weighed and rejected

| Alternative | Verdict | Reason |
|-------------|---------|--------|
| A new `failure_mode` **category in `MISTAKE_TAGS`** | **REJECTED** | No schema change, but violates **L2** — folds outcome-attribution into the process-mistake vocabulary, destroying the "good loss / bad loss" separation and contaminating the mistake-tag frequency metric. |
| A **free-text** `failure_mode` column (no CHECK) | **REJECTED** | No controlled vocabulary → not aggregatable for the follow-on analysis surface (OQ-5); the whole point is a small distinguishable taxonomy. Free-text narrative is already covered by `lesson_learned`. |
| A new **side-table** (`trade_failure_modes`, FK to trades) | **REJECTED (overkill)** | Single-select, single-cardinality, one-per-trade data with no history — a 1:1 child table buys nothing over a nullable column and adds a JOIN to every read. Reserve the side-table shape for if/when multi-select (OQ-3) is adopted in V2. |
| **Reuse `fills.reason`** | **REJECTED** | `fills.reason` is per-leg free-text describing an individual exit fill, not a trade-level attribution; semantically wrong grain and not aggregatable. |

The nullable CHECK column is the minimal change that satisfies L1/L2/L4/L5 simultaneously.

### §4.3 Gotcha #11 — atomic consistency (all in ONE task)

The CHECK enum, the Python constant, the dataclass validator, and the read mapper MUST land
together in a single task, or a partial landing leaves a schema that accepts values the model
rejects (or vice-versa). The complete set:

1. **Migration 0024** — the CHECK enum (the 7 tokens) — §4.1.
2. **`FAILURE_MODES` frozenset** — `swing/trades/review.py` — the canonical Python mirror (§3.4).
3. **`Trade.failure_mode: str | None = None`** + `__post_init__` validation against `FAILURE_MODES`
   — `swing/data/models.py:214-265` (append after the Phase-6 review block). `Literal[...]` is NOT
   runtime-enforced (gotcha) → an explicit frozenset check is required for this external/CLI-fed
   field.
4. **Read-path widening** — `_row_to_trade` (`repos/trades.py:478-550`) reads the new column;
   `_TRADE_SELECT_COLS` appends `failure_mode`; a new `_TRADE_SELECT_COLS_PRE_V24` legacy projection
   emits `NULL AS failure_mode`; `_trade_select_cols` (`:105-119`) gains a `failure_mode`-presence
   branch (PRAGMA `table_info` detection) so the ~140 pre-v21/pre-v24 fixture callsites keep reading
   positionally. **This is the single most error-prone wiring point** — the brief's #11 "read-path
   `_row_to_*` mapper widened in the SAME task as the write-path" is exactly this.
5. **Write-path widening** — `insert_trade_with_event` SVAI branch (`repos/trades.py:155-181`): the
   INSERT column list referencing `failure_mode` against a pre-v24 schema raises `no such column`
   (NULL defaults do NOT cover that case — verbatim the v21 SVAI precedent). Entry-time
   `failure_mode` is always NULL (it's a review-time field), so the legacy INSERT path simply omits
   the column; the SVAI branch must still tolerate both schemas.

### §4.4 The strict backup-gate (v23 → v24)

Add `_b7_backup_gate` to `swing/data/db.py`, copying `_phase14_sb3_backup_gate` (`:909-950`)
verbatim in shape:

```python
def _b7_backup_gate(conn, *, current_version, target_version, backup_dir):
    # Fires ONLY when current_version == 23 AND target_version >= 24 (STRICT
    # equality per the pre_version == target-1 gotcha; NOT <=). Multi-step walks
    # from pre-v23 baselines bypass by design (Phase 9/12/13/14 precedent).
    if target_version < 24 or current_version != 23:
        return
    ...  # _create_pre_b7_migration_backup + _verify_backup_integrity
```

with a `B7_PRE_MIGRATION_EXPECTED_TABLES` snapshot set, a `_create_pre_b7_migration_backup` helper
(filename `swing-pre-b7-migration-<ISO>.db`), and the call wired into `run_migrations` alongside the
existing gates (`db.py:977-1019`). `EXPECTED_SCHEMA_VERSION` 23 → 24.

---

## §5 The review-form UX

### §5.1 Form control + placement

A new fieldset on [`review_form.html.j2`](../../../swing/web/templates/partials/review_form.html.j2),
placed AFTER the "Mistake tags" fieldset and BEFORE the "Counterfactual" fieldset, clearly labeled to
signal it answers a different question than the grades/tags:

```html
<fieldset>
  <legend>Why did this trade fail? (outcome attribution — optional)</legend>
  <label>
    Primary failure mode
    <select name="failure_mode">
      <option value="">&mdash; not a loss / not attributed &mdash;</option>
      {% for value, label in vm.failure_mode_choices %}
        <option value="{{ value }}">{{ label }}</option>
      {% endfor %}
    </select>
  </label>
  <p><small>Records the proximate cause of the loss for later attribution analysis.
     Separate from process grade (how well you executed) and mistake tags (what you
     did wrong) — a clean "good loss" can be an A-grade trade with zero mistakes.</small></p>
</fieldset>
```

The blank `value=""` option is selected by default → an unattributed submit persists `NULL`. The
review form renders ONLY for closed-but-unreviewed trades (`build_review_vm` returns `None`
otherwise), so there is no prior value to pre-select — the control always opens at blank.

### §5.2 Solicitation scope (OQ-2) — recommendation

**Recommended: nullable, the control is ALWAYS shown, OPTIONAL at submit, with helper text
emphasizing it for losses; winners simply leave it blank → `NULL`.** This is the brief's L5 option
(a) — "nullable + only solicited for losing/scratch trades" — implemented WITHOUT hard-gating the
control's visibility on a derived R outcome. Rationale: gating visibility on
`actual_realized_R_effective <= 0` introduces a derivation dependency and a GET/POST TOCTOU surface
for no real benefit — a `NULL` from a winner and a `NULL` from an un-classified loss are
indistinguishable AND identical in meaning ("no failure attributed"). The helper text steers the
operator; the data model stays trivially clean.

#### §5.2.1 Rejected: an explicit `not_a_loss` sentinel

The brief's L5 option (b) — always-solicited with a `not_a_loss` / `n/a` enum value — is **rejected**.
A `not_a_loss` token pollutes a *failure*-cause taxonomy with a non-failure, and forces the analysis
surface (OQ-5) to filter it back out everywhere. `NULL` already encodes "no failure" cleanly and is
the column default. Keeping the enum strictly about failure causes is the orthogonality-preserving
choice.

### §5.3 Required-vs-optional at submit (OQ-7) — recommendation

**Recommended: OPTIONAL** (no "at-least-one" gate analogous to the mistake-tags rule). Forcing an
attribution when the operator is genuinely unsure manufactures noise in the very dataset the feature
exists to keep clean. The mistake-tags `none_observed` gate exists because "no mistakes" is itself a
meaningful, assertable claim; "I don't know why it failed" is not — `NULL` is the honest encoding.
**Flagged for operator (OQ-7):** if the operator wants failure-mode REQUIRED on losing trades, the
plan adds an outcome-conditional gate (mirroring the empty-mistake-tags 400 + re-render ladder),
which reintroduces the R-derivation dependency §5.2 avoided.

### §5.4 POST handler wiring

In `review_post` ([`routes/trades.py:2669-2799`](../../../swing/web/routes/trades.py)):

1. Add `failure_mode: str | None = Form(None)` to the signature.
2. Normalize + validate: `fm = failure_mode or None` (the `... or None` gotcha — empty string →
   `NULL`); if `fm is not None and fm not in FAILURE_MODES` → `400` + re-render `review_form.html.j2`
   with `error_message` (the SAME 400 + re-render ladder the empty-mistake-tags branch uses,
   `:2706-2739`).
3. Thread `failure_mode=fm` into the `complete_trade_review(...)` call (`:2778`).
4. Success path UNCHANGED: `204` + `HX-Redirect: /reviews/pending`.

The validation is defense-in-depth: the `<select>` can only emit valid tokens, but a hand-crafted
POST can carry anything, so the server validates against `FAILURE_MODES` before the CHECK constraint
would reject it (a clean 400, not a 500 from the DB).

### §5.5 VM wiring

`ReviewVM` (view_models/trades.py:1139) gains `failure_mode_choices: tuple[tuple[str, str], ...] = ()`
(value, label pairs) with a safe default — satisfying the shared-`base.html.j2` 5-VM
existing-fields rule (a new `vm.foo` needs a safe default on every base-layout VM only if the base
template dereferences it; `failure_mode_choices` is referenced ONLY in `review_form.html.j2`, so the
default on `ReviewVM` suffices, but the plan double-checks no base-layout deref). `build_review_vm`
(`:1224-1370`) populates it from a `failure_mode_display_choices()` helper in `review.py` that pairs
each `FAILURE_MODES` token with its label.

### §5.6 Read-back display

`_review_entry` ([`trade_chronology.py:157-187`](../../../swing/web/view_models/trade_chronology.py))
is the per-trade read-back: it SELECTs the review columns for a reviewed trade into the chronology
stream. Add `failure_mode` to its SELECT and fold it into the `detail` string (e.g.
`detail = "; ".join(b for b in (failure_mode_label, lesson, tag_display) if b)`). Because this SELECT
names explicit columns (not via `_trade_select_cols`), it is v24-coupled; chronology test fixtures
must migrate to v24 (§7). The review FORM page (`review.html.j2`) is NOT a read-back surface — it
renders only pre-review (build_review_vm returns None once reviewed), so the chronology is the
correct single display target for a completed attribution.

---

## §6 The orthogonality contract (L2)

`failure_mode` is provably independent of both the process grade and the mistake tags:

- **It does NOT feed `compute_process_grade`** ([`review.py:102-138`](../../../swing/trades/review.py)).
  That function's signature is `(*, entry, management, exit_, disqualifying)` — `failure_mode` is not a
  parameter and MUST NOT become one. The grade measures execution quality; the failure mode measures
  outcome cause. They are deliberately decoupled.
- **It is NOT a mistake tag.** It lives in its own `FAILURE_MODES` frozenset, its own column, its own
  fieldset. It does not appear in `MISTAKE_TAGS` (`review.py:37-62`) and is excluded from
  `validate_mistake_tags` / `canonicalize_mistake_tags`. The mistake-tag frequency metric never sees
  it.
- **It is independently queryable** — a plain column on `trades`, filterable on its own.

**The "good loss / bad loss" thesis the contract protects:**

| Trade | `process_grade` | `failure_mode` | `mistake_tags` | Reading |
|-------|-----------------|----------------|----------------|---------|
| Good loss | `A` | `thesis_invalidated` | `["none_observed"]` | Correct process, the thesis was simply wrong. Nothing to fix. |
| Bad loss | `D` | `execution_error` | `["LATE_ENTRY","MISSED_TIME_STOP"]` | Process errors caused/worsened the loss. Fixable. |
| Stopped winner-thesis | `B` | `normal_volatility_stop` | `["STOP_TOO_TIGHT"]` | Thesis held; a too-tight stop took you out. |

The `execution_error` ↔ mistake-tags (`reconciliation`/`management`) relationship deserves a note:
the two CAN correlate (an `execution_error` outcome often co-occurs with execution-flavored mistake
tags), but they answer different questions — `failure_mode` is the single **bucket** ("the loss was
attributable to execution"), `mistake_tags` is the **granular catalog** ("specifically:
`LATE_ENTRY`, `MISSED_TIME_STOP`"). Correlation is expected and fine; the orthogonality is of
*purpose and computation*, not of statistical independence. The contract's test (§7) asserts the
*computational* separation, not an impossible zero-correlation.

---

## §7 Test strategy + the operator browser gate

### §7.1 Automated tests

1. **Migration round-trip + strict backup-gate** — `run_migrations` v23 → v24 adds the column;
   re-running is a no-op (run-migrate-twice idempotency, mirroring the risk_policy + chart-rename
   precedent); the `_b7_backup_gate` fires on `current==23 AND target>=24` and is bypassed from a
   pre-v23 baseline. Assert `EXPECTED_SCHEMA_VERSION == 24`.
2. **CHECK + frozenset + validator consistency (#11)** — every token in `FAILURE_MODES` inserts
   cleanly; a non-member raises (SQL CHECK) AND `Trade(failure_mode="bogus")` raises (`__post_init__`).
   The two vocabularies are asserted identical (the migration's CHECK list == `FAILURE_MODES`) via a
   test that parses the migration or asserts the round-trip for all 7.
3. **Read-mapper parity** — `_row_to_trade` returns `failure_mode` for a v24 row; a pre-v24 fixture
   (run_migrations target < 24) reads `failure_mode = None` via the `_TRADE_SELECT_COLS_PRE_V24`
   projection (no `no such column` raise).
4. **POST persistence ladder** — empty submit → `NULL` persisted (the `... or None` empty-field
   test); a valid token → stored; an invalid token → `400` + re-render (NOT 500). Success → `204` +
   `HX-Redirect`.
5. **Orthogonality test (L2)** — a trade with `process_grade='A'` carries a non-NULL `failure_mode`,
   and a trade with a non-NULL `failure_mode` is unaffected in its computed grade; `compute_process_grade`
   has no `failure_mode` parameter; `failure_mode` is absent from `MISTAKE_TAGS` and from the
   mistake-tag frequency aggregation.
6. **Read-back** — a reviewed trade's chronology `_review_entry` detail includes the failure-mode
   label; chronology fixtures migrated to v24.
7. **`complete_trade_review` signature** — the new keyword-only `failure_mode=None` default keeps
   existing CLI callers green; passing a value writes it atomically with the other 10 fields + the
   `closed → reviewed` transition.
8. **ASCII (#16/#32)** — no non-ASCII glyph in any new user-facing string (labels use plain hyphens,
   not em-dashes, in any CLI path; the form uses `&mdash;` HTML entity, which is browser-rendered, not
   stdout-encoded).

### §7.2 The operator-witnessed browser gate (BINDING — L6)

The review form is HTMX; TestClient cannot detect the browser-only failure surfaces (`hx-headers`
OriginGuard 403; `204`+`HX-Redirect` vs `303`-swallow). The binding acceptance gate is an
**operator-driven real-browser submit**:

1. Open a real closed-but-unreviewed trade's `/trades/{id}/review` page in a browser.
2. Select a failure mode (e.g. `thesis_invalidated`), fill the required fields, submit.
3. Confirm the browser navigates to `/reviews/pending` (the `HX-Redirect` fired) — NOT a swap, NOT a
   stuck form.
4. Confirm the value persisted (DB probe `SELECT failure_mode FROM trades WHERE id=...`).
5. Confirm the chronology read-back displays it.
6. **Unseeded default state** (memory `feedback_seeded_gate_masks_default_state`): also witness a
   submit that LEAVES the control blank → confirm `NULL` persists and the read-back shows no
   failure-mode line. The blank/winner path is the common case and must be witnessed too.

---

## §8 Schema impact (v23 → v24)

- **First migration since the schwabdev arc.** The schwabdev v3 + Fernet arc made NO swing-DB schema
  change; the last bump was v22 → v23 (SB3 chart-surface rename, `edd098d`). B-7 is the next, v23 →
  v24.
- **Migration 0024** — a single nullable CHECK column add (no table rebuild). `BEGIN; ALTER …;
  UPDATE schema_version SET version = 24; COMMIT;` (gotcha #9).
- **Strict backup-gate** — `_b7_backup_gate`, `current_version == 23 AND target_version >= 24`,
  mirroring `_phase14_sb3_backup_gate`. Re-exercises the backup machinery dormant since v23.
- **No multi-version jump** — v24 only (OUT-of-scope: any multi-step walk; strict gate enforces it).
- **Operator live-DB migration** — the operator's live v23 DB migrates to v24 at ship, exactly as it
  migrated v22 → v23 at SB3. Existing trade rows get `failure_mode = NULL` (forward-only, OQ-6).

---

## §9 Sub-bundle / slice recommendation

A single cohesive feature; recommend **one bundle, two slices** (the #11 atomic-consistency boundary
makes the schema+model+repo slice indivisible):

- **Slice A — schema + model + persistence (the #11 atomic task).** Migration 0024 + backup-gate +
  `EXPECTED_SCHEMA_VERSION` bump + `FAILURE_MODES` + `Trade.failure_mode` + validator + read/write
  mapper widening + `update_trade_review_fields` + `complete_trade_review` params. All of §4 lands
  together, tested by §7.1 #1–3,7. (TDD per task.)
- **Slice B — the web surface.** The form fieldset + VM `failure_mode_choices` + POST handler
  validate/thread + the chronology read-back. Tested by §7.1 #4–6, gated by §7.2 (browser).

Slice B depends on Slice A (the column must exist before the form persists into it). Within each
slice, TDD per the project convention (failing test → minimal impl → commit).

---

## §10 V1 simplifications + V2 candidates

**V1 simplifications (deliberate, per L1):**
- Single-select, single column — no multi-select, no side-table (OQ-3 deferred).
- Capture-only — NO analysis/distribution surface (OQ-5 deferred).
- Forward-only — existing reviewed trades stay `NULL`, no backfill prompt (OQ-6).
- Web review form only — the CLI review path passes the `None` default; no CLI prompt in V1.
- Optional at submit — no required-on-loss gate (OQ-7 default).

**V2 candidates (explicitly out of V1):**
- **The failure-mode analysis surface** (OQ-5) — a distribution tile on the trade-process metrics
  card (the natural home: [`trade_process_card.html.j2`](../../../swing/web/templates/metrics/trade_process_card.html.j2)
  already renders mistake-tag frequency; a parallel "failure-mode frequency" table is the obvious
  follow-on). This is the *reason the feature exists* and should be the immediate next arc.
- **Multi-select failure modes** (OQ-3) — if the operator finds single-cause too coarse, migrate to a
  JSON-list (like `mistake_tags`, losing the CHECK) or a `trade_failure_modes` side-table.
- **CLI review-path solicitation** — a `--failure-mode` option on the CLI review command.
- **Required-on-loss gate** (OQ-7) — outcome-conditional requirement if the operator wants it.
- **An optional free-text `failure_mode_note`** companion column — deferred; `lesson_learned` covers
  narrative for now (weighed under OQ-1 per brief §7; not needed in V1).

---

## §11 Operator decision items (the OQs)

| OQ | Question | Recommendation | Status |
|----|----------|----------------|--------|
| **OQ-1** | Schema shape: new nullable `failure_mode` column → v24, vs reuse / free-text / side-table. | **New nullable CHECK column → v24** (§4). | **Operator-binding (the first v24).** |
| **OQ-2** | Solicitation scope: losing/scratch-only vs always-solicited + sentinel. | **Always-shown, optional, nullable; NULL = winner/unattributed; NO sentinel** (§5.2). | **Operator UX — flagged.** |
| OQ-3 | Cardinality: single primary vs multi-select. | **Single-select** (§4.2, §10). | Deferred to V2. |
| **OQ-4** | The exact vocabulary (value set + labels). | **The 7-value set in §3.2** — operator's own attribution language. | **Operator-binding — flagged.** |
| OQ-5 | Read/analysis surface in V1? | **No — capture-only; analysis tile is the next arc** (§10). | Deferred (recommend immediate follow-on). |
| OQ-6 | Backfill existing reviewed trades? | **Forward-only; existing rows stay NULL** (§8). | Recommended; low-stakes. |
| **OQ-7** | Required-or-optional at submit. | **Optional** (§5.3). | **Flagged for operator.** |

The four **bolded** OQs (OQ-1 schema/v24, OQ-2 solicitation, OQ-4 vocabulary, OQ-7 required/optional)
are the operator-triage items the brief calls out for explicit sign-off at writing-plans.

---

## §12 Cumulative-discipline compliance

- **Migration discipline** — gotcha #9 (explicit `BEGIN;…COMMIT;`), #11 (CHECK + frozenset +
  validator + read/write mapper in ONE task — §4.3), strict backup-gate `pre_version == target-1`
  (§4.4), run-migrate-twice no-op test (§7.1 #1), schema-version-aware read/write via PRAGMA
  (`_TRADE_SELECT_COLS_PRE_V24` + SVAI).
- **Form discipline (L6)** — `hx-headers HX-Request` (inherited from the existing form root), `204` +
  `HX-Redirect` success, `400` + re-render validation ladder, the server-stamped
  `auto_populated_field_keys_json` envelope untouched, `... or None` for the nullable CHECK column,
  the operator-witnessed browser gate (§7.2).
- **Nullable-CHECK** — `... or ""` would collide with the CHECK (empty string is not a member); use
  `... or None` (§5.4) + the empty-field-persists-NULL test (§7.1 #4).
- **base.html.j2 5-VM rule** — `failure_mode_choices` is referenced only in `review_form.html.j2`;
  the plan verifies no base-layout deref (§5.5).
- **ASCII (#16/#32)** — labels use plain hyphens in any stdout path; the form uses HTML entities
  (browser-rendered) (§7.1 #8).
- **Commits** — conventional, ZERO `Co-Authored-By`, no `--no-verify`, final `-m` paragraph plain
  prose (trailer-parse hazard); `%(trailers)` verified `[]` before push.
- **L2/L3** — orthogonality contract (§6) + the explicit phase-isolation carve-out (§2 L3).
- **No Schwab / L2-lock surface touched** — B-7 is review-only; the Schwab source-grep baseline is
  untouched.

---

## §13 Position note

B-7 is the **second commissioned Phase-15 arc** (after the schwabdev-v3 + Fernet arc). It is a small,
focused **capture-only** feature: one nullable column, one form control, one read-back line — but it
carries the weight of being the **first v24 migration**, re-exercising the backup-gate + #11
atomic-consistency machinery that has been dormant since v23. The deliberate V1 boundary is *capture
without analysis*: the operator starts accumulating attribution data immediately, and the
failure-mode **analysis surface** (the distribution tile on the trade-process metrics card) becomes
the natural next arc — at which point the data captured here pays off. The orthogonality contract
(§6) is the load-bearing design idea: it keeps "why the trade failed" cleanly separable from "how
well the operator executed," so a "good loss" and a "bad loss" become distinguishable in the data
for the first time.

---

*End of spec. B-7 operator failure-mode classification — the post-trade failure-mode CAPTURE
surface: a tight 7-value CHECK-constrained `failure_mode` enum on `trades` (new nullable column →
the first v24 migration), the review-form control, persistence through `complete_trade_review`, and
the chronology read-back — kept ORTHOGONAL to process-grade and the mistake-tags vocabulary.
Capture-only V1; the analysis surface is the next arc. The binding gate is an operator-witnessed
browser submit on a real closed trade.*
