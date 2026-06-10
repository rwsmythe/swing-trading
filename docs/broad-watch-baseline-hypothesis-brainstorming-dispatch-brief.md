# Broad-Watch-Baseline Hypothesis — Registry Amendment — Brainstorming Dispatch Brief

**Audience:** Fresh Claude Code instance, no prior conversation context.
**Mission:** Brainstorm + spec a **fifth pre-registered hypothesis** — a broad-watch baseline (`bucket == watch`, any non-pass set) — added to the frozen `hypothesis_registry` via the sanctioned governance route (a NEW migration, V2.1 §VII.F), plus the matcher rule that lets the shadow-expectancy engine attribute the population the temporal log actually contains. Converge the spec through Codex and hand back a design spec. **Do NOT implement.**
**Prepared:** 2026-06-09 by the research-director/evaluator instance (operator-commissioned).
**Phase:** copowers:brainstorming. Output → a new spec doc → (later) writing-plans → executing-plans as separate dispatches.

---

## 0. Read first

1. `CLAUDE.md` — conventions (conventional commits; NO Claude co-author footer; NO `--no-verify`; TDD; the migration + SQLite gotchas, esp. #11 schema/constant/validator atomicity and the migration backup-gate strict-equality shape).
2. **The freeze contract** — `swing/data/migrations/0008_hypothesis_registry.sql` header: the four hypotheses are FROZEN; "A formal amendment requires a NEW migration with an explicit version bump (signaling the change passed through the source-of-truth correction protocol, V2.1 §VII.F), not an in-place UPDATE." This arc IS that amendment path — you are not breaking governance, you are exercising it.
3. **The matcher** — `swing/recommendations/hypothesis.py`. The extension point is documented at the name-constants block (~L124): "if a NEW migration adds a fifth hypothesis, add the name + matcher rule here." Read the four existing rule predicates, `match_candidate_to_hypotheses` (~L296, multi-match allowed), `prioritize_recommendations`, and the label-match contract (`swing/metrics/label_match.py`, 3-rule delimiter-aware prefix matching).
4. **The shadow engine's attribution path** — `research/harness/shadow_expectancy/attribution.py` (a thin wrapper over the production matcher), `run.py` ~L55 (`list_hypotheses(conn, status_filter="active")`) and ~L116–124 (zero matches → `matched_no_hypothesis`; **>1 match → `multi_match` → unattributed, i.e. the signal is DROPPED from every cohort**), `constants.py` (funnel-reason vocabulary).
5. **The live evidence** — `exports/research/shadow-expectancy-20260610T063533Z/summary.md`: 210 detections → 42 unique signals → **42/42 `matched_no_hypothesis`**, zero priced. The engine is honest; no active hypothesis covers the #23-widened watch pool.
6. The shipped engine spec + correction spec under `docs/superpowers/specs/` (`2026-06-08-shadow-expectancy-engine-design.md`, `2026-06-09-shadow-expectancy-entry-join-correction-design.md`) — the funnel/attribution vocabulary this amendment plugs into.
7. The evaluator charter `docs/research-director-context.md` §6 "P1-NOW" + §7 2026-06-09 entries (why this amendment is the standing top recommendation).

**Skill posture:** invoke `copowers:brainstorming` (wraps superpowers:brainstorming + adversarial Codex review run to convergence; 5-round cap suspended).

---

## 1. Why (the attribution-coverage finding, 2026-06-09)

The shadow-expectancy engine (P1) is SHIPPED + corrected (`31e7441c`) and runs turnkey, but prices ≈zero. Verified live state (read-only DB query, 2026-06-09, schema v25):

- Registry: H1 `A+ baseline` (active), H2 `Near-A+ defensible: extension test` (active), H3 `Sub-A+ VCP-not-formed` (**closed-target-met**), H4 `Capital-blocked: smaller-position test` (active).
- All 42 live signals are `bucket == watch` with assorted non-pass sets. H2 requires non-pass == exactly `{proximity_20ma}`; H4 requires exactly `{risk_feasibility}`. **Zero of 42 match any active hypothesis** → 100% `matched_no_hypothesis`.
- The #23 pool-widening (Phase 15) deliberately made the temporal log accrue the BROAD watch population (~83× the aplus population) as forward-walk data. The registry predates that widening — no hypothesis was ever registered for the population the log now contains.
- The operator's actual practice is watch-pool trading (12 of 16 live trades were watch). A measured baseline for that population is directly decision-relevant.

**The amendment:** register a fifth hypothesis — the broad-watch baseline — so the engine prices that population. Honest caveat to carry into the spec: this is **necessary, not sufficient** — even with coverage, priced samples accrue only as the log matures and names break out over their `candidate.pivot` (currently zero breakouts in the thin 2–3 session windows).

---

## 2. Proposed design direction (a strong starting hypothesis — pressure-test it, don't rubber-stamp it)

### 2.1 The registry row (migration `0026`, v25→v26)

```sql
INSERT OR IGNORE INTO hypothesis_registry
  (name, statement, target_sample_size, decision_criteria,
   consecutive_loss_tripwire, absolute_loss_tripwire_pct, created_at, notes)
VALUES
  ('Broad-watch baseline',
   'The widened watch pool (bucket==watch, any non-pass set, not matching a narrower active hypothesis), priced by the mechanical shadow ruleset, establishes the baseline expectancy of the population the temporal log contains and the operator actually trades',
   30,
   'SHADOW-measured (not closed live trades): realistic bracket arm; primary read on the closed_only + mtm_at_horizon censoring scenarios at N>=30 priced shadow signals; report mean R + Wilson-LB win rate across all four scenarios. Pre-registered as a BASELINE: negative/zero mean R is a bankable validation of the A+ gate selectivity; positive mean R triggers cohort-refinement research (which miss-sets carry the edge), NOT direct deployment.',
   5, 5.0, '<migration date>',
   'Measurement substrate is the shadow-expectancy engine, not labeled live trades. Tripwires apply only if the operator labels live watch trades with this hypothesis (permitted; matches practice). Not an operator recommendation cohort.');
```

Notes: tripwire columns are schema-mandated NOT NULL > 0 (CHECK constraints in 0008) — they must carry values even though the primary measurement is shadow-side. The `decision_criteria` text above is the research-director's proposed pre-registration; refine wording in brainstorm but keep the substance: shadow-measured, N≥30 (mirrors the V2.1 §VII shadow-mode ≥30-signal gate), baseline framing with both outcomes pre-committed.

### 2.2 The matcher rule — FALLBACK semantics (the load-bearing design choice)

A naive `bucket == "watch"` predicate **overlaps H2 and H4** (and H3, if ever re-activated). The matcher multi-matches, and the engine routes `len(hyps) > 1` → `multi_match` → **unattributed** (`run.py` ~L121) — i.e. naive overlap would CANNIBALIZE the narrow cohorts' attribution the moment H2/H4 signals appear. Proposed resolution:

- **Broad-watch matches only when no other active hypothesis rule matched** (evaluate it last, gated on the other rules' outcomes). Baseline = "watch not otherwise hypothesized" — the honest complement; each signal attributes to exactly one watch hypothesis; no engine/funnel changes needed; `multi_match` stays a substrate-integrity signal rather than becoming routine.
- On today's live data the distinction is empty (zero narrow matches → baseline = all 42), but the semantics must be right for the data to come.

### 2.3 Live-surface containment — broad-watch must NOT flood operator recommendations

The same matcher feeds the live recommendation surfaces (`swing/recommendations/hypothesis_prefill.py` ~L55; `swing/web/view_models/dashboard.py` ~L540 + ~L1061). An always-matching hypothesis would put a recommendation row on ~every watch ticker — a recommendation that fires for everything is noise, and `prioritize_recommendations` would rank it HIGH (distance-to-target 30 beats H2's 10). Proposed mechanism (my lean — pressure-test alternatives):

- `match_candidate_to_hypotheses` gains a keyword-only `include_baseline: bool = False`; the broad-watch rule fires only when True. The shadow engine's `attribution.py` passes `include_baseline=True`. Live call sites are untouched-by-construction (default False). The row's `notes` field documents "not an operator recommendation cohort" so the registry self-describes.
- Alternatives to weigh: (a) a `measurement_only` column on the registry (same migration; more schema surface; live loaders filter it — more durable/self-enforcing but touches models + repo + call sites); (b) prioritizer-level demotion/sink (keeps it visible but last — weakest containment); (c) fully visible (rejected: floods the surface with non-recommendations).

---

## 3. Design questions the brainstorm MUST resolve

1. **Overlap/precedence semantics (§2.2).** Fallback-only vs engine-side precedence vs accepting multi-attribution. Whatever is chosen MUST protect H2/H4 shadow attribution (no routine `multi_match` drops) and state what the baseline cohort means (complement vs superset) in the pre-registration text. If fallback: how is "evaluated last, gated on other rules" implemented without making the rules list order-fragile?
2. **Live-surface containment (§2.3).** Pick the mechanism; enumerate EVERY consumer of the registry / matcher / progress surfaces (`list_hypotheses` callers, metrics hypothesis-progress tiles, `hypothesis_prefill`, tripwire CLI, dashboard VMs) and verify each behaves sanely with a 5th active row — including what a 0/30 progress display means for a shadow-measured hypothesis (suppress? annotate? accept?).
3. **Shadow-sample vs closed-trade sample.** H1–H4 criteria count closed labeled trades; this hypothesis counts shadow-priced signals. Where is that progress read from (the engine's scorecard artifacts are per-run exports, not DB rows)? V1 answer may simply be "progress lives in the engine's summary.md, not the trade-labeled progress surfaces" — but say so explicitly, and decide whether live labeling with this hypothesis is permitted (my lean: permitted, gives the tripwires meaning).
4. **Name/label-matcher safety.** Verify `'Broad-watch baseline'` against the 3-rule delimiter-aware contract (`swing/metrics/label_match.py`): no prefix collision with the four existing names in either direction.
5. **Migration mechanics.** `0026_broad_watch_baseline.sql`, v25→v26; backup gate STRICT equality (`pre_version == 25 AND target >= 26`, the Phase-9 clause shape — see CLAUDE.md gotcha); `INSERT OR IGNORE` keyed on UNIQUE `name` (mirror 0008); run-migrate-twice no-op test; the #11 sweep — grep ALL of `swing/` + `tests/` for hardcoded four-hypothesis assumptions (name lists, tests asserting exactly 4 registry rows, label-match fixtures, testkit seeds). Note the research testkit pins at v24 — engine-test fixture DBs need the 5th row injected version-aware or the testkit story stated.
6. **Engine behavior after the amendment (acceptance shape).** Against the live DB: `matched_no_hypothesis` → ~0; all 42 attribute to `Broad-watch baseline` and route to honest per-hypothesis terminals (`never_triggered` / `missing_observations` / censoring) — NOT to priced rows (no breakouts yet). The success criterion is *attribution-routes-correctly*, not immediate expectancy numbers. A golden fixture where a broad-watch signal prices end-to-end (breakout present) plus a fixture proving an H2-shaped signal does NOT fall into the baseline.
7. **Fixtures from REAL emitter shapes (non-negotiable; the standing data-shape mandate).** Candidate fixtures must carry real non-pass sets pulled from live `candidates` rows (real criterion names, real bucket values). Codex MUST verify the load-bearing cohort claims against the live DB where it can: that 0/42 current signals match H2/H4 predicates, the registry statuses, the criterion-name vocabulary. A fixture that only ever exercises the broad rule (never the overlap case) is the §2.2 bug waiting to recur.

---

## 4. Hard constraints

- **Governance:** the four frozen H1–H4 rows are UNTOUCHED (no UPDATE of their frozen fields; H3's `closed-target-met` status stands). `DOCTRINE_DEFENSIBLE_MISS_SET` is untouched. The amendment is purely additive.
- **Production-touch carve-out (this arc's scope; wider than the engine arcs' CLI-only lock — state it in the spec):** `swing/data/migrations/0026_*.sql` (additive), `swing/recommendations/hypothesis.py` (name constant + rule + the opt-in parameter), `research/harness/shadow_expectancy/attribution.py` (pass the opt-in), tests, and the spec doc. The `measurement_only`-column alternative would additionally touch `swing/data/models.py` + `swing/data/repos/hypothesis.py` + live loaders — if chosen, justify the wider footprint explicitly.
- **NO engine simulator/bracket/funnel/scorecard changes.** `constants.py` reason vocabularies unchanged (fallback semantics requires none). If your chosen design DOES require a funnel change, that is a red flag — re-justify against §2.2.
- **NO new production dependency; the engine's forbidden-import L2 test stays green.**
- Spec output: `docs/superpowers/specs/<date>-broad-watch-baseline-hypothesis-design.md`, cross-referencing the engine spec + correction spec sections it plugs into.
- TDD posture for the eventual plan; this phase produces the SPEC only.

---

## 5. Codex transport (this machine)

The MCP `codex` tools are dead in the VS Code extension. Drive Codex via the WSL CLI:
```
wsl -e bash -c 'export PATH="$HOME/.local/node22/bin:$PATH"; codex exec -s read-only --skip-git-repo-check -C "<repo root>" - < "<repo root>/.copowers-review-prompt.txt"'
```
PATH-prefix export REQUIRED; liveness probe `codex --version` → `codex-cli 0.135.0`; round 2+ via `codex exec resume --last -c sandbox_mode="read-only" --skip-git-repo-check`. The 5-round cap is suspended — run to convergence (`NO_NEW_CRITICAL_MAJOR`). **Persist each Codex RESPONSE** (verdicts + the final convergence line) to a gitignored on-disk file. **Instruct Codex to VERIFY the load-bearing data-shape claims against the live repo/DB where it can** (read-only repo access; the live DB at `~/swing-data/swing.db` is outside the repo — supply it the relevant query OUTPUT in the prompt and have it audit the queries) — the original engine chain's blind spot, now a standing mandate.

---

## 6. Done criteria + handoff

- A design spec written, self-reviewed, and **Codex-converged**, resolving every §3 question, with the final pre-registration text (name/statement/target/criteria/tripwires/notes) frozen in the spec verbatim as it will appear in migration 0026.
- The spec states the acceptance shape (§3.6) and the fixture mandate (§3.7).
- **Do NOT implement.** Return for research-director QA, then writing-plans → executing-plans as separate dispatches.
- Commit the spec (conventional; no co-author footer; verify `git log -1 --format='%(trailers)'` is `[]`). Return a short summary: chosen overlap semantics, chosen containment mechanism, the §3 resolutions, Codex convergence verdict, and anything you pushed back on.
