# P0 — Tuition-vs-Error Instrumentation — Writing-Plans Dispatch Brief

**Audience:** Fresh Claude Code instance, no prior conversation context.
**Mission:** Produce the TDD implementation PLAN (copowers:writing-plans) for the Codex-converged `entry_intent`
design spec. The spec is BINDING — the plan implements it; it does not re-open settled decisions (the operator
decisions D1–D6 and locks L1–L7 in spec §2 are closed).
**Prepared:** 2026-06-10 by the research-director/evaluator instance, after QA-PASS of the brainstorm return
(live-record §1 table independently re-verified row-for-row against the live DB; the MISTAKE_TAGS category premise
behind the §7.1 panel verified — `NO_STOP`/`STOP_NOT_PLACED` in risk/reconciliation, `CHASED`/`NO_SETUP` in entry;
all file:line anchors land; all 4 Codex rounds persisted).
**Phase:** copowers:writing-plans. Output → a TDD plan → (later) executing-plans as a separate dispatch.

---

## 0. Read first

1. `CLAUDE.md` — conventions + the gotcha families this arc walks: migrations (#9, strict backup-gate equality,
   #11 atomicity + the version-pin sweep), web forms (server-stamp; `... or None` CHECK nullability; rejection
   ladder; soft-warn `form_values` round-trip), `Literal`-not-enforced, CLI `ValueError`→`ClickException`, #16
   ASCII/cp1252, and `feedback_regression_test_arithmetic`.
2. **The BINDING spec** — `docs/superpowers/specs/2026-06-10-tuition-vs-error-instrumentation-design.md`
   (commit `0c1efe71`; Codex-converged R4, 6+1+1 majors all resolved). Pay particular attention to:
   - §2 D1–D6 (operator decisions) + L1–L7 (locks) — closed, not yours to revisit.
   - §4 plumbing: `ENTRY_INTENTS` in `models.py` (colocated with `FAILURE_MODES`); `swing/trades/intent.py` as the
     pure presentation/prefill module; the 0024 `failure_mode` migration as the verbatim plumbing template
     (PRAGMA-aware `_trade_select_cols` branch, `_row_to_trade` trailing append, version-aware INSERT, the NEW
     dedicated `update_entry_intent`).
   - §5 the single prefill rule (web control pre-seeded, submit = confirmation; CLI omitted flag = NULL; the
     service layer NEVER derives intent from the label).
   - §7.1 the faceted card + **the always-on cross-intent execution-discipline panel — its contract is fully
     specified in the spec** (`execution_discipline_tag_frequency` over `MISTAKE_TAGS["risk"] ∪
     MISTAKE_TAGS["reconciliation"]`, intent-UNfiltered source set, the SEPARATE `execution_discipline_n_reviewed`
     denominator). Implement that contract; do not reinvent it.
   - §7.2 PGT marker annotation under the L5 #22 locks (inline-SVG-only; every existing route-test hook preserved;
     the 7 rolling series byte-stable).
   - §7.5/§7.6 leave-unchanged surfaces — they appear in NO task.
   - §9–§10 migration discipline + the test strategy (including the orthogonality test: the discipline panel is
     IDENTICAL under every intent-filter value).
3. The commissioning brief `docs/p0-tuition-vs-error-instrumentation-brainstorming-dispatch-brief.md` (context only;
   the spec supersedes it).
4. The code the plan edits — verify every signature you cite against disk: `swing/data/models.py` (`FAILURE_MODES`
   block), `swing/data/repos/trades.py` (`_TRADE_SELECT_COLS` family, `_trade_select_cols`, `_row_to_trade`,
   `insert_trade_with_event`), `swing/trades/entry.py` (`EntryRequest`/`record_entry`), `swing/trades/review.py`
   (`MISTAKE_TAGS` at :37), `swing/metrics/process.py` (`compute_trade_process_metrics` :546; the tag loop ~:747),
   `swing/metrics/cohort.py` (:32,:84), `swing/metrics/process_grade_trend.py` (:79,:524), the trade-process-card
   VM/template, the PGT VM/template, `swing/web/routes/trades.py` + `routes/metrics.py`, `swing/cli.py`.

**Skill posture:** invoke `copowers:writing-plans` (adversarial Codex review to convergence; cap suspended).

---

## 1. What the plan must cover (spec §4–§10, exactly)

1. **Migration `0027` + db.py** — the §4.2 ALTER (0024-shaped column CHECK); `EXPECTED_SCHEMA_VERSION` 26→27;
   `_entry_intent_backup_gate` strict `current==26 AND target>=27` + `ENTRY_INTENT_PRE_MIGRATION_EXPECTED_TABLES`
   (the v26 table set = the v25 set — 0026 added NO table); gate registered after `_broad_watch_baseline_backup_gate`;
   migrate-twice no-op. **Migration-number check at executing time:** Phase 16 has arcs in flight/queued (perf;
   Arc 7 watchlist-pin will itself take a migration) — the plan must instruct the executing agent to verify `0027`
   is free at branch time and renumber + adjust gates/pins if not.
2. **Constant + model + validator (#11 atomic, ONE task)** — `ENTRY_INTENTS` in `models.py`; `Trade.entry_intent`
   field + `__post_init__` validation; the schema CHECK from (1) lands with them.
3. **Repo plumbing** — the §4.4 four points (PRAGMA-aware projection with `NULL AS entry_intent` pre-v27;
   `_row_to_trade` trailing index; version-aware INSERT; the dedicated `update_entry_intent` that touches no review
   field and no state).
4. **`swing/trades/intent.py`** — display tuple + `entry_intent_label` + `entry_intent_display_choices` +
   `suggest_entry_intent` (§5.1 keyword table) + the display/constant no-drift test.
5. **Set/correct surfaces** — §7.3: entry web form (`<select>` seeded from the suggestion; server-stamp POST;
   soft-warn round-trip), `EntryRequest`/`record_entry` threading, CLI `--entry-intent` (omitted → NULL), review
   web form (persisted-value pre-population; NULL → suggestion default; persists via `update_entry_intent`),
   CLI review correction option.
6. **Backfill CLI** — §6 `swing trade backfill-intent` (all-states walk incl. closed-not-reviewed; idempotent;
   `--trade-id`/`--force`; summary-as-audit; `skip` leaves NULL; ASCII; `ClickException` wrapping).
7. **Faceted surfaces** — §7.1: `compute_trade_process_metrics` intent filter (+ `__unclassified__`), `cohort.py`
   predicates, card VM facet on the "All" aggregate (D6), template + route param, AND the execution-discipline
   panel per the spec's exact contract.
8. **PGT markers** — §7.2 field + VM hook + template circles/legend under the L5 locks.
9. **Tests** — the §10 strategy in full, including: the orthogonality test (panel identical across filter states;
   `CHASED` absent from the panel), the regression-arithmetic discipline (pre/post values computed for every
   changed assertion), real-emitter fixtures mirroring the §1 live table (use the REAL label strings), the
   version-pin sweep 26→27 (the ~40-hit family — enumerate the loci like the 0026 plan did, with the
   head-tracking-vs-pinned classification rule), form-safety tests, and the subprocess-encoding test for the
   backfill CLI.

**NOT in the plan (locks):** everything in spec §7.5/§7.6; the measurement chain (L1); grade/tag semantics (L2);
`update_trade_review_fields` widening (the dedicated writer exists instead); the #22 rolling series; any
intent×hypothesis matrix.

---

## 2. Plan-quality requirements

- **TDD per task; each task ends green.** Sequence so the schema/constant/validator family lands atomically and the
  repo projections precede any consumer; state the expected RED set when `EXPECTED_SCHEMA_VERSION` bumps (the 0026
  plan's Task-2 Step-6/7 shape is the precedent — reuse its classification discipline).
- **Fixtures from the §1 live table** — real hypothesis-label strings (including VIR's `inaugural trade test` and
  the NULL-label VSAT/PTEN rows), real tag combinations. A fixture that only uses idealized labels is the
  synthetic-drift gotcha.
- **Every cited signature verified against disk** at plan-write time; if the spec's file:line drifted (main moves),
  re-anchor and note it.

---

## 3. Codex transport + review mandate (this machine)

WSL CLI (MCP codex tools dead in the VS Code extension):
```
wsl -e bash -c 'export PATH="$HOME/.local/node22/bin:$PATH"; codex exec -s read-only --skip-git-repo-check -C "<repo root>" - < "<repo root>/.copowers-review-prompt.txt"'
```
Liveness `codex --version` → `codex-cli 0.135.0`; round 2+ `codex exec resume --last -c sandbox_mode="read-only"
--skip-git-repo-check`. Run to convergence; cap suspended. **Persist EVERY round's full RESPONSE (including
Round 1)** to the gitignored findings file. Mandate Codex verify the plan's edits against the shipped signatures
(§0.4 list) and the spec's §1 live-record claims against supplied query output
(`feedback_adversarial_review_verify_data_shapes`).

---

## 4. Done criteria + handoff

- A TDD plan at `docs/superpowers/plans/2026-06-10-tuition-vs-error-instrumentation.md`, self-reviewed,
  **Codex-converged**, responses persisted (all rounds).
- Covers §1 exactly; honors the locks; meets §2 quality bars.
- **Do NOT implement.** Return for research-director QA, then executing-plans as a separate dispatch.
- Commit the plan (conventional; no co-author footer; `git log -1 --format='%(trailers)'` → `[]`). Return a short
  summary: task list shape, any spec ambiguities resolved (with the spec-faithful reading), Codex verdict, and
  anything you pushed back on.
