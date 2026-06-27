# Phase 13 T2.SB6c — Brainstorming-phase return report

**Status:** BRAINSTORMING COMPLETE on branch `phase13-t2-sb6c-v21-closure-brainstorm` at HEAD `be77115`. Branched from main HEAD `5ca64c3` (post-dispatch-brief commit). 9 commits total (1 initial spec + 8 Codex MCP adversarial-review fix bundles). Codex MCP chain converged at **R8 NO_NEW_CRITICAL_MAJOR** (R1-R7 each surfaced new MAJOR findings closed in turn; R8 verdict cleared with 1 minor closed inline).

**Final spec:** `docs/superpowers/specs/2026-05-21-phase13-t2-sb6c-v21-schema-and-closure-design.md` (724 lines; ASCII + spec-convention non-ASCII for section anchors / em-dashes per project precedent).

**Inline self-verification at brainstorm close:**
- `ruff check swing/` → All checks passed (brainstorming touches docs/ only; no swing/ code).
- Schema v20 UNCHANGED at brainstorm phase (only spec docs added/edited).
- ZERO `Co-Authored-By` footers across all 9 commits (~360+ cumulative streak preserved).

---

## §1 Commits

| Commit | Title |
|---|---|
| `743075d` | docs(phase13): T2.SB6c v21 schema + SB6 closure brainstorming spec |
| `923961f` | docs(phase13): close T2.SB6c Codex R1 — candidates.evaluation_run_id + 5 majors + 2 minors |
| `02afd9a` | docs(phase13): close T2.SB6c Codex R2 — 4 majors + 1 minor |
| `722eb77` | docs(phase13): close T2.SB6c Codex R3 - 3 majors + 2 minors |
| `7578d16` | docs(phase13): close T2.SB6c Codex R4 - 3 majors + 2 minors |
| `6d2a0c7` | docs(phase13): close T2.SB6c Codex R5 - 3 majors + 1 minor |
| `41c7457` | docs(phase13): close T2.SB6c Codex R6 - 3 majors + 1 minor |
| `161733e` | docs(phase13): close T2.SB6c Codex R7 - 1 major + 1 minor |
| `be77115` | docs(phase13): close T2.SB6c Codex R8 minor - test forecast totals |

ZERO `Co-Authored-By` footers across all 9 commits.

---

## §2 OQ disposition table (preview for operator-paired triage)

14 OQs surfaced (10 from brief + 4 NEW during brainstorming). Brainstorm-recommended dispositions:

| OQ | Disposition |
|---|---|
| **OQ-1** Backfill semantics | NULL only (no heuristic match) |
| **OQ-2** SB6c includes Q4 surfaces? | **NO** — Q4 surfaces locked to T4.SB per plan §G.10 |
| **OQ-3** Backup-gate predicate | strict `pre_version == 20 AND target >= 21` |
| **OQ-4** Cleared_by_reason enum | **N/A** — already locked in v20 (`operator_cleared`/`auto_cleared_on_position_open`) |
| **OQ-5** Watchlist-flag partial UNIQUE | **N/A** — already locked in v20 (`WHERE cleared_at IS NULL`) |
| **OQ-6** Outcome bucketing thresholds | `reached_1r` = max daily high since entry >= entry_price + (entry_price - initial_stop); `hit_stop` = any fill at <= initial_stop OR closed with realized_R<0 |
| **OQ-7** D-Q4.2 web+CLI confirmation | **N/A for SB6c** — Q4 surfaces deferred to T4.SB |
| **OQ-8** Backup file name | `swing-pre-phase13-sb6c-migration-<ISO>.db` |
| **OQ-9** Column position assignment | row[52]=candidate_id; row[53]=pattern_evaluation_id |
| **OQ-10** Sub-bundle decomposition | 5 tasks T-A.6c.1..T-A.6c.5 (concurrent dispatch T-A.6c.1+2+3 recommended) |
| **OQ-11** *(NEW)* trades.candidate_id lifecycle | Populate at trade-entry-form lock time via `candidates.evaluation_run_id` JOIN through `pipeline_runs.evaluation_run_id`; NULL for manual_off_pipeline |
| **OQ-12** *(NEW)* trades.pattern_evaluation_id lifecycle | **CLOSURE-COMMITTED** at T-A.6c.4: thread anchor via hidden form input + 5-tier rejection + claim consistency-check gate; manual_off_pipeline persists NULL |
| **OQ-13** *(NEW)* Metric tile cohort denominator | LEFT JOIN from confirmed pattern_evaluations to trades via candidate_id; suppression at denominator<5 |
| **OQ-14** *(NEW)* Volume profile data path | `OhlcvCache.get_or_fetch(ticker, window_days=80)` — fetch-on-miss ACCEPTED for review surface |

---

## §3 Sub-bundle decomposition (preview)

5 tasks proposed with concurrent dispatch recommendation:

```
T-A.6c.1 (v21 migration; foundation; ~17 paired tests + 3 backup-gate tests + 1 cross-bundle pin)
    |
    +---> T-A.6c.2 (Gap A chart-surface wiring; ~11 tests; no schema dep — could run in parallel)
    |
    +---> T-A.6c.3 (Gap B.1/B.2/B.6 no-schema data-completeness; ~13 tests)
    |
    +---> T-A.6c.4 (Gap B.3/B.4/B.5 v21-dependent + entry-form anchor threading + entry-path mapping fix + VM/builder extensions; 31 tests; consumes Delta A + B)
              |
              +---> T-A.6c.5 (closer E2E + ruff)
```

**Concurrent dispatch (recommended)**: T-A.6c.1 + T-A.6c.2 + T-A.6c.3 in parallel; T-A.6c.4 sequential after T-A.6c.1; T-A.6c.5 sequential after all. Expected wall-clock savings ~30-40%.

**Total test forecast**: ~81 fast tests + 1 fast E2E (within brief's expected ~+80-150 range).

---

## §4 Codex MCP adversarial chain shape

Convergence path (8 rounds; brief expected 3-7):

| Round | Verdict | Critical | Major | Minor | Cumulative resolved |
|---|---|---|---|---|---|
| R1 | ISSUES_FOUND | 1 | 5 | 2 | 8 (R1 fix bundle at `923961f`) |
| R2 | ISSUES_FOUND | 0 | 4 | 1 | 5 (R2 fix bundle at `02afd9a`) |
| R3 | ISSUES_FOUND | 0 | 3 | 2 | 5 (R3 fix bundle at `722eb77`) |
| R4 | ISSUES_FOUND | 0 | 3 | 2 | 5 (R4 fix bundle at `7578d16`) |
| R5 | ISSUES_FOUND | 0 | 3 | 1 | 4 (R5 fix bundle at `6d2a0c7`) |
| R6 | ISSUES_FOUND | 0 | 3 | 1 | 4 (R6 fix bundle at `41c7457`) |
| R7 | ISSUES_FOUND | 0 | 1 | 1 | 2 (R7 fix bundle at `161733e`) |
| R8 | **NO_NEW_CRITICAL_MAJOR** | 0 | 0 | 1 | 1 (R8 minor closed at `be77115`) |

**Total findings closed**: 1 CRITICAL + 22 MAJOR + 11 MINOR = 34 findings; all RESOLVED (zero ACCEPT-WITH-RATIONALE; brainstorm-phase scope changes were absorbed in-place).

**The R1 CRITICAL was the most consequential finding**: my brainstorm spec proposed candidate-id lookup via `candidates.pipeline_run_id` but the table is actually keyed on `evaluation_run_id` (per migration 0001 line 26 + `swing/trades/origin.py:10-11` BINDING text). Without Codex catching this, the lookup SQL would have failed at first execution with "no such column" OR silently mis-matched candidates. The correction propagated to OQ-11 + Gap B.3 wiring + §6.4 entry service guidance.

---

## §5 Per-expansion pre-Codex verdict (25th cumulative C.C lesson #6 validation)

**First-run application of NEW Expansions #6 (content-completeness audit) + #7 (cross-row semantic audit on operator-input flows) at brainstorm phase** — banked at T2.SB6b R1 lessons; T2.SB6c is the inaugural binding execution.

| Expansion | Pre-Codex orchestrator-side verdict | Codex-caught | Net assessment |
|---|---|---|---|
| #1 hardcoded-duplicate audit (T3.SB2 hotfix `cf3c489`) | CLEAN at brainstorm | None for hardcoded duplicates per se; but R7 caught VM/builder field-add omissions which are arguably in this family | NOTABLE (sub-family of mirror-discipline applied to dataclass fields) |
| #2 brief-vs-spec source-of-truth (T2.SB4 R1 M1) | **CAUGHT brief §2.3 OBSOLETE** at pre-Codex (the brainstorm spec itself flagged the discrepancy in §0) | None more from R1 directly | CLEAN |
| #3 schema-CHECK-vs-semantic-contract (T2.SB6a R1 CRITICAL #1) | CLEAN at brainstorm — no new schema CHECKs introduced, only nullable FK columns | None | CLEAN |
| #4 CLAUDE.md gotcha specific-scenario trace (T2.SB6a R1 MAJOR #2) | **PARTIAL FAIL** — pre-Codex did NOT trace the candidates-keyed-on-evaluation_run_id scenario through OQ-11 SQL; R1 CRITICAL caught it | R1 CRITICAL #1 | NOTABLE (lesson: when writing SQL skeletons in a spec, EACH column reference must trace to the source schema; pre-Codex specific-scenario trace expanded with "every SQL skeleton's columns verified against the actual schema migration files") |
| #5 cross-section spec inventory grep (T2.SB6a R1 MAJOR #3) | CLEAN at brainstorm — spec §5.10 inventory enumerated + per-item disposition documented at §3.3 | None directly | CLEAN |
| **#6 content-completeness audit (NEW; FIRST RUN BINDING)** | **VERIFIED at brainstorm** — §3.3 audit table enumerates every §5.10 8-item checklist item with per-field disposition (LIVE / V1 PARTIAL / V1 STUB); post-SB6c ZERO V1 STUBs remain | None — Codex found zero content-completeness gaps | CLEAN (validated as effective scope expansion) |
| **#7 cross-row semantic audit on operator-input flows (NEW; FIRST RUN BINDING)** | **VERIFIED at brainstorm** — §3.2 enumerates SCOPE of each cross-row lookup (per-candidate for Gap B.3; per-candidate cohort for Gap B.4; per-pattern_class cohort for Gap B.5); discriminating ticker-proxy-regression test planted | R1 CRITICAL #1 caught the wrong join column (evaluation_run_id vs pipeline_run_id) — arguably an Expansion #4 specific-scenario trace gap rather than a #7 cross-row semantic scope gap | NOTABLE (Expansion #7 caught the SCOPE of the lookup correctly — per-candidate not per-ticker — but missed the SCHEMA correctness of the JOIN; lesson: Expansion #7 verifies semantic scope; Expansion #4 verifies schema/column correctness of the queries) |

**Cumulative result**: 25th cumulative C.C lesson #6 validation = NOTABLE — first run with all 7 expansions (5 original + 2 new) binding; Expansion #6 + #7 effectiveness CONFIRMED. 2 NEW expansion-discipline lessons banked:
1. **Expansion #4 refinement** (BANKED for 26th cumulative validation): pre-Codex specific-scenario trace expanded with "every SQL skeleton's columns verified against the actual schema migration files".
2. **Expansion #7 boundary clarification**: cross-row semantic SCOPE audit (per-candidate vs per-ticker, etc.) does NOT subsume column/JOIN correctness; Expansion #4 (or a new sub-expansion) owns that.

---

## §6 V1 simplifications + V2 candidates banked

| V1 simplification | V2 dependency | Banked for |
|---|---|---|
| Existing pre-v21 trades persist `candidate_id = NULL` (no retroactive heuristic match) | OQ-1 disposition; operator-paired investigation of data quality required | V2 enrichment if operator surfaces value |
| Multi-pattern_class trade backlink = single anchor; one trade attaches to ONE pattern_evaluation | many-to-many `trade_pattern_evaluations` link table to capture "this trade was visible against N detector evaluations at lock time" | V2 schema dispatch |
| Volume profile fetch-on-cache-miss accepted as desired behavior | `get_cached_only` variant for pure read-only scenarios | V2 cache architecture |
| Backup-gate strict-equality skips backup on multi-version jump (v19→v21) | `--enforce-stepwise` flag on `swing db-migrate` to refuse multi-version jumps | V2 migration-runner enhancement |
| `pattern_evaluations.candidate_id` direct column (alternative to JOIN via pipeline_runs.evaluation_run_id) | If Phase 13.5+ surfaces require frequent per-candidate cross-row lookups, this column would eliminate the two-table JOIN | V2 schema dispatch |
| Phase 6 `chart_pattern_algo` enum (`none`/`flag`) disjoint from Phase 13 detector enum | Unify the two enums via a separate spec dispatch | V2 schema migration |

No new V1 STUBs introduced by SB6c — closure dispatch intent honored. All T2.SB6b §6 V1 simplifications targeted by SB6c are RESOLVED (closure-committed) or kept-explicit-in-V2-bank.

---

## §7 Forward-binding lessons banked

1. **Brief-vs-actual schema reality check (Expansion #2 effective)**: T2.SB6c brainstorm caught the brief §2.3 OBSOLETE proposal at pre-Codex review. Future dispatches: when a brief proposes "NEW table X", verify against `swing/data/migrations/` before consuming brief verbatim. Pre-empt: dispatch-brief authoring at orchestrator side should grep migrations + spec line locks before publishing.

2. **SQL skeleton column verification (NEW Expansion #4 refinement)**: every SQL JOIN written into a spec MUST have its column names verified against the actual schema migration files. The R1 CRITICAL caught `candidates.pipeline_run_id` (non-existent) vs `candidates.evaluation_run_id` (canonical per migration 0001). Pre-empt: at brainstorm phase, treat any SQL JOIN as a load-bearing claim requiring schema-file verification.

3. **Function name verification (NEW)**: spec references to existing functions MUST be verified against actual source. R6 caught `resolve_trade_origin` vs `derive_trade_origin` at `swing/trades/origin.py:52`. Pre-empt: at brainstorm phase, grep for any cited function name before publishing.

4. **Hidden-anchor missing-value semantics (NEW)**: every hidden form field driving POST-time validation MUST specify the missing-value behavior. R5 caught `claimed_pattern_evaluation_anchor` missing semantics; R6 caught `pipeline_run_id_at_form_render` missing semantics. Default discipline: missing → safe default (typically `False` for boolean flags); rejects fire on missing-while-required pattern.

5. **Server-derived vs form-submitted value-domain discipline (NEW)**: validation rules that reference `trade_origin` MUST clarify whether the rule checks SERVER-DERIVED (via `swing/trades/origin.py:derive_trade_origin`) or FORM-SUBMITTED (UI origin field). R5 + R7 closed wording slippages between the two domains. Pre-empt: spec rules involving derived domain values MUST cite the resolver function + line number.

6. **EntryPath mapping load-bearing for trade_origin derivation (NEW)**: `derive_trade_origin(conn, ticker, entry_path: EntryPath)` cannot distinguish `pipeline_watch_hyp_recs` from `pipeline_watch_manual` if all web POSTs hardcode `EntryPath.MANUAL_WEB_FORM`. R6 caught this load-bearing defect at `swing/web/routes/trades.py:1095`. SB6c T-A.6c.4 fixes it as a side-effect of anchor-threading. Forward-binding: any future spec that consumes derived `trade_origin` MUST verify the entry-path mapping at the consumer's POST handler.

7. **VM/builder fields are part of anchor-threading scope (NEW)**: form-render hidden anchors require VM dataclass fields + builder population + template emission + POST validation. R7 caught my scope omitting the VM/builder layer. Pre-empt: when specifying a new form anchor, enumerate all 4 layers (VM field + builder population + template emission + POST validation) AND their discriminating tests.

8. **Schema-version-aware INSERT for nullable columns (R1 expansion)**: even nullable column extensions warrant the `PRAGMA table_info` runtime branch pattern (T3.SB1 fills.py:51-53 precedent) for robustness against v20-fixture tests that bypass migration. Codex R1 MAJOR #2 flagged my "no SVAI needed for nullables" conclusion as unsafe.

---

## §8 References

- **Brief** at `docs/phase13-t2-sb6c-v21-closure-brainstorm-dispatch-brief.md` (HEAD `5ca64c3`)
- **Spec** at `docs/superpowers/specs/2026-05-21-phase13-t2-sb6c-v21-schema-and-closure-design.md` (HEAD `be77115`)
- **Phase 13 source spec** at `docs/superpowers/specs/2026-05-18-phase13-charts-patterns-autofill-usability-design.md`
- **Phase 13 plan** at `docs/superpowers/plans/2026-05-18-phase13-charts-patterns-autofill-usability-plan.md`
- **T2.SB6b return report** at `docs/phase13-t2-sb6b-return-report.md`
- **T2.SB6a return report** at `docs/phase13-t2-sb6a-return-report.md`
- **CLAUDE.md** at `CLAUDE.md`

---

## §9 Streaks preserved

- **ZERO `Co-Authored-By` footer trailer drift** across all 9 brainstorming commits (~360+ cumulative streak preserved through this dispatch).
- **C.C lesson #6 cumulative validations**: 22x CLEAN through T3.SB3 + 23rd NOTABLE at T2.SB6a (3 expansions banked) + 24th NOTABLE at T2.SB6b (FIRST RUN applying all 5 original expansions; 2 NEW proposals #6 + #7 banked) + **25th NOTABLE at T2.SB6c (FIRST RUN applying all 7 expansions; Expansions #6 + #7 effectiveness CONFIRMED; 2 NEW lessons banked for 26th validation: Expansion #4 SQL-column verification refinement; Expansion #7 boundary clarification re schema/column correctness)**.
- **10 of 11 Phase 13 sub-bundles SHIPPED**; SB6c brainstorm output unblocks the SB6c writing-plans + executing-plans dispatch sequence. T4.SB remains paused per `project_phase13_t4_sb_pause_for_list_additions` BINDING memory.

---

## §10 Post-brainstorming handback

Brainstorming complete. Orchestrator-side next steps:

1. **Operator-paired triage of 14 OQs** per §2 above; refinement of brainstorm-recommended dispositions into BINDING decisions.
2. **Spec updates** in-place if operator triage diverges from brainstorm recommendations.
3. **Writing-plans dispatch brief** authored consuming the brainstorming spec + operator-paired OQ decisions.
4. **Phase 3e-todo + orchestrator-context refresh** to reflect SB6c brainstorming SHIPPED.
5. **CLAUDE.md line 3 refresh** to reflect 25th cumulative C.C lesson #6 validation outcome + Expansion #6 + #7 first-run effectiveness confirmation.
6. **Codex MCP session state** at `~/.copowers/sessions/...` updated per adversarial-critic skill's post-output step.

PAUSE-FOR-LIST-ADDITIONS for T4.SB still binding — separate from this dispatch.

---

*End of T2.SB6c brainstorming return report. Codex MCP chain converged at R8 NO_NEW_CRITICAL_MAJOR after 8 rounds (1 CRITICAL + 22 MAJOR + 11 MINOR cumulative findings, ALL RESOLVED in-place; zero ACCEPT-WITH-RATIONALE). 25th cumulative C.C lesson #6 validation = NOTABLE; Expansion #6 + #7 effectiveness confirmed; 2 NEW expansion-discipline lessons banked. ~360+ ZERO Co-Authored-By footer streak preserved.*
