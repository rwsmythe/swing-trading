# Phase 13 T2.SB6c — v21 schema + SB6 closure brainstorming dispatch brief

**Status:** READY FOR DISPATCH. Drafted 2026-05-21 PM #4 post-T2.SB6b SHIPPED at `6ec989e` + housekeeping at `2dd90fe`. Operator-decided scope per orchestrator-paired triage: **v21 schema dispatch to unblock all T2.SB6 completion gaps + Q4 close-tracking flag schema pull-forward**.

**Branch:** `phase13-t2-sb6c-v21-closure-brainstorm` — branches from main HEAD `2dd90fe` (post-T2.SB6b housekeeping).

**Worktree:** create via `git worktree add .worktrees/phase13-t2-sb6c-v21-closure-brainstorm phase13-t2-sb6c-v21-closure-brainstorm`.

**Workflow:** Full copowers (`copowers:brainstorming` → `copowers:writing-plans` → `copowers:executing-plans`) per operator decision. Schema work touching multiple tables + §A.14 paired discipline + cross-row semantic contracts (NEW expansions #6 + #7 BINDING) warrants the full adversarial-review cadence. Expected 3-7 Codex rounds (schema brainstorms have historically run R1-R5+; Phase 9 Sub-bundle A + Phase 12 Sub-sub-bundle C.A precedent).

**Time estimate:** brainstorming phase 2-4 hours operator-paced (per `feedback_time_estimates_overstated.md` ÷3-5x; Phase 13 brainstorm precedent was 1483 lines + 7 Codex rounds; T2.SB6c brainstorm is narrower scope — 3 schema deltas + SB6 closure mapping — but spec quality must match).

---

## §1 Scope summary

**Drives:** close Phase 13 T2.SB6 completion gaps surfaced at T2.SB6b orchestrator-side verification (post-merge) per `docs/phase13-t2-sb6b-return-report.md` §6 + §7. T2.SB6b correctly shipped all 8 T-A.6.X task IDs, but plan §G.9 acceptance criteria (c)+(d) on T-A.6.6 + spec §5.10 data-surface checklist items + S6+S7 operator-witnessed gates were V1-banked with V2 dependencies cited. Operator decision: dispatch v21 schema unblock + SB6 wiring closure now, not after T4.SB.

**v20 LOCKED streak ENDS with this dispatch.** Schema unchanged through 10 sub-bundles since T-A.1.1 v20 landing. v21 will introduce 3 new schema deltas.

**Output:** brainstorming-phase spec at `docs/superpowers/specs/<date>-phase13-t2-sb6c-v21-schema-and-closure-design.md` covering:
1. v21 schema delta design (3 deltas confirmed at orchestrator scope-triage)
2. SB6 closure consumer mapping (which gaps each delta unblocks; which gaps need wiring-only)
3. Atomic-landing strategy per §A.14 paired discipline (schema CHECK + Python constant + dataclass validator + read-path mapper + all paired tests in SAME task)
4. Test scope projection (Phase 13 brainstorm projected +590-1020; T2.SB6c projects ~+80-150 fast tests + 1-2 fast E2Es)
5. OQ disposition table (open questions surfaced during brainstorm for operator-paired triage)

---

## §2 v21 schema delta scope (3 deltas confirmed)

### §2.1 `trades.candidate_id` backlink (PRIMARY)

**Shape:** NULLable INTEGER column on `trades` table; FK constraint `REFERENCES candidates(candidate_id) ON DELETE SET NULL` (FK is advisory; candidates rows decay weekly per pipeline lifecycle). Index `idx_trades_candidate_id ON trades(candidate_id)` for outcome lookups + Phase 10 cohort joins.

**Backfill semantics for existing trades rows:** NULL (no retroactive lookup; existing trades pre-Phase-13 do not have a guaranteed candidate row in the same pipeline run). Brainstorming OQ: should backfill attempt heuristic ticker+date match against `candidates` table within a tolerance window, or just leave NULL?

**Unblocks (per T2.SB6b return report §6):**
- POST `/patterns/{id}/review` `label_source` split (`closed_loop_review` if no trade opened; `organic_trade_history` if confirm + trade opened resolved via this backlink — spec §5.10 lines 785-790)
- Metric tile `reached_1r` + `hit_stop` bucketing (`/metrics/pattern-outcomes` 9th tile; T-A.6.5 plan §G.9 acceptance)
- Review form outcome distribution full bucketing (`reached_1r_pct` + `hit_stop_pct` alongside `triggered_pct`; T-A.6.3 spec §5.10 line 773)

**Pre-Codex review scope expansion #1 BINDING (T3.SB2 hotfix `cf3c489` discipline):** grep `swing/` for ALL hardcoded copies of any existing trades-row column tuples that would need widening to include candidate_id (e.g., SELECT statements with explicit column lists; INSERT statements; dataclass field tuples). The schema-version-aware INSERT pattern at `swing/data/repos/fills.py:51-53` is the canonical template (T3.SB1 precedent for NOT-NULL-DEFAULTED columns; this column is NULLable so pattern may differ).

### §2.2 `trades.pattern_evaluation_id` backlink

**Shape:** NULLable INTEGER column on `trades` table; FK constraint `REFERENCES pattern_evaluations(evaluation_id) ON DELETE SET NULL`. Index `idx_trades_pattern_evaluation_id ON trades(pattern_evaluation_id)` for detector calibration metrics.

**Backfill semantics:** NULL for existing trades; no retroactive lookup (pattern_evaluations is a Phase 13 table — pre-Phase-13 trades have no corresponding row).

**Unblocks (forward-binding; not in T2.SB6b return report §6):**
- Direct linkage from trade → detector's evaluation row (composite_score + geometric_score + template_match_score visible per trade)
- Future closed-loop quality tracking + post-hoc detector calibration metrics (Phase 13.5 monitoring side)
- Operator analysis: "Of trades opened on VCP detector hits, what fraction reached 1R?" via single JOIN

### §2.3 `watchlist_close_track_flags` NEW table (T4.SB Q4 pull-forward)

**Source:** Phase 13 brainstorm §7.2 D-Q4.1 architectural decision (brainstorm-default LOCKED: NEW table; Web + CLI both surfaces; persistent-until-cleared-or-position-open; badge inline; UNION'd with pipeline output; watchlist-surface-only; per-flag-event audit row). Pulled forward from T4.SB to T2.SB6c so T4.SB closer can focus exclusively on Theme 4 usability work without schema dispatch overhead.

**Shape (per Phase 13 brainstorm §7.2):**
- `flag_id INTEGER PRIMARY KEY AUTOINCREMENT`
- `ticker TEXT NOT NULL`
- `flagged_ts TEXT NOT NULL` (ISO 8601)
- `flagged_by_surface TEXT NOT NULL CHECK (flagged_by_surface IN ('web', 'cli'))`
- `cleared_ts TEXT` (NULLable; auto-set on position-open per spec; OR explicitly cleared by operator)
- `cleared_by_reason TEXT CHECK (cleared_by_reason IN ('operator_explicit', 'position_opened', NULL))` (NULLable per CHECK)
- Partial UNIQUE index on `(ticker)` WHERE `cleared_ts IS NULL` (one active flag per ticker)
- Per-flag-event audit row pattern: NEW INSERTs are the audit trail (append-only); UPDATEs only set `cleared_ts` + `cleared_by_reason`

**Brainstorming OQs:**
- Does PTEN canonical use case (Phase 13 brainstorm preserved verbatim) need any spec amendment now that we have ~6 months more operating history?
- Should the cleared_by_reason enum include any additional values (e.g., `position_closed_recently_already`)?
- Index strategy for the "active flags" surface query — partial UNIQUE on `WHERE cleared_ts IS NULL` is the brainstorm-default; brainstorming spec to confirm performance characteristics.

---

## §3 SB6 closure scope (Gap class A + B items)

Each item below has a SPEC source + a V2-dependency state per T2.SB6b return report §6.

### §3.1 Gap class A — chart-surface wiring (NO schema dependency; can land in T2.SB6c executing-plans)

| Gap | Spec source | Wiring required |
|---|---|---|
| Hyp-rec detail VM 800×500 SVG | plan §G.9 T-A.6.6 (c); spec §C.1 line 396 | `swing/web/view_models/recommendations.py` → `RecommendationsVM` extends with `hyprec_detail_chart_svg_bytes` field; route handler populates from `chart_renders` cache via `get_cached_chart_svg(surface='hyprec_detail', pipeline_run_id=...)`; template renders inline SVG |
| Position detail VM 800×500 SVG with fill markers | plan §G.9 T-A.6.6 (d); spec §C.1 line 398 | `swing/web/view_models/trades.py` → position detail VM extends with `position_chart_svg_bytes` field; consumes `get_cached_chart_svg(surface='position_detail', pipeline_run_id=NULL)` per §C.2 cache key shape (position_detail is run-agnostic) |
| WatchlistVM template renders thumbnail | plan §G.9 T-A.6.6 (b) PARTIAL; spec §C.1 line 395 | `swing/web/templates/partials/watchlist_row.html.j2` → consume existing `watchlist_chart_svg_bytes` field already populated on WatchlistVM (T2.SB6b R1 MAJOR #5 partial fix at `94e4418`); render inline SVG per row |
| Exemplar cache-miss write-through | spec §C.2 cache key shape | `swing/web/view_models/patterns/exemplars.py` cache-miss path → after live render via `render_theme2_annotated_svg`, write through to `chart_renders` via `refresh_chart_render` (NEW path; substrate-API verbatim) |

### §3.2 Gap class B (no schema dependency) — review form spec data-completeness

| Gap | Spec source | Wiring required |
|---|---|---|
| Trend-template state (currently "n/a") | spec §5.10 line 768 | Live `current_stage()` weather-state read; pull from `weather_runs.weather_runs_id` for current action_session per existing session-anchor pattern; populate `PatternReviewFormVM.trend_template_state: str` field |
| Volume profile (currently "(not available)") | spec §5.10 line 770 | 30-session volume + 50d avg join from existing OhlcvCache; populate `PatternReviewFormVM.volume_profile: VolumeProfileRow` with rolling stats |

### §3.3 Gap class B (v21 schema-dependent) — review form + queue + metric tile

| Gap | Spec source | Wiring required (post-v21 land) |
|---|---|---|
| POST `/patterns/{id}/review` label_source split | spec §5.10 lines 785-790 | POST handler joins via `trades.candidate_id` to check if any open/closed trade exists for the candidate; emit `organic_trade_history` if yes + confirm decision; else `closed_loop_review` |
| Review form outcome distribution full bucketing | spec §5.10 line 773 | Compute `reached_1r_pct` + `hit_stop_pct` from `trades` JOIN'd via `candidate_id` against prior-similar-candidate cohort |
| Metric tile `reached_1r` + `hit_stop` | T-A.6.5 plan §G.9 + spec §5.10 | `swing/metrics/pattern_outcomes.py` extends `build_pattern_outcome_rows` to JOIN trades via `candidate_id` per pattern_class; bucket per `reached_1r` (yes/no) + `hit_stop` (yes/no) |
| Queue criterion 3 underrepresented_regime weather-state-aware variant | spec §5.10 line 799 | `swing/patterns/active_learning.py` extends criterion 3 to consider current weather-state (via Phase 8 `weather_runs` read) when counting exemplars for "underrepresented regime" — per spec §5.10 line 799 (vs current V1 proxy = total exemplar count) |

### §3.4 NEW Theme 4 Q4 surfaces (post-v21 land; Phase 13 brainstorm §7.2 reference)

These were V2-deferred at brainstorm but Q4 close-tracking flag schema pulled forward to v21 means SB6c can ALSO land Q4 surfaces (Web + CLI). Alternatively, surfaces can land at T4.SB consuming v21 schema; brainstorming to decide.

| Surface | Source | Disposition options |
|---|---|---|
| `POST /watchlist/{ticker}/flag` HTMX route | brainstorm §7.2 D-Q4.2 | Land in SB6c OR defer to T4.SB |
| `POST /watchlist/{ticker}/unflag` HTMX route | brainstorm §7.2 D-Q4.2 | Land in SB6c OR defer to T4.SB |
| `swing watchlist flag <ticker>` CLI subcommand | brainstorm §7.2 D-Q4.2 | Land in SB6c OR defer to T4.SB |
| `swing watchlist unflag <ticker>` CLI subcommand | brainstorm §7.2 D-Q4.2 | Land in SB6c OR defer to T4.SB |
| Watchlist UI badge inline rendering | brainstorm §7.2 D-Q4.4 | Land in SB6c OR defer to T4.SB |
| Auto-clear on position-open trigger | brainstorm §7.2 D-Q4.3 | Land in SB6c OR defer to T4.SB |

**Brainstorming OQ: SB6c scope boundary** — does SB6c include Q4 surfaces (Web + CLI + auto-clear), or just the v21 schema landing + SB6 closure wiring (leaving Q4 surfaces to T4.SB)?

---

## §4 Watch items (BINDING per cumulative discipline)

### §4.1 Cumulative pre-Codex 5-expansion discipline (24th cumulative validation result locked at T2.SB6b NOTABLE)

The 5 ORIGINAL expansions BINDING for T2.SB6c brainstorm + writing-plans + executing-plans:

1. **Expansion #1 — hardcoded-duplicate audit** (T3.SB2 hotfix `cf3c489`): grep `swing/` for hardcoded duplicates of ALL new constants introduced by v21 schema deltas + SB6 closure work. Specifically: `_FLAGGED_BY_SURFACE_VALUES` enum + `_CLEARED_BY_REASON_VALUES` enum + any new module-level constants for SB6 closure (e.g., outcome bucketing thresholds; weather-state codes).
2. **Expansion #2 — brief-vs-spec source-of-truth** (T2.SB4 R1 M1): cross-check this brief's prescriptions against spec §5.10 + §C.1 + §C.2 + Phase 13 brainstorm §7.2 D-Q4.1..D-Q4.7 BINDING text byte-for-byte. Verify Q4 schema shape matches brainstorm-default verbatim.
3. **Expansion #3 — schema-CHECK-vs-semantic-contract gap audit** (T2.SB6a R1 CRITICAL #1): every NEW dataclass `__post_init__` validator on the 3 new schema surfaces MUST mirror BOTH the schema CHECK AND every SEMANTIC contract layered atop (e.g., partial UNIQUE index existence semantics; FK semantics; cross-column invariants not captured by table CHECK).
4. **Expansion #4 — CLAUDE.md gotcha specific-scenario trace** (T2.SB6a R1 MAJOR #2): each cumulative gotcha cited in this brief MUST be walked through a SPECIFIC failure scenario in the T2.SB6c code path. NOT generic "is the lesson applied" sufficiency check.
5. **Expansion #5 — cross-section spec inventory grep** (T2.SB6a R1 MAJOR #3): grep production code under `swing/data/migrations/` (NEW v21 migration) + `swing/data/models.py` (NEW dataclass validators) + `swing/data/repos/` (NEW repo functions) + `swing/web/routes/` for `§<section>` citations + add each to pre-Codex byte-fidelity scope.

### §4.2 NEW expansions banked at T2.SB6b (#6 + #7) — FIRST RUN BINDING for T2.SB6c

6. **NEW Expansion #6 — content-completeness audit** (T2.SB6b lesson; FIRST RUN BINDING here): for each spec data-surface checklist item (especially §5.10 8-item checklist + Phase 13 brainstorm §7.2 Q4 architectural surfaces), pre-Codex review MUST enumerate the implementer's per-field disposition explicitly (LIVE / V1 PLACEHOLDER / V1 STUB) BEFORE Codex invocation. Walk each spec data-surface item + ask "does my code provide LIVE data or a STUB?". T2.SB6c is a closure dispatch — V1 STUBs are EXPLICITLY in scope to fix; the audit lights up gaps that this dispatch should close, not bank for V2.
7. **NEW Expansion #7 — cross-row semantic audit on operator-input flows** (T2.SB6b lesson; FIRST RUN BINDING here): for any new POST handler that consumes operator input AND looks up cross-row state (`trades`, `pattern_evaluations`, `watchlist_close_track_flags`, etc.), pre-Codex review MUST enumerate the SCOPE of the lookup (ticker / pattern_class / candidate / pipeline_run / etc.) + cross-check against the spec's wording for the lookup semantics. The label_source split in T2.SB6b Codex R1 MAJOR #3 was the canonical example — this dispatch fixes it.

### §4.3 Cumulative schema-CHECK widening discipline (T3.SB2 hotfix + Phase 12 C.A + Phase 12 C.C lessons)

8. **§A.14 paired atomic landing** (Phase 12 C.A return report §11.#2): schema CHECK widening + Python constant widening + dataclass `__post_init__` validator + read-path mapper extension + all discriminating tests MUST land in ONE atomic task/commit. Splitting across tasks creates inconsistent-system-state window.
9. **N-mirror auditing** (T3.SB2 hotfix `cf3c489`): when introducing a new constant mirrored elsewhere, grep ALL `swing/` modules for hardcoded copies + add discriminating tests that exercise EACH downstream consumer through the production code path (NOT mocked at a higher boundary).
10. **Schema-CHECK + semantic contract paired discipline** (T2.SB6a R1 CRITICAL #1 NEW gotcha): dataclass `__post_init__` MUST mirror ALL semantic invariants from spec/plan (cache key shapes; partial-index existence semantics; cross-column uniqueness only enforced by partial UNIQUE indexes) — NOT just the schema CHECK.
11. **Manual-input vs service-only constant separation** (Phase 12 C.C R1 M#4 + R2 M#1): if a constant has both manual-operator-input surfaces (CLI validators; form validators) AND service-only surfaces, isolate the manual surface allowlist from the service-only allowlist.

### §4.4 Migration runner discipline (Phase 9 + Phase 12 + Phase 13 cumulative)

12. **Backup-gate strict equality**: `pre_version == 20 AND target >= 21` (NOT `<=`). Copy Phase 9 Sub-bundle A backup-gate clause VERBATIM. The `<=` form would fire for multi-version jumps + bypass the v20→v21 boundary's own gate.
13. **`executescript()` implicit-COMMIT**: migration runner MUST use explicit `BEGIN`+`executescript`+`COMMIT` with try/except `rollback()` per `swing/data/db.py:_apply_migration` canonical implementation.
14. **`INSERT OR REPLACE` cascade-wipe**: NEW v21 INSERT paths must use SELECT-then-UPDATE-or-INSERT for any upsert intent against tables with FK references or audit-trail intent.

### §4.5 Read-path mapping + write-path discipline

15. **Read-path mapping must keep pace with write-path** (T3.SB3 R1 M#1): when widening a dataclass with a new field (or adding a new column), grep ALL `_row_to_<table>` mapper functions in the same module AND extend them in the SAME task with column-position comments + 2 round-trip discriminating tests (persist via write path + read back via public reader; assert equality NULL + non-NULL).
16. **Schema-version-aware INSERT for newly-widened columns** (T3.SB1 precedent at `swing/data/repos/fills.py:51-53`): runtime branch via `PRAGMA table_info` between legacy-column-list and new-column-list INSERTs preserves pre-v21 fixtures unchanged. NULLable columns (this dispatch's columns) may not need this pattern; brainstorming to confirm.

### §4.6 V1 simplification banking discipline (NEW T2.SB6b gotcha)

17. **Every V1 placeholder/stub/simplification MUST be enumerated in return report §6 WITH V2 dependency cited**. T2.SB6c is a closure dispatch — V1 STUBs are EXPLICITLY in scope to fix, NOT bank again. If a V1 stub from T2.SB6b §6 cannot land in T2.SB6c, brainstorming must surface the BLOCKING dependency + re-bank with updated V2 dependency.

### §4.7 Form-driven route discipline (T3.SB3 + cumulative)

18. **Server-recompute at POST** (T3.SB3 R1 M#2 LOCK): all POST handlers re-derive audit envelopes from canonical state at POST time. T2.SB6c Q4 flag POST handlers inherit.
19. **HTMX 3-surface discipline** (Phase 5 R1 M1+M2 + Phase 6 I3): all new POST routes carry `hx-headers='{"HX-Request": "true"}'` + return `204 + HX-Redirect: <url>` (NOT 303) + target route registered in app routes.
20. **Hidden anchor 4-tier rejection ladder** (T3.SB1): if any new T2.SB6c form has hidden audit anchors driving POST validation, apply 4-tier rejection (malformed JSON → 400 + clear anchor on recovery).

### §4.8 Cumulative process discipline

21. **NO Co-Authored-By footer** — cumulative ~360+ commit streak ZERO trailer drift through T2.SB6b housekeeping; do NOT regress.
22. **`python -m swing.cli` from worktree cwd**, NOT bare `swing`.
23. **ASCII-only on runtime CLI paths** + ASCII-only narrative text in templates (T2.SB6b R1 MAJOR #7 em-dash lesson).
24. **TDD per task** via `superpowers:test-driven-development`.
25. **Edit tool for per-file edits** when fixing E501 / type / import-order — do NOT bulk-rewrite.

---

## §5 Open questions for brainstorming-paired triage

The brainstorming implementer will surface + propose dispositions; operator-paired triage during brainstorming refines. Expected OQ count 6-10 based on Phase 13 brainstorm precedent (12 OQs).

**OQ-1**: Backfill semantics for `trades.candidate_id` for existing trades — NULL (default) vs heuristic ticker+date match within tolerance?

**OQ-2**: Should SB6c include Q4 surfaces (Web routes + CLI subcommands + watchlist UI badge + auto-clear-on-position-open), or just v21 schema landing + SB6 closure wiring?

**OQ-3**: Should v21 migration backup-gate use `pre_version == 20` strict equality (per gotcha lesson; minimal risk), or extend to `pre_version >= 16` (multi-version backup safety net)?

**OQ-4**: Cleared_by_reason enum scope — just `('operator_explicit', 'position_opened')` + NULL, or include other values surfaced from operating history?

**OQ-5**: Watchlist-flag partial UNIQUE index semantics — `WHERE cleared_ts IS NULL` (active-only uniqueness) vs `WHERE 1=1` (all-time uniqueness, blocks re-flag after clear)?

**OQ-6**: Outcome distribution bucketing precision — by what threshold defines "reached 1R" + "hit stop"? Spec §5.10 line 773 may not specify; brainstorming to confirm.

**OQ-7**: Phase 13 brainstorm §7.2 D-Q4.2 brainstorm-default "Web + CLI both" — operator may want to confirm both surfaces still desired (no narrowing to one).

**OQ-8**: Migration backup file naming for v21 — `swing-pre-phase13-sb6c-migration-<ISO>.db` (per Phase 13 precedent) OR `swing-pre-v21-migration-<ISO>.db` (per schema-version-direct naming)?

**OQ-9**: Read-path mapper extension scope — `_row_to_trade` extends with 2 NEW columns (candidate_id + pattern_evaluation_id); brainstorming to confirm column-position assignment (e.g., row[24] + row[25] for 28+2-column trades schema).

**OQ-10**: Sub-bundle decomposition — SB6c brainstorm to propose task decomposition (likely T-A.6c.1 v21 migration + T-A.6c.2 atomic constants/validators/mappers + T-A.6c.3 chart-surface wiring + T-A.6c.4 review form data-completeness + T-A.6c.5 metric tile data-completeness + T-A.6c.6 queue weather-state + T-A.6c.7 [optional Q4 surfaces if OQ-2 yes] + T-A.6c.X closer). Brainstorming to refine.

---

## §6 Done criteria for brainstorming output

The brainstorming-phase spec at `docs/superpowers/specs/<date>-phase13-t2-sb6c-v21-schema-and-closure-design.md` MUST cover:

- [ ] **§1 Status + scope summary** — v21 schema deltas (3) + SB6 closure scope (Gap A + B items) + (optional) Q4 surfaces per OQ-2.
- [ ] **§2 v21 schema delta detailed design** — per delta: column shape + NULL/NOT-NULL + DEFAULT + CHECK constraints + FK constraints + indexes + backfill semantics + paired Python constant + dataclass `__post_init__` validator + paired tests; NEW table `watchlist_close_track_flags` per Phase 13 brainstorm §7.2 verbatim.
- [ ] **§3 SB6 closure consumer mapping** — per Gap A + B item: which v21 delta unblocks it (if any); wiring required (VM extension; template extension; route handler; service-layer changes); per-task disposition LIVE / RESOLVED / V2-NEW (V2-NEW should be exception not rule for this dispatch).
- [ ] **§4 Atomic-landing strategy per §A.14** — schema CHECK + Python constant + dataclass validator + read-path mapper + ALL discriminating tests land in SAME task; enumerated explicitly per delta.
- [ ] **§5 Test scope projection** — fast tests + slow tests + cross-bundle pins + operator-witnessed gates count + cumulative test delta forecast.
- [ ] **§6 Sub-bundle decomposition** — proposed task decomposition (likely T-A.6c.1..T-A.6c.X) with per-task acceptance criteria + cross-task dependency map.
- [ ] **§7 OQ disposition table** — per-OQ brainstorm recommendation + operator-paired triage outcome + binding decisions.
- [ ] **§8 LOCKs + watch items** — per-task LOCKs + cumulative-discipline watch items inherited from this brief §4.
- [ ] **§9 Forward-binding lessons + V2 candidates** — banking for future arcs (Phase 13.5; T4.SB; V2 dispatch).
- [ ] **§10 References** — Phase 13 spec; Phase 13 plan; T2.SB6b return report; this brief; relevant CLAUDE.md gotchas.

Brainstorming chain expected 3-7 Codex rounds (NEW expansions #6 + #7 FIRST RUN at brainstorm phase; schema complexity + 3 deltas × atomic-landing discipline + cross-row semantic surfaces → likely R3-R5 convergence).

---

## §7 References

- **Phase 13 spec** at `docs/superpowers/specs/2026-05-18-phase13-charts-patterns-autofill-usability-design.md` — §5.10 closed-loop surface + §C.1 chart renderer inventory + §C.2 cache key shape + §C.3 dashboard chart placement + §4.6 Theme 2 annotated chart deliverable + §7.2 Q4 close-tracking flag architectural decisions D-Q4.1..D-Q4.7.
- **Phase 13 plan** at `docs/superpowers/plans/2026-05-18-phase13-charts-patterns-autofill-usability-plan.md` — §G.9 T-A.6.X task enumeration + §G.10 T4.SB usability triage scope + §H.3 cross-bundle pin schedule.
- **T2.SB6b return report** at `docs/phase13-t2-sb6b-return-report.md` — §6 V1 simplifications + V2 candidates; §7 operator-paired gates S6+S7 V2-deferred.
- **T2.SB6a return report** at `docs/phase13-t2-sb6a-return-report.md` — substrate API surface; 3 NEW expansion proposals banked for 24th validation.
- **T2.SB6 partial-completion return report** at `docs/phase13-t2-sb6-return-report.md` — original 8-task scope before partial split.
- **CLAUDE.md gotchas relevant to T2.SB6c** (top 8 anticipated; brainstorming to enumerate all applicable):
  - Schema-CHECK widening MUST audit ALL Python-side surface guards (T3.SB2 hotfix `cf3c489`)
  - Schema-CHECK + Python-constant + dataclass-validator MUST land in same task (Phase 12 C.A T-A.2)
  - Schema-coverage Python constant is NOT necessarily the manual-input allowlist (Phase 12 C.C R1 M#4)
  - Read-path mapping must keep pace with write-path (T3.SB3 R1 M#1)
  - Migration runner backup-gate strict equality (Phase 12 C.A §0.5)
  - `executescript()` implicit-COMMIT (Phase 7 Sub-A R1 M3)
  - `INSERT OR REPLACE` cascade-wipe (Phase 8 daily-management spec §4.2)
  - **NEW** Schema-CHECK + Python-constant + dataclass-validator EXTENDS to semantic contracts (T2.SB6a R1 CRITICAL #1)
  - **NEW** F6 transient-empty at construction barrier when helper accepts dataclass parameter (T2.SB6a R1 MAJOR #2)
  - **NEW** Pre-Codex 5-expansion discipline does NOT catch CONTENT-completeness vs spec text (T2.SB6b R1 lessons)
  - **NEW** V1 simplification banking discipline (T2.SB6b lessons)

---

## §8 Post-brainstorming workflow

1. **Brainstorming output → operator-paired triage** — OQs resolved; spec doc updated with binding dispositions; commit at end of brainstorming session.
2. **Brainstorming SHIPPED → housekeeping** — orchestrator-side: phase3e-todo new top entry; orchestrator-context current state refresh; CLAUDE.md line 3 refresh + any new gotchas surfaced; archive-split per size-check trigger.
3. **Writing-plans dispatch** — orchestrator drafts writing-plans dispatch brief consuming the SB6c spec; inline implementer prompt; operator dispatches.
4. **Executing-plans dispatch** — sub-bundle decomposition per writing-plans output; orchestrator-paced dispatches OR single executing-plans bundle per sub-bundle complexity.
5. **T4.SB UNBLOCKED post-SB6c-SHIPPED** — operator's PAUSE-FOR-LIST-ADDITIONS still binding; T4.SB usability triage list addition required before T4.SB dispatch brief commissioning per `project_phase13_t4_sb_pause_for_list_additions` BINDING memory. Q4 close-tracking flag schema pulled forward to v21 (this dispatch); T4.SB scope shrinks to Theme 4 usability work only.

---

## §9 NON-scope (V2 / future arc)

- Phase 13.5 drift surfaces (feature_distribution_log_json accumulation; ≥1 month operating data required)
- ZERO new Schwab API calls — L2 LOCK preserved through this dispatch
- Interactive client-side JS chart library (V2)
- Per-row sparklines / multi-timeframe toggle / annotation editor (V2)
- Operator-supplied T4.SB usability triage items (separate operator action; PAUSE-FOR-LIST-ADDITIONS binding)

---

*End of brainstorming dispatch brief. Phase 13 T2.SB6c — v21 schema (3 deltas) + SB6 closure (Gap A + B items) + (optional Q4 surfaces per OQ-2). Full copowers workflow per operator decision. v20 LOCKED streak ENDS with this dispatch; ~10 sub-bundles since T-A.1.1 v20 landing. ~360+ cumulative ZERO Co-Authored-By footer drift streak preserved through this brief commit. PAUSE-FOR-LIST-ADDITIONS for T4.SB still binding — operator's added usability triage items separate from this dispatch.*
