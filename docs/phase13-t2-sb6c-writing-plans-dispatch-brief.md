# Phase 13 T2.SB6c — Writing-Plans Dispatch Brief

**Audience:** Fresh Claude Code instance dispatched as the T2.SB6c writing-plans implementer. No prior conversation context.

**Mission:** Produce an implementation plan that decomposes the T2.SB6c 5-task scope (v21 schema atomic landing + SB6 completion-gap closure) per the operator-confirmed brainstorming spec + 14 OQ dispositions (ALL affirmed verbatim per operator triage 2026-05-21 PM #5).

**Brainstorm spec:** `docs/superpowers/specs/2026-05-21-phase13-t2-sb6c-v21-schema-and-closure-design.md` (659 lines; 8 Codex rounds; ZERO ACCEPT-WITH-RATIONALE). **PRIMARY SUBSTRATE — read end-to-end.**

**Brief:** `docs/phase13-t2-sb6c-writing-plans-dispatch-brief.md` (this file).

**Sequencing:** T2.SB6c brainstorming SHIPPED 2026-05-21 PM #5 at `fb177e3` + housekeeping at `043a5bc`. This writing-plans dispatch is the next step. Output feeds the executing-plans dispatch (5 sub-tasks per spec §6; concurrent T-A.6c.1 + T-A.6c.2 + T-A.6c.3; sequential T-A.6c.4 + T-A.6c.5).

**Branch:** `phase13-t2-sb6c-writing-plans` — branches from main HEAD `043a5bc` (post-brainstorming housekeeping).

**Worktree:** create via `git worktree add .worktrees/phase13-t2-sb6c-writing-plans phase13-t2-sb6c-writing-plans`.

**Workflow:** `copowers:writing-plans` skill (wraps `superpowers:writing-plans` with adversarial Codex MCP review). Expected 2-5 Codex rounds — schema work + pre-Codex discipline now mature at 25 cumulative validations.

**Expected duration:** ~3-6 hours operator-paced (per `feedback_time_estimates_overstated.md` ÷3-5x). Plan line target: ~800-1400 lines (Phase 9 Sub-bundle A writing-plans precedent for similar-scale schema migration was ~1100 lines; T2.SB6c brainstorm is 659 lines + 5-task decomposition adds per-task elaboration).

---

## §0 Read first (in this order)

1. **`docs/superpowers/specs/2026-05-21-phase13-t2-sb6c-v21-schema-and-closure-design.md`** — operator-confirmed brainstorm spec (659 lines; 10 §-sections; 8 Codex rounds; ZERO ACCEPT-WITH-RATIONALE). **PRIMARY SUBSTRATE.** Read end-to-end:
   - §1 Status + scope summary
   - §2 v21 schema delta detailed design (§2.1 Delta A `trades.candidate_id` + §2.2 Delta B `trades.pattern_evaluation_id` + §2.3 Delta C OBSOLETE + §2.4 migration file shape)
   - §3 SB6 closure consumer mapping (§3.2 cross-row lookup discipline + §3.3 content-completeness audit table)
   - §4 Atomic-landing strategy per §A.14
   - §5 Test scope projection
   - §6 Sub-bundle decomposition T-A.6c.1..T-A.6c.5
   - §7 14 OQs with operator-affirmed dispositions (per §1.3 below)
   - §8 LOCKs + watch items
   - §9 Forward-binding lessons + V2 candidates
   - §10 References

2. **`docs/phase13-t2-sb6c-v21-closure-brainstorm-dispatch-brief.md`** — predecessor brief that drove the brainstorming dispatch. Note: §2.3 watchlist_close_track_flags v21 delta C proposal was OBSOLETE; the brainstorm spec correctly caught this via Expansion #2 + reduced v21 scope from 3 → 2 deltas.

3. **`docs/phase13-t2-sb6c-brainstorm-return-report.md`** (188 lines) — brainstorming-phase return report with Codex chain shape + per-expansion verdict (Expansion #6 + #7 effectiveness CONFIRMED; 2 NEW discipline lessons banked) + 8 forward-binding lessons + 6 V1 simplifications + V2 candidates.

4. **`docs/superpowers/plans/2026-05-18-phase13-charts-patterns-autofill-usability-plan.md`** §G.9 (the original T2.SB6 task §) + §H.3 cross-bundle pin schedule + §A.14 atomic-landing discipline. This is the prior Phase 13 plan; T2.SB6c is a v21 extension that does NOT replace the Phase 13 plan; the T2.SB6c plan should reference the Phase 13 plan §-sections + be a separate doc.

5. **`CLAUDE.md`** at repo root — project conventions + cumulative gotchas. ESPECIALLY relevant for T2.SB6c writing-plans phase:
   - Schema-CHECK widening MUST audit ALL Python-side surface guards (T3.SB2 hotfix `cf3c489`)
   - Schema-CHECK + Python-constant + dataclass-validator MUST land in same task (Phase 12 C.A T-A.2)
   - Schema-coverage Python constant is NOT necessarily manual-input allowlist (Phase 12 C.C R1 M#4)
   - Read-path mapping must keep pace with write-path on widened columns (T3.SB3 R1 M#1)
   - Migration runner backup-gate strict equality `pre_version == 20` (Phase 12 C.A §0.5)
   - `executescript()` implicit-COMMIT (Phase 7 Sub-A R1 M3)
   - `INSERT OR REPLACE` cascade-wipe (Phase 8 daily-management spec §4.2)
   - Schema-CHECK + Python-constant + dataclass-validator EXTENDS to semantic contracts (T2.SB6a R1 CRITICAL #1)
   - F6 transient-empty at construction barrier when helper accepts dataclass parameter (T2.SB6a R1 MAJOR #2)
   - Pre-Codex 5-expansion discipline does NOT catch CONTENT-completeness vs spec text NOR cross-row semantic scope drift (T2.SB6b R1)
   - V1 simplification banking discipline (T2.SB6b lessons)
   - **NEW** Brief-vs-actual schema reality check + SQL skeleton column verification (T2.SB6c brainstorming R1 CRITICAL + Expansion #2 catch)
   - Schema-version-aware INSERT for newly-widened columns (T3.SB1 precedent at `swing/data/repos/fills.py:51-53`)
   - Hidden anchor 4-tier rejection ladder (T3.SB1) — extends to 5-tier for `claimed_pattern_evaluation_anchor` per spec §2.2 OQ-12 disposition
   - Recovery form anchor-clear discipline (T3.SB1 R3 M#2)
   - "Server-stamped" hidden form inputs are STILL tampering surfaces unless POST RECOMPUTES (T3.SB3 R1 M#2)

6. **`docs/orchestrator-context.md`** "Currently in-flight work" + "Recent decisions and framings" + "Maintenance: retention discipline" — current state reflects T2.SB6c brainstorming SHIPPED + operator-affirmed 14 OQs.

---

## §1 Operator-affirmed OQ dispositions (BINDING for writing-plans phase)

**Per operator-paired triage 2026-05-21 PM #5 (post-housekeeping; in chat affirmation):** ALL 14 OQ dispositions from brainstorm spec §7 are AFFIRMED VERBATIM. Writing-plans phase encodes spec §7 dispositions BINDING; no divergence; no operator-paired re-triage required.

Highlights for writing-plans phase scope:

- **OQ-1**: NULL backfill for existing `trades.candidate_id` (no heuristic match).
- **OQ-2**: SB6c does NOT include Q4 surfaces (T4.SB owns; schema already in v20).
- **OQ-3**: `pre_version == 20 AND target >= 21` strict-equality backup-gate.
- **OQ-4** + OQ-5: N/A (Q4 schema already in v20).
- **OQ-6**: `reached_1r` = `max(daily_high since entry_date) >= entry_price + (entry_price - initial_stop)`; `hit_stop` = ANY fill at `<= initial_stop` OR `trade.state IN ('closed', 'reviewed') AND realized_R_if_plan_followed < 0`. Suppression at n<5 per Phase 10 honesty.suppress_for_n.
- **OQ-7**: N/A for SB6c (T4.SB owns Q4 surface dispositions).
- **OQ-8**: `swing-pre-phase13-sb6c-migration-<ISO>.db` backup file naming.
- **OQ-9**: row[52] = candidate_id; row[53] = pattern_evaluation_id (after `planned_target_R` at row[51] from migration 0016).
- **OQ-10**: 5-task decomposition T-A.6c.1..T-A.6c.5; concurrent dispatch T-A.6c.1 + T-A.6c.2 + T-A.6c.3 recommended.
- **OQ-11**: `trades.candidate_id` populated at trade-entry-form lock time inside `with conn:` block IF `trade_origin IN pipeline-origins` AND candidates lookup returns row; ELSE NULL.
- **OQ-12** (CLOSURE-COMMITTED at T-A.6c.4): `trades.pattern_evaluation_id` threaded via hidden form input + 5-tier rejection ladder + `claimed_pattern_evaluation_anchor` consistency-check gate; manual-off-pipeline persists NULL.
- **OQ-13**: Metric tile cohort denominator = LEFT JOIN from confirmed `pattern_evaluations` (via `pattern_exemplars.final_decision='confirmed'`); numerator subset with `trades.candidate_id` AND outcome bucket met; suppression at denominator<5.
- **OQ-14**: Volume profile via `swing.web.ohlcv_cache.get_or_fetch(ticker, window_days=80)` with fetch-on-cache-miss ACCEPTED.

---

## §2 Scope inheritance from brainstorm spec

The writing-plans output (plan doc) MUST encode the brainstorm spec §6 5-task decomposition with per-task acceptance criteria + cross-task dependency map + writing-plans §5 watch items. The plan is the BINDING substrate for the executing-plans dispatch.

### §2.1 v21 schema deltas (2 deltas; per spec §2)

**Delta A** = `trades.candidate_id` NULLable INTEGER FK to `candidates(candidate_id) ON DELETE SET NULL`; idx_trades_candidate_id; backfill NULL for existing rows. Unblocks organic_trade_history label_source split + reached_1r/hit_stop metric tile + outcome distribution full bucketing.

**Delta B** = `trades.pattern_evaluation_id` NULLable INTEGER FK to `pattern_evaluations(evaluation_id) ON DELETE SET NULL`; idx_trades_pattern_evaluation_id; backfill NULL for existing rows. Forward-binding for closed-loop quality tracking; threaded via hidden form anchor at T-A.6c.4.

**Delta C** = OBSOLETE per brainstorm spec §2.3 (table already in v20 migration 0020:262-307).

### §2.2 Sub-bundle decomposition (per spec §6; OQ-10 affirmed)

- **T-A.6c.1**: v21 migration atomic landing (~17 paired tests + 3 backup-gate tests + 1 cross-bundle pin). NO schema-dep; foundation.
- **T-A.6c.2**: SB6 closure Gap A chart-surface wiring (~11 tests; no schema dep; can dispatch concurrent with T-A.6c.1).
- **T-A.6c.3**: SB6 closure Gap B no-schema review form data-completeness (~13 tests; can dispatch concurrent with T-A.6c.1).
- **T-A.6c.4**: SB6 closure Gap B v21-dependent + entry-form anchor threading + entry-path mapping fix + VM/builder extensions (31 tests; consumes Delta A + B; sequential after T-A.6c.1).
- **T-A.6c.5**: Closer E2E + ruff sweep + cross-bundle pin row 12 promote (sequential after all).

### §2.3 Cumulative test delta projection (per spec §5)

~81 fast tests + 1 fast E2E projected (within brainstorming brief's expected ~+80-150 range). Baseline 5559 → ~5640 fast post-T2.SB6c executing-plans. Schema v20 → v21 LANDS at T-A.6c.1 (ending the 10+ sub-bundle v20-LOCKED streak).

---

## §3 Watch items + cumulative discipline (BINDING for writing-plans phase)

### §3.1 Pre-Codex 7-expansion discipline (25th cumulative validation banked; 26th expected at executing-plans)

Writing-plans phase pre-Codex review applies ALL 7 expansions (5 original + 2 NEW from T2.SB6b banking) PLUS 2 NEW discipline refinements banked at T2.SB6c brainstorming for the 26th validation:

1. **Expansion #1** — hardcoded-duplicate audit (T3.SB2 hotfix `cf3c489`).
2. **Expansion #2** — brief-vs-spec source-of-truth (T2.SB4 R1 M1) + brief-vs-actual-schema reality check (T2.SB6c brainstorm Expansion #2 catch; NEW refinement).
3. **Expansion #3** — schema-CHECK-vs-semantic-contract gap audit (T2.SB6a R1 CRITICAL #1).
4. **Expansion #4** — CLAUDE.md gotcha specific-scenario trace (T2.SB6a R1 MAJOR #2) **PLUS NEW REFINEMENT (T2.SB6c R1 CRITICAL banking)**: every SQL skeleton's columns MUST be verified against actual `swing/data/migrations/*.sql` files. The plan's SQL skeletons (especially in T-A.6c.4 candidate_id lifecycle + Gap B.3/B.4/B.5 cross-row lookups) MUST each be column-verified against migrations.
5. **Expansion #5** — cross-section spec inventory grep (T2.SB6a R1 MAJOR #3).
6. **Expansion #6** — content-completeness audit (T2.SB6b lessons; CONFIRMED effective at T2.SB6c brainstorming). For T2.SB6c plan: every spec data-surface item the plan ships MUST have per-field disposition LIVE/V1-PARTIAL/V1-STUB; closure dispatch intent honored; no new V1 STUBs.
7. **Expansion #7** — cross-row semantic audit on operator-input flows (T2.SB6b lessons; CONFIRMED effective at T2.SB6c brainstorming) **PLUS NEW BOUNDARY CLARIFICATION (T2.SB6c banking)**: cross-row semantic SCOPE audit (per-candidate vs per-ticker etc.) does NOT subsume column/JOIN correctness — that's Expansion #4 territory. The plan distinguishes the two concerns explicitly.

### §3.2 Cumulative schema-CHECK widening discipline (T3.SB2 hotfix + Phase 12 C.A + Phase 12 C.C lessons + T2.SB6c R1 brainstorming lessons)

- **§A.14 paired atomic landing** (Phase 12 C.A): schema CHECK widening + Python constant widening + dataclass `__post_init__` validator + read-path mapper extension + ALL discriminating tests land in ONE atomic task. T-A.6c.1 enumerates EACH explicitly per Delta A + Delta B.
- **N-mirror auditing** (T3.SB2 hotfix `cf3c489`): grep ALL `swing/` modules for hardcoded copies of any constant introduced; add discriminating tests exercising EACH downstream consumer through production code path.
- **Schema-CHECK + semantic contract paired discipline** (T2.SB6a R1 CRITICAL #1 + T2.SB6c brainstorm validation): dataclass `__post_init__` MUST mirror ALL semantic invariants (cache key shapes, partial-index existence, cross-column uniqueness via partial UNIQUE only) — NOT just schema CHECK.
- **Schema-version-aware INSERT for nullable columns** (T2.SB6c R1 expansion; banked from brainstorming): even nullable column extensions warrant the `PRAGMA table_info` runtime branch pattern (T3.SB1 `fills.py:51-53` precedent). T-A.6c.1 plan task §5 watch item.

### §3.3 Migration runner discipline

- **Backup-gate strict equality**: `pre_version == 20 AND target >= 21` (OQ-3 affirmed). Copy Phase 9 Sub-bundle A backup-gate clause VERBATIM; do NOT paraphrase to `<=`.
- **`executescript()` implicit-COMMIT**: migration runner uses explicit `BEGIN`+`executescript`+`COMMIT` with try/except `rollback()` per `swing/data/db.py:_apply_migration` canonical.
- **`INSERT OR REPLACE` cascade-wipe**: NEW v21 INSERT paths use SELECT-then-UPDATE-or-INSERT for any upsert intent against tables with FK references.
- **Backup file naming**: `swing-pre-phase13-sb6c-migration-<ISO>.db` (OQ-8 affirmed).

### §3.4 Read-path mapping + write-path discipline

- **Read-path mapping must keep pace with write-path** (T3.SB3 R1 M#1): T-A.6c.1 plan task extends `_row_to_trade` mapper with `row[52] = candidate_id; row[53] = pattern_evaluation_id` (OQ-9 affirmed) + adds 2 round-trip discriminating tests per Delta (persist via write path + read back via public reader; assert equality NULL + non-NULL).

### §3.5 Form-driven route discipline (T-A.6c.4 entry-form anchor threading)

- **Server-recompute at POST** (T3.SB3 R1 M#2 LOCK): POST `/trades/entry` MUST re-derive `pattern_evaluation_id` from canonical state at POST time, NOT consume operator-submitted hidden input verbatim. The 5-tier rejection ladder rejects tampered anchors.
- **Hidden anchor 5-tier rejection ladder** (T3.SB1 4-tier extended): per spec §2.2 OQ-12 disposition, `claimed_pattern_evaluation_anchor` consistency-check gate validates: (a) malformed JSON → 400 + clear anchor; (b) non-dict JSON → 400 + clear; (c) dict missing required keys → 400 + clear; (d) dict with invalid value shapes → 400 + clear; (e) **NEW tier-5**: claimed_anchor inconsistent with server-derived `derive_trade_origin()` (e.g., entry_path mismatch) → 400 + clear.
- **Recovery form anchor-clear discipline** (T3.SB1 R3 M#2): on anchor-rejection 400, recovery form clears bad anchor.
- **EntryPath mapping fix at `swing/web/routes/trades.py:1095`** (T2.SB6c brainstorm forward-binding lesson #6): `derive_trade_origin(conn, ticker, entry_path: EntryPath)` cannot distinguish `pipeline_watch_hyp_recs` from `pipeline_watch_manual` if all web POSTs hardcode `EntryPath.MANUAL_WEB_FORM`. T-A.6c.4 fixes as side-effect of anchor-threading.
- **VM/builder fields as part of anchor-threading scope** (T2.SB6c brainstorm forward-binding lesson #7): enumerate all 4 layers (VM field + builder population + template emission + POST validation) per anchor; discriminating tests per layer.

### §3.6 V1 simplification banking discipline (T2.SB6b cumulative; T2.SB6c closure-committed)

T2.SB6c is a CLOSURE dispatch. Every T2.SB6b §6 V1 simplification targeted by SB6c MUST be RESOLVED in the plan (closure-committed) — NOT bank again. Plan §5 watch item enumerates this explicitly. NO new V1 STUBs introduced by SB6c (brainstorm spec §9 confirmed ZERO new V1 STUBs).

### §3.7 Cumulative process discipline

- **NO Co-Authored-By footer** — cumulative ~360+ commit streak ZERO trailer drift through T2.SB6c brainstorming + housekeeping; do NOT regress.
- **`python -m swing.cli` from worktree cwd**, NOT bare `swing`.
- **ASCII-only on runtime CLI paths** + template narrative text.
- **TDD per task** via `superpowers:test-driven-development`.
- **Edit tool for per-file edits**.
- **Cite the discipline in commit messages** per cumulative precedent.

---

## §4 Sub-bundle decomposition guidance (per spec §6)

The writing-plans plan doc decomposes the 5 tasks T-A.6c.1..T-A.6c.5 with per-task acceptance criteria. Plan structure should mirror Phase 13 main plan §G (per-task sub-section per sub-bundle):

```
T-A.6c.1 — v21 migration atomic landing
  Step 1: Write 17+ failing tests covering paired discipline per Delta A + B
  Step 2: Implement migration 0021_phase13_sb6c_v21_trades_backlinks.sql
  Step 3: Implement schema-version-aware INSERT branch in repo
  Step 4: Extend dataclass + read-path mapper atomically
  Step 5: Run tests; verify PASS; backup-gate strict equality verified
  Step 6: Commit — feat(phase13): v21 migration + trades backlinks atomic landing (T-A.6c.1)

T-A.6c.2 — Gap A chart-surface wiring (no schema dep)
  Step 1: Write 11 failing tests for hyp-rec detail VM + position detail VM + WatchlistVM template + exemplar cache-miss write-through
  Step 2: Wire VMs to consume substrate via get_cached_chart_svg + refresh_chart_render
  Step 3: Run tests; verify PASS
  Step 4: Commit — feat(phase13): Gap A chart-surface wiring (T-A.6c.2)

T-A.6c.3 — Gap B no-schema review form data-completeness
  Step 1: Write 13 failing tests for trend-template live read + volume profile join
  Step 2: Implement VM extensions consuming current_stage() + OhlcvCache.get_or_fetch(window_days=80)
  Step 3: Run tests; verify PASS
  Step 4: Commit — feat(phase13): Gap B no-schema data-completeness (T-A.6c.3)

T-A.6c.4 — Gap B v21-dependent + entry-form anchor threading + entry-path mapping fix
  Step 1: Write 31 failing tests for label_source split + reached_1r/hit_stop bucketing + outcome distribution + queue criterion 3 weather-state-aware variant + entry-form anchor threading (5-tier rejection ladder) + entry-path mapping fix + VM/builder extensions per 4-layer scope
  Step 2: Implement POST /trades/entry handler with anchor threading + 5-tier rejection + claim consistency-check gate; server-recompute pattern_evaluation_id derive_trade_origin; fix EntryPath mapping at trades.py:1095
  Step 3: Implement label_source split + outcome bucketing service-layer
  Step 4: Implement queue criterion 3 weather-state-aware variant
  Step 5: Implement read-path consumer extensions (review form outcome distribution; metric tile reached_1r/hit_stop)
  Step 6: Run tests; verify PASS
  Step 7: Commit — feat(phase13): Gap B v21-dep + entry anchor threading (T-A.6c.4)

T-A.6c.5 — Closer (E2E + ruff sweep + cross-bundle pin row 12 promote)
  Step 1: Write 1 fast E2E covering seeded happy path (pipeline run -> pattern_evaluations rows -> trade entry with anchor -> outcome rolls forward via cohort metric tile)
  Step 2: Run full fast-test suite; verify all PASS; verify cross-bundle pin row 12 (TBD per plan §H.3 update) un-skipped + GREEN
  Step 3: ruff check swing/ clean
  Step 4: Commit — test(phase13): T2.SB6c closer + cross-bundle pin row 12 (T-A.6c.5)
```

Each task acceptance criteria enumerated EXPLICITLY in plan; concurrent dispatch sequence captured in plan §H.1 (mirroring Phase 13 main plan §H.1 dispatch sequence convention).

---

## §5 Done criteria for writing-plans output

The plan at `docs/superpowers/plans/2026-05-21-phase13-t2-sb6c-v21-schema-and-closure-plan.md` MUST cover:

- [ ] **§A Status + scope** — v21 migration + SB6 closure; 5 tasks; OQ-affirmed dispositions verbatim.
- [ ] **§B Schema deltas** — Delta A + Delta B verbatim from brainstorm spec §2; SVAI nullable-column pattern enumerated.
- [ ] **§C Atomic-landing strategy** — per Delta: schema CHECK + Python constant + dataclass validator + read-path mapper + paired tests in SAME task (T-A.6c.1); enumerated explicitly.
- [ ] **§D Closure consumer mapping** — per Gap A + B item: V1 STUB → LIVE disposition; cross-row lookup scope per Gap; volume profile data path; outcome bucketing thresholds; queue criterion 3 weather-state variant.
- [ ] **§E Cross-bundle pin updates** — row 12 (TBD; planted at T-A.6c.5 closer) for v21 paired atomic landing invariant.
- [ ] **§F Test scope projection** — total fast + slow + E2E counts; per-task test budget; baseline 5559 → ~5640 expected.
- [ ] **§G Per-task decomposition** — T-A.6c.1..T-A.6c.5 with per-task acceptance criteria + Step 1-N enumeration + commit message templates.
- [ ] **§H Dispatch sequence** — concurrent T-A.6c.1+2+3; sequential T-A.6c.4 + T-A.6c.5; H.1 = sub-bundle dependency graph.
- [ ] **§I Forward-binding lessons inherited** — from T2.SB6c brainstorming return report §7 (8 lessons) + cumulative gotchas relevant.
- [ ] **§J References** — brainstorm spec + Phase 13 main plan + relevant CLAUDE.md gotchas + this brief.

Plan-phase Codex chain expected 2-5 rounds. Pre-Codex 7-expansion discipline + 2 NEW refinements BINDING; verdict per expansion captured in plan-phase return report.

---

## §6 References

- **Brainstorm spec**: `docs/superpowers/specs/2026-05-21-phase13-t2-sb6c-v21-schema-and-closure-design.md`
- **Brainstorming return report**: `docs/phase13-t2-sb6c-brainstorm-return-report.md`
- **Brainstorming dispatch brief (predecessor)**: `docs/phase13-t2-sb6c-v21-closure-brainstorm-dispatch-brief.md`
- **Phase 13 main plan**: `docs/superpowers/plans/2026-05-18-phase13-charts-patterns-autofill-usability-plan.md`
- **Phase 13 main spec**: `docs/superpowers/specs/2026-05-18-phase13-charts-patterns-autofill-usability-design.md`
- **Phase 9 Sub-bundle A writing-plans dispatch brief + plan**: similar-scale schema migration precedent
- **Phase 12 Sub-sub-bundle C.A writing-plans dispatch brief + plan**: schema-widening atomic-landing precedent
- **T2.SB6b return report**: `docs/phase13-t2-sb6b-return-report.md` §6 V1 simplifications (CLOSURE TARGETS for SB6c)
- **CLAUDE.md** at repo root — full cumulative gotcha set

---

## §7 NON-scope (V2 / future arc)

- Phase 13.5 drift surfaces (V2)
- ZERO new Schwab API calls (L2 LOCK preserved through this dispatch)
- T4.SB usability triage items (operator-supplied; PAUSE-FOR-LIST-ADDITIONS BINDING)
- Q4 close-tracking flag surfaces — T4.SB owns (schema already in v20 per migration 0020:262-307)
- Many-to-many `trade_pattern_evaluations` link table (V2 schema dispatch; per brainstorm spec §9 V2 candidates)
- `--enforce-stepwise` migration flag (V2 migration-runner enhancement; per brainstorm spec §9)
- Phase 6 chart_pattern_algo enum unification with Phase 13 detector enum (V2 schema dispatch; per brainstorm spec §9)

---

## §8 Post-writing-plans handback

When writing-plans Codex chain converges to NO_NEW_CRITICAL_MAJOR:

1. Write return report at `docs/phase13-t2-sb6c-writing-plans-return-report.md` per cumulative precedent (commit chain + per-expansion verdict + Codex chain shape + forward-binding lessons + V1 simplifications + V2 candidates + cumulative streaks).
2. Inline self-verification: ruff check; schema unchanged at v20 (writing-plans touches docs only).
3. Hand back to user with summary.

Orchestrator-side next steps post-writing-plans return:
- Merge writing-plans branch --no-ff to main; push; housekeeping bundle.
- Draft executing-plans dispatch brief (typically combines all 5 tasks into one executing-plans dispatch with concurrent T-A.6c.1+2+3 + sequential T-A.6c.4 + T-A.6c.5; OR may split into 2 dispatch bundles per operator decision based on plan complexity).

---

*End of T2.SB6c writing-plans dispatch brief. Brainstorm spec at fb177e3; operator affirmed all 14 OQs verbatim per orchestrator-paired triage 2026-05-21 PM #5; v21 schema scope = 2 deltas (trades backlinks); 5-task decomposition; concurrent dispatch recommended; ~81 fast tests + 1 fast E2E projected; v20 LOCKED streak ENDS at T-A.6c.1; ~360+ ZERO Co-Authored-By footer streak preserved through this brief commit; PAUSE-FOR-LIST-ADDITIONS for T4.SB still binding post-SB6c-executing-plans SHIPPED.*
