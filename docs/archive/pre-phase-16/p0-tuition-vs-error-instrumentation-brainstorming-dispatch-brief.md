# P0 — Tuition-vs-Error Instrumentation — Brainstorming Dispatch Brief

**Audience:** Fresh Claude Code instance, no prior conversation context.
**Mission:** Brainstorm + spec a first-class distinction between **deliberate hypothesis-test entries (sub-optimal
by design — "tuition")** and **genuine discipline violations ("error")** in the trade record, so the process-quality
surfaces (`process_grade` trend, mistake-tag frequency, trade-process card) stop conflating them. Converge through
Codex; hand back a design spec. **Do NOT implement.**
**Prepared:** 2026-06-10 by the research-director/evaluator instance (operator-commissioned; this is the standing P0
from `docs/research-director-context.md` §6).
**Phase:** copowers:brainstorming. Output → spec doc → (later) writing-plans → executing-plans as separate dispatches.

---

## 0. Read first

1. `CLAUDE.md` — conventions + gotchas. Directly relevant families: the **migration gotchas** (#9 explicit
   BEGIN/COMMIT; backup-gate STRICT equality; #11 schema/constant/validator atomicity + hardcoded-enum sweep) and the
   **web-form gotcha family** (server-stamp don't trust hidden inputs; hidden-anchor round-trip through soft-warn
   `form_values`; the 4-tier rejection ladder; `... or None` for nullable CHECK columns).
2. The evaluator charter `docs/research-director-context.md` §3–§4 — the problem statement is forensic, not
   hypothetical: 16 live trades, ~13 self-graded process "A" while program expectancy is −0.083R/trade; most losses
   are **H3 succeeding by design** (pre-registered sub-A+ entries expected to lose); but genuine slips exist in the
   same record (VIR carried `STOP_NOT_PLACED`). The conflation misled the research director himself (session 1,
   2026-06-08) — any analyst reading `process_grade`/`mistake_tag_frequency` today will misread the record the same way.
3. The schema ground truth: `mistake_tags` (JSON-text) + `process_grade` (`CHECK IN ('A','B','C','D','F')`) are
   columns ON `trades` — added by migration `0013` (Phase 6), re-created in `0014`'s trades table. Validation/
   canonicalization helpers live in `swing/trades/review.py` (`validate_mistake_tags`, `canonicalize_mistake_tags`,
   `compute_process_grade`).
4. The consumer surfaces (enumerate exhaustively in the spec; these are the verified starting set):
   `swing/metrics/process.py` (trade-process card; note its `n_reviewed` "closed AND reviewed" scope),
   `swing/metrics/process_grade_trend.py` (**the #22 PGT-redesign — read its design doc/spec before proposing
   changes to the trend surface**), `swing/web/routes/metrics.py` + the process/trend view models + templates,
   `swing/web/routes/trades.py` (review form), `swing/cli.py` (review + journal surfaces), and anything else a
   `process_grade|mistake_tags` grep over `swing/` surfaces.
5. `docs/hypothesis-recommendation-backend-brief.md` + `docs/trade-hypothesis-label-brief.md` — the pre-registered
   4-hypothesis program (now 5 with `Broad-watch baseline`, migration 0026) and how `hypothesis_label` reaches
   trades (Phase 4.5 entry-form field + CLI `--hypothesis`; canonicalized via `canonicalize_hypothesis_label`).

**Skill posture:** invoke `copowers:brainstorming` (wraps superpowers:brainstorming + adversarial Codex review run
to convergence; 5-round cap suspended).

---

## 1. The problem, precisely

`process_grade` and `mistake_tags` currently measure **execution quality** against the operator's plan — and the
operator's plan for most of the 16 trades was a *pre-registered, designed-to-probably-lose hypothesis test* (H3
et al., frozen in migration 0008). So the record shows "A-grade process, negative expectancy" — which is CORRECT
(the tests were executed as designed) but reads as either self-delusion or strategy failure to anyone who doesn't
already know the design intent. Meanwhile genuine discipline violations (VIR `STOP_NOT_PLACED`) sit in the same
tag pool, visually indistinguishable from tuition.

**The missing dimension is trade-level DESIGN INTENT.** It is orthogonal to execution quality:

| | executed cleanly | executed with slips |
|---|---|---|
| **standard entry** | the goal | the real problem to surface |
| **designed hypothesis test** | tuition working as intended | STILL a real problem (VIR) |

The fix gives every trade an explicit intent attribute and facets the process surfaces by it — it must NOT weaken
the slip-detection semantics on designed trades (the bottom-right cell stays a violation).

---

## 2. Proposed design direction (starting hypothesis — pressure-test it)

- **One nullable trade column** via migration `0027` (schema v26→v27, additive, backup gate STRICT
  `current == 26 AND target >= 27`): e.g. `entry_intent TEXT CHECK (entry_intent IS NULL OR entry_intent IN
  ('standard','hypothesis_test_by_design'))`. NULL = unclassified (legacy/unset), distinct from 'standard' —
  surfaces must render the three states honestly, not coerce NULL→standard.
- **Set at entry, correctable at review.** Entry form + CLI gain the field (default suggestion derivable from the
  hypothesis label — see §3.3 — but the persisted value is the operator's explicit choice; server-stamp gotchas
  apply). The review flow may correct it (intent was known at entry, but the operator may mislabel).
- **Backfill the 16 historical trades** by an operator-driven classification pass (he is the only source of truth
  for intent). Decide the surface (a one-shot CLI walk vs the web review-edit) — idempotent, auditable.
- **Facet, don't fork, the surfaces:** the trade-process card + mistake-tag frequency + PGT trend split or annotate
  by intent (e.g. tabs/filter or per-intent rows) so "execution quality on standard entries" is finally readable in
  isolation. `process_grade`/`mistake_tags` semantics themselves UNCHANGED.

---

## 3. Design questions the brainstorm MUST resolve

1. **Field shape + placement.** Enum vs boolean; trade-level column vs review-table field; exact vocabulary (is
   `hypothesis_test_by_design` the right second value? is a third value needed, e.g. for forced/closing-event
   entries?). Justify against the live record's actual shapes.
2. **The semantic contract for `process_grade` going forward** — write it down in the spec: the grade measures
   execution-given-intent (the historical "A on designed losers" grades are then CORRECT, and the fix is display
   faceting, not regrading). Decide whether any historical grades need revisiting at backfill or stand as-is.
3. **Intent prefill from `hypothesis_label`** — mapping proposal: H3-labeled ⇒ suggest `hypothesis_test_by_design`;
   H1/`Broad-watch baseline` ⇒ suggest `standard`; H2/H4 ⇒ decide (they are designed *tests* but the entries follow
   the method). PREFILL ONLY — the operator confirms; nothing auto-stamps from the label at persist time. Where
   does the suggestion render (entry form, review form, backfill walk)?
4. **Backfill mechanism** for the 16 historical trades: surface, idempotency, audit trail (does a backfill write
   need a provenance note?), and what happens to trades that stay NULL.
5. **Surface-by-surface disposition** — the exhaustive consumer sweep (§0.4 starting set + grep): for EACH surface,
   split / annotate / leave-unchanged, with the NULL-intent rendering decided. The PGT-redesign (#22) trend surface
   is the most sensitive — read its spec first and respect its design.
6. **Measurement-chain isolation (LOCK).** The hypothesis registry, matcher, tripwires, progress counters, shadow
   engine, and temporal log are UNTOUCHED. Intent is a process-quality instrument, not a measurement input. If the
   design seems to need a measurement-chain change, that is a red flag — stop and re-justify.
7. **Form-safety compliance.** Any new entry/review/backfill form field walks the CLAUDE.md web-form gotcha family
   (server-stamp; hidden-anchor round-trip; rejection ladder; `... or None` nullability with the CHECK).
8. **Fixtures from REAL emitter shapes + live-record verification (standing mandate).** Pull the actual 16 trades'
   `hypothesis_label` / `process_grade` / `mistake_tags` states from the live DB (read-only `mode=ro`,
   `~/swing-data/swing.db`) at design time; the spec's claims about the record must match it (e.g. verify the VIR
   `STOP_NOT_PLACED` claim, the ~13-A-grades claim, how many trades are labeled per hypothesis). Supply the query
   OUTPUT to Codex and have it audit the spec's claims against it — the `feedback_adversarial_review_verify_data_shapes`
   discipline.

---

## 4. Hard constraints

- **Schema:** one additive migration `0027` (v26→v27); nullable column(s) only; no rewriting of existing rows in
  the migration itself (backfill is operator-driven, post-migration); backup gate strict equality mirroring
  `_broad_watch_baseline_backup_gate` (`swing/data/db.py`); migrate-twice no-op test; the #11 sweep (the v26 pin
  family was just swept at 0026 — the same families move to 27).
- **Phase-isolation carve-out (state it in the spec):** `swing/data/migrations/0027_*.sql` + `swing/data/db.py`
  (gate/version) + the trades model/repo column plumbing + `swing/trades/review.py` + the entry/review/backfill
  form-and-CLI surfaces + the metrics consumer surfaces (§3.5) + tests. Default read-only posture holds for
  everything else.
- **UNTOUCHED:** the hypothesis registry rows + matcher + `swing/recommendations/`, the shadow engine
  (`research/harness/`), the temporal log, `mistake_tags`/`process_grade` validation semantics (faceting only).
- **V1 small.** One field, prefill, backfill, faceted surfaces. No review-flow redesign, no historical regrading
  engine, no new metric inventions.
- Spec output: `docs/superpowers/specs/<date>-tuition-vs-error-instrumentation-design.md`.

---

## 5. Codex transport (this machine)

WSL CLI (MCP codex tools are dead in the VS Code extension):
```
wsl -e bash -c 'export PATH="$HOME/.local/node22/bin:$PATH"; codex exec -s read-only --skip-git-repo-check -C "<repo root>" - < "<repo root>/.copowers-review-prompt.txt"'
```
Liveness `codex --version` → `codex-cli 0.135.0`; round 2+ `codex exec resume --last -c sandbox_mode="read-only"
--skip-git-repo-check`. Run to convergence (`NO_NEW_CRITICAL_MAJOR`); 5-round cap suspended. **Persist EVERY
round's full RESPONSE (including Round 1)** to a gitignored findings file. Mandate Codex verify the spec's claims
against the shipped code (the review/process/PGT surfaces) and the supplied live-DB query output (§3.8).

---

## 6. Done criteria + handoff

- A design spec written, self-reviewed, **Codex-converged**, resolving every §3 question, with the §3.2 semantic
  contract and the §3.5 surface dispositions stated explicitly, and the live-record verification (§3.8) embedded.
- **Do NOT implement.** Return for research-director QA, then writing-plans → executing-plans as separate dispatches.
- Commit the spec (conventional; no co-author footer; `git log -1 --format='%(trailers)'` must be `[]`). Return a
  short summary: chosen field shape + vocabulary, the semantic contract, the surface dispositions, the backfill
  design, Codex verdict, and anything you pushed back on.
