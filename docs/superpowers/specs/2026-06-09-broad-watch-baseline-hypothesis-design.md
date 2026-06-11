# Broad-Watch-Baseline Hypothesis — Registry Amendment — Design Spec

**Phase:** copowers:brainstorming (design only — do NOT implement).
**Authored:** 2026-06-09. **Commission:** `docs/broad-watch-baseline-hypothesis-brainstorming-dispatch-brief.md`.
**Governance route:** V2.1 §VII.F source-of-truth correction protocol — a formal amendment to the frozen
`hypothesis_registry` via a NEW migration with an explicit version bump (migration `0026`, schema v25→v26).
This arc *exercises* the freeze contract's amendment path; it does not break it.

**Plugs into:** `docs/superpowers/specs/2026-06-08-shadow-expectancy-engine-design.md` (the engine's funnel/attribution
vocabulary) and `docs/superpowers/specs/2026-06-09-shadow-expectancy-entry-join-correction-design.md` (the
`candidate.pivot` entry-recompute + per-hypothesis terminal routing this amendment feeds population into).

---

## 1. Problem (the attribution-coverage finding, 2026-06-09)

The shadow-expectancy engine is SHIPPED + corrected (merge `31e7441c`) and runs turnkey, but prices ≈zero.
Latest live run (`exports/research/shadow-expectancy-20260610T063533Z/summary.md`): 210 detections → 42 unique
signals → **42/42 `matched_no_hypothesis`**, zero priced. The funnel is honest; the bottleneck is *attribution
coverage*.

**Root cause:** all 42 live signals are `bucket == watch` with assorted non-pass sets. The active narrow cohorts
do not cover them:
- H2 `Near-A+ defensible: extension test` requires non-pass set **exactly** `{proximity_20ma}`.
- H4 `Capital-blocked: smaller-position test` requires non-pass set **exactly** `{risk_feasibility}` (bucket `watch`
  or `skip`).
- H1 `A+ baseline` requires `bucket == aplus` (zero aplus in the log).
- H3 `Sub-A+ VCP-not-formed` is `closed-target-met` (not loaded by the engine, which filters `status='active'`).

The Phase-15 #23 pool-widening deliberately made the temporal log accrue the **broad watch population** (~83× the
aplus population) as forward-walk data. The registry predates that widening — no hypothesis was ever registered for
the population the log now contains, which is *also the operator's actual trading practice* (12 of 16 live trades
were watch).

**The amendment:** register a fifth pre-registered hypothesis — a **broad-watch baseline** (`bucket == watch`, any
non-pass set, not otherwise hypothesized) — so the engine prices that population.

**Honest caveat carried into the design (necessary, not sufficient):** even with coverage, priced samples accrue
only as the log matures and names break out over their `candidate.pivot`. As of this run every `candidate.pivot`
sits above its forward highs in the thin 2–3 session windows → zero breakouts → the fix routes attribution
correctly but still prices ≈zero today. The success criterion is **attribution-routes-correctly**, not immediate
expectancy numbers (§7).

---

## 2. The registry row — FROZEN pre-registration (migration 0026, verbatim)

This is the exact content as it will appear in `swing/data/migrations/0026_broad_watch_baseline.sql`. The
`name`/`statement`/`target_sample_size`/`decision_criteria`/`consecutive_loss_tripwire`/`absolute_loss_tripwire_pct`
fields are FROZEN at this migration per the 0008 freeze contract; only `status` (+ its audit columns) may be
mutated later via the sanctioned CLI/service path.

> **Note on formatting:** `||` below is SQLite string-literal concatenation used purely for line-wrapping in this
> doc — the STORED value is the single concatenated string with NO embedded newlines. The implementer may equally
> use one long single-line literal per field (0008's style); the literal *text* is what is frozen, not the wrapping.

```sql
-- Migration 0026: broad-watch-baseline hypothesis (V2.1 §VII.F amendment).
-- ADDITIVE. The four frozen H1–H4 rows from 0008 are UNTOUCHED. INSERT OR IGNORE
-- keyed on the UNIQUE `name` column (mirrors 0008) so a re-run is a no-op.
-- Explicit BEGIN;...COMMIT; per gotcha #9 (executescript runs in autocommit;
-- _apply_migration does NOT open its own transaction — 0023/0024/0025 all wrap).
-- Load-bearing here: the history INSERT…SELECT below is NON-idempotent, so a
-- mid-script failure must roll back the registry insert too.
BEGIN;
INSERT OR IGNORE INTO hypothesis_registry
  (name, statement, target_sample_size, decision_criteria,
   consecutive_loss_tripwire, absolute_loss_tripwire_pct, created_at, notes)
VALUES
  ('Broad-watch baseline',
   'The widened watch pool (bucket==watch, any non-pass set, not matching a '
   || 'narrower active hypothesis), priced by the mechanical shadow ruleset, '
   || 'establishes the baseline expectancy of the population the temporal log '
   || 'contains and the operator actually trades.',
   30,
   'SHADOW-measured (not closed live trades): primary read = realistic bracket '
   || 'arm on the closed_only and mtm_at_horizon censoring scenarios at N>=30 '
   || 'priced shadow signals; report mean R + Wilson lower-bound win rate across '
   || 'all four censoring scenarios. Pre-registered as a BASELINE: negative or '
   || 'zero mean R is a bankable validation of A+ gate selectivity; positive mean '
   || 'R triggers cohort-refinement research (which miss-sets carry the edge), '
   || 'NOT direct deployment.',
   5, 5.0, '2026-06-09',
   'Measurement substrate is the shadow-expectancy engine '
   || '(research/harness/shadow_expectancy), not labeled live trades. The baseline '
   || 'cohort = watch signals NOT otherwise matching a narrower active hypothesis '
   || '(the honest complement, via fallback matching). Surfaced by the production '
   || 'matcher ONLY in shadow/measurement context (opt-in); live recommendation '
   || 'surfaces never surface it. Tripwires apply only if the operator labels live '
   || 'watch trades with this hypothesis (permitted; matches practice). Not an '
   || 'operator recommendation cohort. Registry amendment via migration 0026 per '
   || 'V2.1 §VII.F.');

-- Seed the initial OPEN status-history interval for the new row, mirroring
-- migration 0017's per-row seed (0017_phase9_…:306-321). Without this the
-- governance/progress timeline (hypothesis_progress_card transition_timeline,
-- list_history_for_hypothesis) is EMPTY until the first status transition.
-- Scoped to the new row only (the four frozen rows already have their 0017
-- seed — UNTOUCHED). recorded_at uses the same strftime('now') shape as 0017.
INSERT INTO hypothesis_status_history
  (hypothesis_id, status, effective_from, effective_to, change_reason, recorded_at)
SELECT id, status,
       strftime('%Y-%m-%dT00:00:00.000', created_at), NULL, NULL,
       strftime('%Y-%m-%dT%H:%M:%f', 'now')
FROM hypothesis_registry
WHERE name = 'Broad-watch baseline';

UPDATE schema_version SET version = 26;
COMMIT;
```

The `hypothesis_status_history` partial-unique "current interval" index (one open `effective_to IS NULL` row per
hypothesis, from 0017) is satisfied — this INSERT creates exactly one open interval for the new id. Idempotency: a
re-run after the `INSERT OR IGNORE` no-ops the registry row, but the history `INSERT … SELECT` would create a SECOND
open interval on re-run → the migration runner's version-gate (`current >= target` short-circuit, `db.py:1153-1155`)
prevents 0026 from re-executing once `schema_version=26`, so this is safe. The run-migrate-twice test (§7.1) asserts
exactly ONE history row for the new hypothesis.

**Tripwire columns** (`consecutive_loss_tripwire=5`, `absolute_loss_tripwire_pct=5.0`) are schema-mandated
`NOT NULL CHECK (> 0)` (0008) and must carry values even though the PRIMARY measurement is shadow-side. They become
meaningful only if the operator labels live watch trades with this hypothesis (§5.3) — a permitted secondary use.
Values mirror H2/H4's `5.0` absolute and a `5`-loss streak (the broad cohort is the loosest, so the loosest
consecutive threshold is appropriate).

**`target_sample_size = 30`** mirrors the V2.1 §VII shadow-mode ≥30-signal promotion gate. Its UNIT is **priced
shadow signals**, authoritatively read from the engine's `summary.md` scorecard — NOT the DB trade-progress
surfaces (see §5.2 for the dual-read).

---

## 3. The matcher rule — two-phase fallback + opt-in containment

Two orthogonal mechanisms, in `swing/recommendations/hypothesis.py`:

### 3.1 Fallback / complement semantics (resolves §3.1)

The brief's load-bearing risk: a naive `bucket == "watch"` predicate **overlaps H2/H4** → the matcher multi-matches
→ the engine routes `len(hyps) > 1` → `multi_match` → **unattributed (DROPPED)** (`run.py` ~L121). Naive overlap
would cannibalize the narrow cohorts' attribution the moment their signals appear.

**Resolution — a STRUCTURAL two-phase matcher (NOT a flat ordered rules list):**

1. **Narrow phase.** Evaluate the four existing rules (H1–H4) exactly as today. These rules are *mutually exclusive
   on `watch` by construction*: H2 requires non-pass `== {proximity_20ma}`; H4 requires non-pass `== {risk_feasibility}`;
   H3 requires a `{tightness, vcp_volume_contraction}` trigger in the non-pass set → its non-pass set can never equal
   either singleton. So multi-match *among the narrow rules* effectively never occurs (it would be a genuine
   substrate-integrity signal if it ever did).
2. **Baseline phase.** The broad-watch rule fires **iff (a) the caller opted in AND (b) the narrow phase returned
   ZERO matches.** Implemented as an explicit gate `if include_baseline and not matches:`, NOT as list position.
   Order within the narrow phase is irrelevant to correctness — the gate is on the *emptiness of `matches`*, not on
   where the baseline rule sits in any list. This is order-robust by construction (answers the brief's "without
   making the rules list order-fragile" sub-question).

**Net (in the engine context, `include_baseline=True`, baseline row active+present):** every `watch` signal
attributes to **exactly one** hypothesis — a narrow one if it fits, else the baseline. (In the live context,
`include_baseline=False`, a pure-baseline watch signal gets **zero** matches — that is the containment, §3.2, not a
gap.) `multi_match → unattributed` stays a real substrate-integrity signal rather than becoming routine, so H2/H4
shadow attribution is provably protected (resolves the §2.2 cannibalization hazard).

**Cohort meaning (state in pre-registration — done, §2 statement):** the baseline cohort is the **honest complement**
— "watch signals NOT otherwise matching a narrower *active* hypothesis" — NOT a superset of H2/H4. The membership is
defined against the **active** narrow rules, which is load-bearing given the real watch-pool composition (verified
against the live DB 2026-06-09, recent watch candidates):

H3's exact predicate (`_sub_aplus_vcp_not_formed_match`, `hypothesis.py:223-236`): a `{tightness, vcp_volume_contraction}`
trigger in the non-pass set AND the **entire** non-pass set ⊆ `DOCTRINE_DEFENSIBLE_MISS_SET ∪ {tightness, vcp_volume_contraction}`
where `DOCTRINE_DEFENSIBLE_MISS_SET = {TT8_rs_rank, risk_feasibility, proximity_20ma}`. So a set containing ANY
criterion outside that allowed union (e.g. `adr`, `orderliness`, `ma_short_rising`) does **NOT** match H3, even if it
contains `tightness`.

| Non-pass set (sample) | count | H3 predicate? | routes to (today, H3 closed) |
|---|---|---|---|
| `{proximity_20ma, tightness}` | 110 | YES (proximity∈defensible) | **baseline** (H3 not active) |
| `{adr, tightness}` | 61 | **NO** (`adr` not allowed) | **baseline (regardless of H3)** |
| `{tightness, vcp_volume_contraction}` | 60 | YES | **baseline** |
| `{tightness}` | 36 | YES | **baseline** |
| `{adr}` | 15 | NO (no trigger) | **baseline (regardless)** |
| `{orderliness, tightness}` | 15 | **NO** (`orderliness` not allowed) | **baseline (regardless)** |
| `{TT8_rs_rank, adr, tightness}` | 10 | **NO** (`adr` not allowed) | **baseline (regardless)** |
| `{proximity_20ma}` (H2-exact) | **1** | — (H2 matches) | `Near-A+ extension` |
| `{risk_feasibility}` (H4-exact) | **0** | — (H4 matches) | (none observed) |

H3 is `closed-target-met`, so the engine (`status='active'` filter) never loads it and even its TRUE matches fall to
the **baseline** today. **The broad cohort's exact membership flips on H3's active-status — but only for the
H3-eligible subset:** if H3 were re-activated, the `tightness`/`vcp`-with-allowed-defensible sets
(`{proximity_20ma,tightness}`, `{tightness,vcp_volume_contraction}`, `{tightness}`, …) would reclaim to H3, while the
sets carrying a non-allowed criterion (`{adr,tightness}` 61, `{orderliness,tightness}` 15, `{TT8_rs_rank,adr,tightness}`
10, `{adr}` 15, …) stay baseline **regardless of H3**. This is the complement semantics working as designed; the
pre-registration statement ("not matching a narrower active hypothesis") captures exactly this, and the H3-flip
fixture (§9.1.4) must use an H3-*eligible* set so it actually exercises the flip.

On today's live data (H1/H2/H4 active, H3 closed) the H2/H4-exact matches are ≈0 (1 H2, 0 H4 across 400 recent watch
rows), so baseline ≈ the whole watch pool — but the semantics are correct for the data to come.

The broad-watch rule predicate itself:

```python
def _broad_watch_baseline_match(candidate: Candidate) -> bool:
    """Watch bucket, any non-pass set. The fallback gate (caller-side, on
    `not matches`) — NOT this predicate — enforces the complement semantics."""
    return candidate.bucket == "watch"
```

A new name constant `H_BROAD_WATCH_BASELINE = "Broad-watch baseline"` joins the existing four at the
`hypothesis.py` ~L124 extension point.

### 3.2 Opt-in containment for live recommendation surfaces (resolves §3.2, mechanism A)

`match_candidate_to_hypotheses` gains a keyword-only `include_baseline: bool = False`. The baseline phase fires only
when `include_baseline=True`.

- **Engine path** (`research/harness/shadow_expectancy/attribution.py`) passes `include_baseline=True`. This is the
  ONLY caller that opts in.
- **Live recommendation call sites are untouched-by-construction** (default `False`): `dashboard.py` ~L540 and
  ~L1061 (`match_candidate_to_hypotheses(c, registry=registry)`), and `hypothesis_prefill.py:55`
  (`lookup_active_recommendation_label`). None pass `include_baseline`, so the baseline rule never fires for them →
  it cannot put a recommendation row on every watch ticker and cannot outrank H2/H4 via `distance_to_target` in
  `prioritize_recommendations`.

**Containment decision (operator-confirmed 2026-06-09): mechanism (A) — opt-in only, NO new registry column.**

Rationale for rejecting the `measurement_only`-column alternative (brief §2.3(a)) in V1:
- The matcher opt-in fully contains the *recommendation* surfaces. The *registry-reading* surfaces (§5) read the
  registry directly, not the matcher, and split cleanly: the **progress/process** surfaces are **coherent** with a
  5th cohort because live-labeling is PERMITTED (§5.3) — their `X/30` is a meaningful "live-labeled trades / target"
  read, identical in kind to H1's `1/20`, so there is nothing to filter; the **tier/deviation** surfaces
  **auto-exclude** the 5th row via their existing 4-name allowlist (§5.2), which is the desired behavior. Either way a
  containment column would buy nothing these surfaces actually need.
- A column adds schema surface + a #11 multi-mirror sweep (`models.py` dataclass field, `repos/hypothesis.py`
  `_row_to_entry` + `_SELECT_COLUMNS`, the inline column-list SELECTs in `hypothesis_progress_card.py` ~L420 and
  `tier.py` ~L464, plus every surface) for a generalization (multiple measurement-only hypotheses) that is purely
  speculative.
- `status` cannot double as the flag: the engine *requires* `status='active'` to load the row
  (`list_hypotheses(conn, status_filter="active")`, `run.py` ~L55), so "measurement-only" cannot be expressed as a
  status. A dedicated column would be the only clean encoding — and it is unnecessary per the first bullet.
- If a SECOND measurement-only hypothesis is ever registered, the column becomes worth it then. YAGNI for V1.

This keeps the production-touch carve-out exactly as the brief scoped it (§8).

---

## 4. Attribution wrapper change (engine side)

`research/harness/shadow_expectancy/attribution.py:attribute_hypotheses` passes the opt-in through:

```python
matches = match_candidate_to_hypotheses(
    candidate, registry=list(registry), include_baseline=True,
)
```

No other engine change. `run.py`'s funnel logic, `constants.py` reason vocabularies, the simulator, the bracket, and
the scorecard are **UNCHANGED** — the fallback semantics requires no new funnel reason. (The brief's hard constraint:
if the design required a funnel change, that would be a red flag; it does not.) The L2 forbidden-import test stays
green (no new production dependency; `attribution.py` already imports the production matcher).

---

## 5. Consumer enumeration & behavior with a 5th active row (resolves §3.2 enumeration)

Two families. The matcher opt-in governs Family 1; Family 2 reads the registry directly — the progress/process
surfaces ACCEPT the 5th cohort, while tier/deviation AUTO-EXCLUDE it via their 4-name allowlist (the desired split).

### 5.1 Family 1 — matcher-driven (live recommendation) surfaces — CONTAINED by `include_baseline=False`

| Consumer | Behavior with the 5th row |
|---|---|
| `swing/web/view_models/dashboard.py` ~L540 (recommendations build) | default `False` → baseline rule never fires → no extra recommendation rows. Unchanged. |
| `swing/web/view_models/dashboard.py` ~L1061 (2nd matcher call) | same — unchanged. |
| `swing/recommendations/hypothesis_prefill.py:55` (CLI/web entry-form pre-fill) | default `False` → never pre-fills the baseline label. Unchanged. |
| `prioritize_recommendations` | never receives a baseline match (matcher didn't emit it) → no ranking impact. Unchanged. |

### 5.2 Family 2 — registry-reading surfaces — progress/process ACCEPT the 5th cohort; tier/deviation AUTO-EXCLUDE it

| Consumer | Behavior with the 5th row |
|---|---|
| `swing/web/view_models/metrics/hypothesis_progress_card.py` (`build_hypothesis_progress_card_vm`, SELECT all rows `ORDER BY id`) | Renders a 5th cohort card. `n_closed` = live trades labeled `Broad-watch baseline …`; `progress_pct = n_closed/30` (`hypothesis_progress_card.py:354-357`). With zero live labels it shows `0/30, 0%`. The card carries `decision_criteria` VERBATIM (`CohortProgressVM.decision_criteria`), which begins `"SHADOW-measured (not closed live trades)…"` — but it sits in a `<details>` block (`hypothesis_progress_card.html.j2:48-50`), COLLAPSED by default, while the `0/30` bar is at `:26-31` (Codex R2-M4). So the unit caveat is available-on-the-card but hidden-until-expanded, not literally beside the bar. ACCEPTED for V1 (§3.3 residual-risk acceptance). The "every registered cohort MUST appear" invariant already holds. |
| `swing/metrics/cohort.py:count_per_cohort` + `swing/web/view_models/metrics/trade_process_card.py` (process-by-cohort tabs, "every cohort including registry cohorts at n=0") | `count_per_cohort` returns counts for ALL registry rows (+orphans) → the trade-process card gains a 5th cohort tab (`0` closed until labeled). ACCEPTED (coherent live-labeled read; the card explicitly includes n=0 cohorts). Test sweep: `tests/web/test_view_models/test_trade_process_card_vm.py`, `tests/web/test_routes/test_metrics_routes.py`. |
| `swing/metrics/tier.py` (`compute_tier_comparison` / `compute_deviation_outcome`) | **AUTO-EXCLUDED — no change, by design.** tier is hard-locked to a 4-name allowlist `TAXONOMY_COHORTS` (`tier.py:87-92`); `TierComparisonResult.__post_init__` RAISES unless `cohorts == TAXONOMY_COHORTS` exactly (`tier.py:310-323`); the compute iterates `TAXONOMY_COHORTS`, not all registry rows. The 5th row is loaded as unused metadata and never rendered as a cohort. This is the DESIRED outcome: a shadow/measurement baseline does NOT belong in a live-trade A+-relative *deviation* comparison. **`test_tier.py`'s `== 4` STAYS 4** (do NOT bump); the "taxonomy-locked to 4" comment stays correct. tier.py is therefore self-containing WITHOUT a `measurement_only` column. |
| `swing/journal/stats.py:compute_hypothesis_progress_breakdown` (one row per registered hypothesis) | Emits a 5th progress row (live-labeled count vs target 30). Deterministic registry-order render. ACCEPTED. |
| `swing/cli.py` `hypothesis list` / `hypothesis status` (`list_hypotheses` + `compute_tripwire_status`) | Lists the 5th row + its tripwire status (computed from live labeled trades). ACCEPTED. |
| `swing/cli.py` journal progress section (`render_hypothesis_progress`) | Renders the 5th line. ACCEPTED. |
| `swing/trades/hypothesis.py` status-transition service | Additive — no interaction; the new row is independently status-mutable via the same audit path (which synthesizes predecessor history; see §7's `hypothesis_status_history` seed). |

**§3.2 sub-question — what `0/30` means for a shadow-measured hypothesis (suppress / annotate / accept):**
**ACCEPT, with operator-visible annotation (NOT merely a spec note).** The DB trade-progress surfaces read
`target_sample_size=30` as a **live-closed-labeled-trade** target (their existing semantics); for this row that is a
*secondary* read tracking any live watch trades the operator labels. The **authoritative** shadow measurement (N≥30
priced *shadow signals*) lives in the engine's `summary.md` / `manifest.json` scorecard, NOT in any DB surface. The
caveat lives in the row's FROZEN `decision_criteria` text (`"SHADOW-measured (not closed live trades)…"`), which the
web progress card carries — but in a `<details>` block collapsed by default (Codex R2-M4), and the CLI
`hypothesis list`/`status` one-liners + `journal` progress section show `X/30` without the full criteria text at all.
**So the unit caveat is available-on-the-surface but NOT guaranteed visible at the point of display.** **Residual risk
EXPLICITLY ACCEPTED for V1** (single operator who authored the hypothesis; the authoritative shadow read is one
`summary.md` away) rather than add a `measurement_only` column, a per-surface unit-flag, or a template change to
surface the caveat uncollapsed. **Deferred enhancement (noted, not specified):** a tiny inline unit-tag (e.g. a
`shadow-measured` chip beside the bar for cohorts whose `decision_criteria` starts with `SHADOW-measured`) would make
it always-visible at low cost — pull it in if/when a second measurement-only hypothesis lands and the machine-readable
unit flag is reconsidered.

### 5.3 Live-labeling — PERMITTED (resolves §3.3)

The operator MAY label live watch trades with `Broad-watch baseline …`. Permitting it (a) gives the schema-mandated
tripwires meaning, (b) matches the operator's actual practice (12/16 live trades were watch), and (c) makes the
Family-2 governance display coherent (it's a real cohort with a real, if secondary, progress count). The descriptive
label builder (`_descriptive_label`) already emits `"<name> (watch); failed: …"`, which matches the registered name
via the space-delimiter rule of the 3-rule contract (§6). No change needed to support labeling.

---

## 6. Name / label-matcher safety (resolves §3.4)

`'Broad-watch baseline'` checked against the 3-rule delimiter-aware contract
(`swing/metrics/label_match.py:label_matches_hypothesis`: exact-equal, or `name + " "` prefix, or `name + ";"`
prefix) vs each of the four existing names, **both directions**:

| Existing name | `'Broad-watch baseline'` collide? |
|---|---|
| `A+ baseline` | No. Neither is a delimiter-prefix of the other. (Shared word `baseline` is a *suffix* of `A+ baseline` — the contract is PREFIX-based, so suffix overlap is irrelevant.) |
| `Near-A+ defensible: extension test` | No shared prefix. |
| `Sub-A+ VCP-not-formed` | No shared prefix. |
| `Capital-blocked: smaller-position test` | No shared prefix. |

No prefix collision in either direction → no cohort-attribution cross-talk. The SQL helper
(`label_matches_hypothesis_sql`) inherits the same safety (same contract). A regression test asserts
`label_matches_hypothesis('Broad-watch baseline …', other_name) is False` for all four others, and the reverse.

---

## 7. Migration mechanics (resolves §3.5)

- **File:** `swing/data/migrations/0026_broad_watch_baseline.sql`. Single `INSERT OR IGNORE` (keyed on UNIQUE `name`,
  mirroring 0008) + `UPDATE schema_version SET version = 26;`. Plain SQL, no `ALTER` (additive row insert only — the
  registry table is unchanged; consistent with mechanism (A)'s no-column decision).
- **`EXPECTED_SCHEMA_VERSION`** in `swing/data/db.py` bumps `25 → 26`.
- **Backup gate — STRICT equality.** Add `_broad_watch_baseline_backup_gate` (registered in `run_migrations`)
  mirroring `_phase16_backup_gate`'s shape: fires ONLY when `current_version == 25 AND target_version >= 26` (NOT
  `<=`; multi-version jumps must be separate two-step migrations per the CLAUDE.md gotcha). Snapshots a real
  file-backed v25 DB before crossing v26; in-memory connections raise `MigrationBackupRequiredException`.
  **Expected-tables constant (Codex R2-M2 correction):** the v25 pre-0026 table set is NOT
  `PHASE16_PRE_MIGRATION_EXPECTED_TABLES` — that constant is the **v24** set and intentionally EXCLUDES
  `pipeline_step_timings` (`db.py:221-225`, the table 0025 creates). Define the new constant as
  `PHASE16_PRE_MIGRATION_EXPECTED_TABLES | {"pipeline_step_timings"}` (the true v25 table set), with a provenance
  comment mirroring the existing derived-set convention. 0026 adds NO table, so the v26 post-migration table set
  equals the v25 set (the integrity check verifies the snapshot has the expected v25 tables).
- **Run-migrate-twice no-op test.** Apply 0026 twice on the same DB → second run is a no-op (`INSERT OR IGNORE` on
  the UNIQUE name; version already 26). Asserts exactly ONE `Broad-watch baseline` row and no duplicate.

### 7.1 #11 sweep — hardcoded four-hypothesis assumptions (test-only)

Grep of `swing/` + `tests/` surfaced these row-count assertions to update `4 → 5` (or otherwise reconcile). All are
TEST-only, with ONE production exception: `tier.py`/`deviation_outcome.py` are allowlist-locked to 4 cohorts by
design (§5.2), so they are deliberately NOT row-count-agnostic — they exclude the 5th row and must NOT be widened.
Every OTHER registry-reading surface iterates `list_hypotheses` and is row-count-agnostic:

**CRITICAL fixture-vs-live distinction (a self-review correction):** H3's `closed-target-met` status was set on the
**live** DB via an operator CLI action — it is NOT in any migration. A FRESH test DB built from migrations seeds ALL
of H1–H4 as `active` (0008 `status` defaults to `'active'`). Therefore:
- **Live DB at head (v26):** 5 rows, **4 active** (H1/H2/H4/H5; H3 closed).
- **Fresh migrated test DB at head (v26):** 5 rows, **5 active** (H3 still `active` unless the test closes it).

| Location | Current | Action |
|---|---|---|
| `tests/data/test_db_v8.py:48,106` | `len(rows) == 4`, "expected 4 seed rows" | Asserts the **v8** seed. Confirm the test migrates to exactly v8 (its name implies so) → it legitimately STAYS `4` (0026 is v26, never applied here). Do NOT bump unless it actually migrates to head. |
| `tests/data/test_repos_hypothesis.py:35,54` | `len(rows) == 4`, `len(active) == 4` | If built at head: `len(rows) → 5`; `len(active) → 5` for a fresh migrated DB (NOT 4 — H3 is active in fixtures), UNLESS the test explicitly closes H3. Resolve against the test's actual setup. |
| `tests/journal/test_hypothesis_progress.py:111` | `len(rows) == 4` | → `5` if at head. |
| `tests/metrics/test_tier.py:135,156` | `len(result.cohorts) == 4`, `len(result.rows) == 4` | **STAYS `4`** — tier is allowlist-locked to `TAXONOMY_COHORTS` (§5.2); the 5th row is auto-excluded and `TierComparisonResult.__post_init__` would RAISE if it appeared. Do NOT bump; do NOT touch `tier.py`. |
| `tests/integration/test_phase10_bundle_c_e2e.py:243` | `len(result.rows) == 4` | If this is a tier/deviation result → STAYS `4` (allowlist). If it is the hypothesis-progress card / cohort result → `5`. Determine which result type the row asserts. |
| `tests/web/test_view_models/test_trade_process_card_vm.py` (~77-91,137-143), `tests/web/test_routes/test_metrics_routes.py` (~140-154) | per-cohort tab/count assertions | Reconcile to include the 5th process-card cohort (`count_per_cohort` returns all registry rows). |
| `tests/data/test_phase9_hypothesis_seed_verification.py:15`, `tests/data/test_migration_0017.py:404` | prose "4 hypothesis rows" | Update prose; these assert the v17-era seed — keep numeric if pinned pre-26, else reconcile. |

**Docstring/comment sweep (Minor):** `4-cohort` prose in `swing/web/routes/metrics.py` (~70,88,118,266) and the
progress/process-card docstrings update to reflect the 5th cohort. **EXCEPTION:** the tier/deviation docstrings
(`swing/metrics/tier.py:84`, `swing/web/view_models/metrics/tier_comparison.py:7-16`,
`deviation_outcome.py:7-18`) stay "4-cohort" — those surfaces remain allowlist-locked to 4 (§5.2), so their
"4" is still correct.

**Discipline (binding):** each assertion is resolved **version-aware AND active-vs-all-aware** — determine the test's
`target_version` and whether it closes H3; a test pinned below v26 legitimately still sees 4, and a fresh head-built
fixture sees 5 *active*, not 4. Per memory `feedback_regression_test_arithmetic`, compute the expected count under
BOTH the pre-0026 and post-0026 schema to confirm each updated assertion actually distinguishes.

### 7.2 Research testkit (resolves §3.5 testkit note)

`tests/research/shadow_expectancy/testkit.py:13` pins `run_migrations(c, target_version=24, …)` — so the broad-watch
row (v26) is NOT present in engine fixtures by default. **Resolution: bump the shadow-engine testkit to
`target_version=26`** so the seeded 5th row is present + active for attribution tests. This affects only
shadow-engine tests (`tests/research/shadow_expectancy/`).

**Codex R2-M3 correction — an existing engine-wrapper test WILL flip and must be updated (not "still passes"):**
`test_attribution.py:79-86` (`test_no_match_returns_empty`) asserts a `watch` candidate with non-pass `{orderliness}`
returns `[]`. But `attribute_hypotheses` is *exactly* the wrapper this arc changes to pass `include_baseline=True`
(§4), and the testkit now seeds the active baseline row — so that candidate now returns `["Broad-watch baseline"]`.
Required test changes:
- **Update `test_no_match_returns_empty`** → it now asserts the `watch`/`{orderliness}` candidate attributes to
  `["Broad-watch baseline"]` (rename to reflect the new truth, e.g. `test_unmatched_watch_falls_to_baseline`).
- **Preserve a genuine empty-match assertion via a NON-watch fixture** (the `matched_no_hypothesis` funnel reason must
  stay reachable + tested): e.g. a `bucket='skip'` candidate with non-pass `{tightness}` matches no rule even under
  `include_baseline=True` (baseline requires `bucket=='watch'`) → `attribute_hypotheses(...) == []`.
- **Add direct matcher containment tests** at the `match_candidate_to_hypotheses` level: a `watch` candidate yields
  the baseline match under `include_baseline=True` and `[]` (for a pure-baseline shape) under the default `False`.

Other existing attribution tests (the H2/H3/H4-shaped fixtures) are unaffected — the four narrow rules are unchanged
and they assert narrow matches, which the fallback gate leaves intact. (Alternative considered: keep the testkit at
v24 + inject the 5th row via a version-aware helper — rejected as more fragile than a clean migration bump; the bump
keeps fixtures honest against the production schema.)

---

## 8. Production-touch carve-out (this arc's scope)

Wider than the engine arcs' CLI-only lock — stated explicitly per the brief:

- `swing/data/migrations/0026_broad_watch_baseline.sql` — NEW: additive registry row insert + the
  `hypothesis_status_history` open-interval seed for the new row (§2). No `ALTER`, no change to existing rows.
- `swing/data/db.py` — `EXPECTED_SCHEMA_VERSION` bump 25→26 + `_broad_watch_baseline_backup_gate` + expected-tables
  constant + gate registration in `run_migrations`.
- `swing/recommendations/hypothesis.py` — `H_BROAD_WATCH_BASELINE` constant + `_broad_watch_baseline_match`
  predicate + `include_baseline` keyword-only param + two-phase fallback gate.
- `research/harness/shadow_expectancy/attribution.py` — pass `include_baseline=True`.
- Tests (§7.1, §9) + the testkit bump (§7.2) + this spec doc.

**NOT touched:**
- `swing/metrics/tier.py` — **no change.** The allowlist + raising validator auto-exclude the 5th cohort, which is
  the desired behavior (§5.2). (Codex R1-C1 corrected the earlier draft that wrongly proposed a comment bump.)
- `swing/data/models.py`, `swing/data/repos/hypothesis.py`, and the live loaders — i.e. NO `measurement_only` column
  (mechanism (A)).
- `swing/metrics/cohort.py`, `swing/web/view_models/metrics/trade_process_card.py`, `hypothesis_progress_card.py`,
  `journal/stats.py`, `cli.py` hypothesis/journal surfaces — **no code change**; they iterate the registry and
  accept the 5th cohort by construction (only their TESTS update, §7.1).
- **Frozen rows H1–H4 UNTOUCHED** (no UPDATE of frozen fields; H3's `closed-target-met` status stands; their 0017
  status-history seeds untouched). `DOCTRINE_DEFENSIBLE_MISS_SET` untouched. Engine simulator/bracket/funnel/
  scorecard + `constants.py` reason vocabularies UNTOUCHED. No new production dependency.

---

## 9. Acceptance shape & fixture mandate (resolves §3.6, §3.7)

### 9.1 Acceptance shape (§3.6)

Against the live DB after the amendment: `matched_no_hypothesis → ~0` *for the watch population* (the
`matched_no_hypothesis` funnel reason stays REACHABLE + tested for non-watch non-matching signals — e.g. a `skip`
bucket that matches no rule even with the baseline opted in, since the baseline requires `bucket=='watch'`; it is not
a dead reason); all 42 current signals attribute to `Broad-watch baseline` and route to **honest per-hypothesis
terminals** — `never_triggered` (no forward bar reaches
`candidate.pivot`) / `missing_observations` (zero frozen obs) / a censoring terminal — **NOT to priced rows** (no
breakouts yet). **The success criterion is attribution-routes-correctly, not immediate expectancy numbers.**

Golden fixtures (TDD targets for the plan):
1. **Baseline prices end-to-end:** a broad-watch signal (non-pass set NOT matching H2/H4) with a forward bar that
   breaks `candidate.pivot` → attributes to `Broad-watch baseline`, simulates, lands a priced `closed` /
   `open_at_horizon` terminal with a finite realized R. Proves the baseline cohort can reach a priced scorecard row.
2. **H2-shaped signal does NOT fall into the baseline (anti-cannibalization):** a signal with non-pass `=={proximity_20ma}`
   → attributes to `Near-A+ extension` ONLY; the baseline rule does NOT also fire (fallback gate); `len(hyps)==1`;
   NO `multi_match`. The direct test of the §3.1 fallback. (This shape is RARE but real — 1 of 400 recent watch rows.)
3. **H4-shaped signal** (non-pass `=={risk_feasibility}`, bucket `watch`) → `Capital-blocked` ONLY, baseline silent.
4. **H3 active-status flip (the dominant real population):** a `tightness`-bearing signal (e.g. non-pass
   `=={tightness, vcp_volume_contraction}` — the n=60 real shape) → with H3 **active** in the registry attributes to
   `Sub-A+ VCP-not-formed` ONLY (baseline silent, fallback gate); with H3 **closed/absent** (today's live state)
   attributes to `Broad-watch baseline` ONLY. Locks the §3.1 dependence of baseline membership on the *active* narrow
   set — the single most consequential routing case given the live watch composition.
5. **`include_baseline=False` (live path):** a broad-watch signal → ZERO matches (so live recommendation surfaces
   stay empty). Proves containment.
6. **Migrate-twice no-op** (§7.1) + **name-safety** (§6) regression tests.

### 9.2 Fixture mandate — REAL emitter shapes (§3.7, non-negotiable; standing data-shape discipline)

- Candidate fixtures MUST carry **real** non-pass sets pulled from live `candidates` rows — real `criterion_name`
  vocabulary (e.g. `proximity_20ma`, `risk_feasibility`, `tightness`, `vcp_volume_contraction`, `TT8_rs_rank`), real
  `bucket` values, real `result ∈ {pass,fail,na}` — via `CriterionResult(criterion_name, layer, result)` /
  `Candidate(bucket=…, criteria=…)` (`swing/data/models.py:127,136`). A fixture that only ever exercises the broad
  rule (never the overlap case in fixtures 2–3) is the §2.2 bug waiting to recur — fixtures 2 & 3 are MANDATORY.
- **Load-bearing data-shape claims — VERIFIED against the live DB `~/swing-data/swing.db` (read-only) 2026-06-09**
  during this brainstorm (the §3.7 standing mandate, exercised at design time so the spec rests on real shapes, not
  fixtures forced to agree):
  1. `schema_version = 25` → migration `0026 → v26` is the correct next bump.
  2. Registry: H1 `active`(20), H2 `active`(10), H3 `closed-target-met`(5), H4 `active`(10) — the engine's
     `status='active'` load excludes H3.
  3. Watch-pool non-pass composition (400 most-recent watch candidates): H2-exact `=={proximity_20ma}` = **1**;
     H4-exact `=={risk_feasibility}` = **0**; dominant sets are multi-criterion `tightness`-bearing
     (`{proximity_20ma,tightness}`=110, `{adr,tightness}`=61, `{tightness,vcp_volume_contraction}`=60,
     `{tightness}`=36). Confirms the broad fallback is the genuine complement and the H3-status flip (fixture 4) is
     the dominant real routing case.
  4. `criterion_name` vocabulary present in live `candidate_criteria`: `proximity_20ma`, `risk_feasibility`,
     `tightness`, `vcp_volume_contraction`, `TT8_rs_rank`, `adr`, `orderliness`, `ma_short_rising`, `pullback`,
     `prior_trend`, `ma_stack_10_20_50`, the 8 `TT*`. Fixtures MUST draw from this exact vocabulary.
- **Codex MUST independently re-verify** these claims where it can (read-only repo + the supplied live-query OUTPUT
  in the review prompt) and challenge any that the fixtures would otherwise force true. This is the discipline the
  original engine chain lacked (the `detection.pivot==candidate.pivot` false premise survived 9 Codex rounds because
  reviews checked logic-vs-spec, never data-vs-DB; memory `feedback_adversarial_review_verify_data_shapes`).

---

## 10. Out of scope / explicitly deferred

- No engine simulator / bracket / funnel / scorecard / `constants.py` change.
- No `measurement_only` registry column (deferred until a 2nd measurement-only hypothesis exists).
- No automated wiring of the engine's shadow scorecard into the DB trade-progress surfaces (the `30` target's
  authoritative read stays in `summary.md`; the dual-read is documented, not unified).
- No Phase-16 drumbeat integration (that is the separate Phase-16 Arc-5 commission,
  `docs/phase16-shadow-expectancy-drumbeat-integration-commissioning-brief.md`).
- TDD posture for the eventual writing-plans → executing-plans dispatches; this phase produces the SPEC only.
```

---

### ADDENDUM 2026-06-10 — Arc 7 attribution-surface re-classification (V2.1 §VII.F governance)

**Context.** Phase 16 / Arc 7 (`docs/superpowers/specs/2026-06-10-watchlist-pin-labeling-design.md`) makes
hypothesis labeling effective in the web-first workflow. It introduces TWO production callers that opt into the
broad-watch baseline via `match_candidate_to_hypotheses(..., include_baseline=True)`. This addendum amends the LETTER
of §3.2 + §5.1 of this spec (which listed `hypothesis_prefill.py:55` among the CONTAINED, default-`False` surfaces) —
NOT its spirit. The containment of the *recommendation flood* surfaces is preserved exactly.

**Re-classification.** The following two surfaces are re-classified from "contained recommendation surface" to
**attribution surface** — they opt into `include_baseline=True`:

1. **`swing/recommendations/hypothesis_prefill.py` — `lookup_active_recommendation_label`** (the entry-form/CLI
   server-stamped label prefill). Rationale: it fires ONLY for a ticker the operator has ALREADY chosen to enter and
   it recommends nothing — it labels an entry for downstream shadow attribution. The §3.2 flood rationale ("cannot put
   a recommendation row on every watch ticker") never applied to it: it surfaces exactly one label for one
   operator-selected ticker. Labeling watch trades with `Broad-watch baseline` is the PERMITTED secondary use already
   sanctioned in §5.3.
2. **`swing/web/view_models/watchlist.py` — the per-row cohort-hint helper** (`cohort_hint_for`, the LONE
   `include_baseline=True` for the hint). Rationale: an affordance that tells the operator what a name WOULD attribute
   as on entry (narrow name | `broad-watch` | none). It is read-only, surfaces no recommendation row, and drives no
   ranking — it is an attribution *preview*, not a recommendation. It does not call `prioritize_recommendations`. The
   helper is consumed by THREE read-only render sites — the standalone watchlist page (`build_watchlist`), the
   `/watchlist/{ticker}/row` collapse route, and the dashboard top-5 section (`build_dashboard`, which imports it) —
   all of which render the same chip and none of which produce a recommendation row. Because the literal opt-in lives
   in this single helper, the inventory guard's "exactly 3 files" invariant holds.

**Still CONTAINED (unchanged, default `include_baseline=False`).** The live *recommendation* surfaces remain contained:
`swing/web/view_models/dashboard.py` (~L540 + ~L1061, the recommendations build + the 2nd matcher call) and
`prioritize_recommendations`. The broad-watch rule never fires for them, so it cannot put a recommendation row on every
watch ticker nor outrank H2/H4 via `distance_to_target`. **Enforced by a regression test** asserting the dashboard call
sites do NOT pass `include_baseline` (kwargs assertion) and that no broad-watch rows reach the hyp-recs panel.

**Bounded opt-in set.** The COMPLETE set of `include_baseline=True` call sites is now exactly THREE: the two above plus
the engine's `research/harness/shadow_expectancy/attribution.py` (the original §4 opt-in). An **opt-in call-site
inventory guard test** (Arc 7 §10.3) asserts this set verbatim; any future opt-in fails the test and requires a
governance amendment (this addendum's path).

**Measurement-universe note (research-director ruling, AMENDMENT 2026-06-10).** The watchlist pin unions pinned
tickers into the `_step_evaluate` evaluated universe, so the evaluated universe is **screen ∪ pinned (∪ held)**. A
pin-injected ticker that evaluates to `bucket=watch` enters the #23 detect/observe pool → the v22 temporal log → the
shadow-engine broad-watch measurement population. This is ACCEPTED and coherent: the FROZEN hypothesis statement
already defines the cohort as "the population the temporal log contains and the operator actually trades," and pinned
names literally are that population (the operator's intentional forward-watch universe). Per-run auditability is
preserved by the pin-injection `warnings_json`/`pipeline.log` line (Arc 7 §5) listing the injected tickers (count +
symbols), so screen-vs-pin provenance stays decomposable from run logs. No schema change; the frozen registry row and
the matcher gate are untouched.

---
