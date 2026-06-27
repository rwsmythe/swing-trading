# Phase 13 T2.SB6a — Substrate Codex completion dispatch brief

**Status:** READY FOR DISPATCH. Drafted 2026-05-21 PM #3 post-T2.SB6 partial-ship at substrate level. Per operator decision 2026-05-21 PM #3 (Path C from 3-path analysis): the T2.SB6 partial-completion shipped charts.py + chart_renders cache helpers (load-bearing substrate) BUT deferred pre-Codex + Codex MCP chain; **T2.SB6a closes the discipline gap on the substrate alone** + merges via standard sub-bundle workflow + unblocks a separate T2.SB6b dispatch for the 6 remaining tasks.

**Branch:** `phase13-t2-sb6-closed-loop-surface` — EXISTING branch at HEAD `a9838a7` (substrate state); do NOT create new branch. Worktree already exists at `.worktrees/phase13-t2-sb6-closed-loop-surface`.

**Scope POSTURE**: this is a **Codex-completion dispatch on existing substrate state — NO new feature code expected**. The 3 shipped commits at HEAD (`e80101a` T-A.6.1 renderers + `255823b` T-A.6.2 cache helpers + `a9838a7` partial-completion return report) are FROZEN for substrate-only merge. Any code change in this dispatch should be a Codex fix-bundle ONLY, not new feature work. The deferred 6 tasks (review form + queue + metric tile + chart-surface integration + exemplars + closer) are rebranded as T2.SB6b + dispatched in a SEPARATE brief AFTER this substrate merges + housekeeping.

**Time estimate:** orchestrator wall-clock 2-4 hours operator-paced (per `feedback_time_estimates_overstated.md` ÷3-5x; small bounded scope = pre-Codex review + Codex chain only; expected 2-3 Codex rounds based on T2.SB5 + T3.SB3 precedent for similar-sized substrate dispatches; matches inherited cumulative pre-Codex discipline effectiveness).

---

## §1 Scope summary

**T2.SB6a = T2.SB6 substrate Codex-completion + merge unblock**. Closes the discipline gap on the substrate shipped at HEAD `a9838a7` per operator-decided Path C from the T2.SB6 partial-completion 3-path analysis.

| Task | Title | Posture |
|---|---|---|
| T-A.6a.1 | Pre-Codex orchestrator-side review on substrate (23rd cumulative C.C lesson #6 validation; BOTH scope expansions BINDING) | NEW dispatch step |
| T-A.6a.2 | Codex MCP adversarial-critic chain on substrate | NEW dispatch step |
| T-A.6a.3 | Substrate Codex-completion return report (extends `docs/phase13-t2-sb6-return-report.md` OR new `docs/phase13-t2-sb6a-return-report.md`) | NEW dispatch step |

### §1.1 What's already shipped at substrate HEAD `a9838a7` (FROZEN for this dispatch)

Per implementer's partial-completion return report (`docs/phase13-t2-sb6-return-report.md`):

| Commit | Task | Surface |
|---|---|---|
| `e80101a` | T-A.6.1 | `swing/web/charts.py` (524 lines NEW; 5 SVG-inline renderers per spec §C.1 LOCK: `render_watchlist_thumbnail_svg` + `render_hyprec_detail_svg` + `render_position_detail_svg` + `render_market_weather_svg` + `render_theme2_annotated_svg`); ASCII-only text discipline; `_assert_ascii_only` (body) + `_assert_title_no_math` (title `$`/`^`/`_`/`\` gate) defense-in-depth split; `_CHART_SURFACE_VALUES` imported from `swing/data/models.py` per L8 LOCK; 14 tests including cross-bundle pin row 10 (`test_theme1_theme2_shared_renderer_handles_5_v1_patterns`) lands GREEN |
| `255823b` | T-A.6.2 | `swing/data/repos/chart_renders.py` (+116 lines; `get_cached_chart_svg` + `refresh_chart_render` cache helpers per §C.2 LOCK) + 7 cache helper tests covering all 3 cache key shapes (run-bound / position_detail / theme2_annotated) + §A.13 session-anchor round-trip + §A.15 DELETE-then-INSERT atomic refresh wrapped in BEGIN IMMEDIATE / COMMIT per §A.12 |
| `a9838a7` | (return report) | `docs/phase13-t2-sb6-return-report.md` (259 lines; partial-completion documentation + §3 handoff enumerating each deferred task's file scope + LOCKs + tests + key disciplines) |

**Substrate baseline state**:
- 5484 fast tests / 2 skipped / 0 failed (+21 vs main HEAD `4e71787` baseline 5463)
- Ruff clean (0 E501)
- Schema v20 unchanged (no migrations)
- ZERO new Schwab API calls (substrate consumes OhlcvCache + pattern_evaluations + chart_renders only)
- ZERO Co-Authored-By trailer drift across all 3 commits
- 1 cross-bundle pin closure: row 10 (`test_theme1_theme2_shared_renderer_handles_5_v1_patterns`) GREEN

### §1.2 Inheritance from T3.SB3 + T2.SB5 forward-binding lessons (BINDING)

T2.SB6a inherits the same cumulative discipline as T2.SB6 originally would have (per T2.SB6 dispatch brief §1.1-§1.5):

1. **Read-path mapping must keep pace with write-path on widened columns** (T3.SB3 R1 M#1) — N/A for substrate (no new column writes; `chart_renders` table columns unchanged from T-A.1.1 v20 landing). BINDING for downstream T2.SB6b consumers.
2. **"Server-stamped" hidden form inputs are STILL tampering surfaces unless POST RECOMPUTES** (T3.SB3 R1 M#2) — N/A for substrate (no POST routes; pure renderers + cache helpers). BINDING for downstream T2.SB6b consumers.
3. **Audit envelope empty-state representation must be uniform** (T3.SB3 pre-Codex M#1; emit `None` not `"[]"`) — N/A for substrate (no audit envelopes). BINDING for downstream T2.SB6b consumers if any introduced.
4. **Pre-Codex orchestrator-side review with BOTH scope expansions** (T3.SB3 22nd cumulative) — **BINDING for T2.SB6a pre-Codex review** (23rd cumulative validation expected).
5. **Bad-exemplar isolation in retrieval functions** (T2.SB5 R1 M#1) — if `render_theme2_annotated_svg` consumes `template_match_nearest_exemplar_ids_json` (which it does per §4.6) AND iterates exemplar thumbnails (`exemplar_thumbnails: list[bytes] | None`), the iteration MUST honor per-exemplar try/except to skip bad bundles. Codex should verify.
6. **DTW Sakoe-Chiba band infeasibility on asymmetric series** (T2.SB5 R1 — informational) — N/A for substrate.
7. **Universe histogram POST-template** (T2.SB5 — informational) — N/A for substrate.

### §1.3 Inheritance from Theme 1 chart discipline (§A.9 + §C.1 LOCK; T2.SB6 brief §1.3)

8. **Matplotlib mathtext LOCK** — implementer's substrate already split into `_assert_ascii_only` (body text; allows `_` literal) + `_assert_title_no_math` (title; gates `$`/`^`/`_`/`\`). Codex should verify discipline holds across all 5 renderer functions + verify no leakage in error messages / annotations.
9. **HTMX OOB-swap partials must not lead with `<tr>`** (CLAUDE.md gotcha; informational) — N/A for substrate (no HTMX response paths).
10. **`base.html.j2` shared-VM-field propagation** — N/A for substrate (no VM changes). BINDING for T2.SB6b downstream.

### §1.4 Pre-Codex review BOTH scope expansions BINDING (per T3.SB2 hotfix `cf3c489` + T2.SB4 R1 M1)

11. **Expansion #1 (T3.SB2 hotfix `cf3c489` discipline; hardcoded-duplicate audit)**: grep `swing/` for hardcoded duplicates of any new T2.SB6a constants. Specifically:
    - `_CHART_SURFACE_VALUES` 5-tuple — verify canonical site at `swing/data/models.py` + verify `swing/web/charts.py` IMPORTS (does NOT redefine) per L8 LOCK
    - Chart size tuples — grep for `(200, 100)` / `(800, 500)` / `(400, 150)` / `(800, 600)` etc. across `swing/`; verify each is at the canonical site (likely module-level constants in `swing/web/charts.py`)
    - Renderer kwarg names / default values
12. **Expansion #2 (T2.SB4 R1 M1 lesson; cross-check brief vs spec source-of-truth)**: cross-check spec §C.1 + §C.2 BINDING text byte-for-byte vs the implementer's actual implementation. Specifically:
    - 5 renderer function signatures match §C.1 lines 395-403 verbatim (`render_watchlist_thumbnail_svg(*, ticker, bars, ma_lines)` + `render_hyprec_detail_svg(*, ticker, bars, pattern_evaluation)` + etc.)
    - Cache key shapes match §C.2 verbatim (run-bound = `(ticker, surface, pipeline_run_id)`; position-detail = `(ticker, surface)` with `pipeline_run_id=NULL`; theme2-annotated = `(ticker, surface, pipeline_run_id, pattern_class)`)
    - `BEGIN IMMEDIATE` / `COMMIT` discipline per §A.12 + DELETE-then-INSERT atomic per §A.15
    - Session-anchor read/write predicate alignment per §A.13 (writer + reader both use `last_completed_session(now())`)

---

## §2 Per-task acceptance criteria

| Task | Title | Acceptance |
|---|---|---|
| T-A.6a.1 | Pre-Codex orchestrator-side review on substrate (23rd cumulative C.C lesson #6) | Implementer dispatches focused reviewer subagent with this brief's §3 file-scope + §4 watch items + §6 LOCKs as anchors BEFORE invoking Codex MCP. Verdict captured in return report. **BOTH scope expansions BINDING** per §1.4 above. Verdict CLEAN OR find-then-fix BEFORE Codex (per T3.SB3 22nd cumulative precedent where pre-Codex caught 1 MAJOR + 2 MINORs that would have cost Codex rounds). |
| T-A.6a.2 | Codex MCP adversarial-critic chain on substrate | Invoke copowers Codex MCP adversarial-critic chain on the substrate diff (`main..HEAD`). Iterate fix-bundles until `NO_NEW_CRITICAL_MAJOR`. Expected 2-3 rounds based on T2.SB5 + T3.SB3 precedent for similar-sized substrate scope. Bank any ACCEPT-WITH-RATIONALE Minors in return report. |
| T-A.6a.3 | Substrate Codex-completion return report | Update `docs/phase13-t2-sb6-return-report.md` (or CREATE `docs/phase13-t2-sb6a-return-report.md`) with §3 Codex chain findings (per-round + per-finding) + §4 pre-Codex review verdict + §5 LOCK status post-Codex + §6 forward-binding lessons surfaced + §10 (if used) pre-Codex orchestrator-side review verdict. Mirror T3.SB3 / T2.SB5 return report shape. |

**Recommended ordering**: T-A.6a.1 (pre-Codex review FIRST per cumulative discipline) → T-A.6a.2 (Codex MCP after pre-Codex catches/fixes findings) → T-A.6a.3 (return report after Codex chain converges).

---

## §3 Files in scope

**Frozen at HEAD `a9838a7`** (no new code beyond Codex fix-bundles):
- `swing/web/charts.py` (524 lines; verify spec §C.1 fidelity)
- `swing/data/repos/chart_renders.py` (+116 lines; verify spec §C.2 fidelity)
- `tests/web/test_charts.py` (333 lines; 14 tests; verify cross-bundle pin row 10 still GREEN post-Codex)
- `tests/data/repos/test_chart_renders_repo.py` (192 lines; 7 tests; verify §A.12 + §A.13 + §A.15 disciplines)
- `docs/phase13-t2-sb6-return-report.md` (259 lines; extension target for Codex chain findings)

**Likely modified by Codex fix-bundles** (depending on findings):
- Any of the above 5 files
- `swing/data/models.py` (if `_CHART_SURFACE_VALUES` duplication is surfaced)
- New discriminating tests added per Codex fix-bundle (standard pattern)

**NOT in scope** (deferred to T2.SB6b dispatch):
- T-A.6.3 `/patterns/{candidate_id}/review` review form
- T-A.6.4 `/patterns/queue` active-learning prioritization
- T-A.6.5 `/metrics/pattern-outcomes` 9th metric tile
- T-A.6.6 Theme 1 chart surface integration + dashboard market weather
- T-A.6.6b `/patterns/exemplars` enhanced rendering (Deficiency 1 fold-in)
- T-A.6.7 T2.SB6 closer — integration E2E + cross-bundle pin row 11 un-skip + ruff sweep
- New route handlers / VMs / templates of any kind

---

## §4 Watch items

### §4.1 T2.SB6a-specific watch items

1. **Spec §C.1 + §C.2 + §A.9 + §A.12 + §A.13 + §A.15 LOCK fidelity**: substrate already implements; Codex chain verifies. Pre-Codex review (#11 + #12 above) cross-checks BEFORE Codex.
2. **`_CHART_SURFACE_VALUES` canonical site discipline** per L8 LOCK + plan §B.7 + Phase 12 C.A T-A.2 + T3.SB2 hotfix `cf3c489`: imported from `swing/data/models.py`; NOT redefined in `swing/web/charts.py`. Pre-Codex Expansion #1 grep verification BINDING.
3. **Matplotlib mathtext LOCK**: implementer's substrate ALREADY applies `_assert_title_no_math` discipline. Codex should verify discipline holds across ALL renderer paths (not just titles — also annotations + axis labels + suptitles + legend text).
4. **Cache invalidation pattern** per §A.15: DELETE-then-INSERT atomic refresh wrapped in `BEGIN IMMEDIATE` / `COMMIT` per §A.12. NO `INSERT OR REPLACE` on `chart_renders` table.
5. **Session-anchor read/write predicate alignment** per §A.13 LOCK: substrate's `refresh_chart_render` writer + `get_cached_chart_svg` reader MUST both use `last_completed_session(now())` predicate.
6. **External-API empty-result must be treated as transient** per CLAUDE.md gotcha — substrate's cache helpers MUST NOT blank existing rows on empty/error returns from upstream renderers (retain existing cache row; re-render on next pipeline run).
7. **`Literal[...]` type hints are NOT runtime-enforced** per T-A.1.5b R3 M#1 — if substrate introduces any `Literal[...]` fields on dataclasses (e.g., surface enum constraints), verify `__post_init__` frozenset validation.
8. **ASCII-only on any new CLI/print path** — N/A for substrate (no CLI surface introduced).

### §4.2 Substrate-frozen discipline

9. **NO new feature code beyond Codex fix-bundles**. The 6 deferred tasks are EXPLICITLY out of scope for this dispatch. Any deviation requires operator escalation.
10. **Branch base = main HEAD `4e71787`** at substrate creation; the existing branch is descendant. Verify NOT rebased.
11. **Substrate Codex chain may surface API issues that propagate into T2.SB6b design**. If substrate's renderer signature changes (e.g., Codex catches a kwarg shape that doesn't match spec §C.1 line 395-403 verbatim), document the impact in return report §5 for T2.SB6b dispatch brief author awareness.

### §4.3 Cumulative process discipline

12. **Pre-Codex orchestrator-side review (C.C lesson #6 BINDING; 23rd cumulative validation expected with BOTH SCOPE EXPANSIONS BINDING)** — reference: 22nd cumulative validation BANKED CLEAN at T3.SB3 with both expansions applied + 1 MAJOR + 2 MINORs caught BEFORE Codex.
13. **NO `Co-Authored-By` footer** — cumulative ~330+ commit streak ZERO trailer drift through T2.SB6 brief commit `f562100` + substrate ship; do NOT regress.
14. **Cite the discipline in commit messages** (matches all prior precedent).
15. **TDD per Codex fix-bundle** — write failing discriminating test → see fail → minimal fix → see pass → commit.

---

## §5 Done criteria

### §5.1 S1 (inline; implementer self-verifies before declaring T2.SB6a complete)

- [ ] Pre-Codex orchestrator-side review dispatched + verdict captured (23rd cumulative C.C lesson #6 validation; BOTH scope expansions applied per §1.4).
- [ ] Codex MCP adversarial-critic chain invoked + converged to `NO_NEW_CRITICAL_MAJOR` (expected 2-3 rounds).
- [ ] `python -m pytest -m "not slow" -q -n auto` PASS post any Codex fix-bundle. **Expected**: 5484 + ~5-15 new discriminating tests from Codex fixes = ~5489-5499 total; 0 failures; ≤2 skipped.
- [ ] `ruff check swing/` clean (0 E501).
- [ ] Schema version unchanged at v20.
- [ ] All commits on branch `phase13-t2-sb6-closed-loop-surface` have empty `Co-Authored-By` trailer.
- [ ] Substrate cross-bundle pin row 10 (`test_theme1_theme2_shared_renderer_handles_5_v1_patterns`) preserved GREEN post-Codex.
- [ ] Return report extended with Codex chain findings.

### §5.2 S2 (operator-paired post-merge — substrate-only constraints)

**The substrate has NO route surfaces — operator-paired browser gates are NOT runnable at substrate-merge alone.** S2-S8 gates from the original T2.SB6 brief §5.2 DEFER to T2.SB6b merge.

**Substrate-merge operator-paired verification (minimal)**:
- S0 (orchestrator-driven): main HEAD picks up substrate modules; `swing.web.charts` imports cleanly; `swing.data.repos.chart_renders.get_cached_chart_svg` + `refresh_chart_render` importable.
- S1 (inline): per §5.1 above.

---

## §6 LOCKs (do not deviate without operator escalation)

- **L1**: Substrate code is FROZEN at HEAD `a9838a7`. Codex fix-bundles only; NO new feature code.
- **L2**: Spec §C.1 + §C.2 + §A.12 + §A.13 + §A.15 BINDING verbatim.
- **L3**: ZERO new Schwab API calls (preserved from substrate ship).
- **L4**: ZERO schema changes (v20 LOCKED; chart_renders table already at T-A.1.1).
- **L5**: `_CHART_SURFACE_VALUES` imported from `swing/data/models.py` (canonical site).
- **L6**: Matplotlib mathtext LOCK — ASCII-only + `parse_math=False` defense-in-depth + NO `$`/`^`/`_` in titles.
- **L7**: Cache invalidation atomic per §A.15 + `BEGIN IMMEDIATE` / `COMMIT` per §A.12.
- **L8**: Session-anchor read/write predicate alignment per §A.13.
- **L9**: Branch base = main HEAD `4e71787`. Verify substrate branch is descendant.
- **L10**: Pre-Codex review BOTH scope expansions BINDING (Expansion #1 hardcoded-duplicate audit + Expansion #2 spec source-of-truth byte-fidelity).
- **L11**: Cross-bundle pin row 10 GREEN preserved post-Codex (do NOT regress).
- **L12**: 6 deferred tasks are EXPLICITLY out of scope. Deviation requires operator escalation.

---

## §7 Reference materials (read before dispatching)

- **Original T2.SB6 brief**: `docs/phase13-t2-sb6-closed-loop-surface-dispatch-brief.md` (316 lines; committed at `f562100`) — full 8-task scope including the 6 deferred tasks. Inherited LOCKs + watch items + cumulative discipline apply to substrate slice.
- **Implementer partial-completion return report**: `docs/phase13-t2-sb6-return-report.md` (259 lines; committed at `a9838a7`) — §3 handoff enumerates deferred task scope + LOCKs + tests + key disciplines.
- **Spec**: `docs/superpowers/specs/2026-05-18-phase13-charts-patterns-autofill-usability-design.md`:
  - §4.3 Chart rendering technology LOCK (matplotlib SVG inline; ASCII-only; parse_math=False)
  - §4.4 Cache architecture LOCK (chart_renders schema + caching semantics)
  - §A.9 + §A.10 Matplotlib mathtext LOCK (operator-witnessed browser verification BINDING)
  - §A.12 BEGIN IMMEDIATE / COMMIT transactional discipline
  - §A.13 Session-anchor read/write predicate alignment
  - §A.15 No INSERT OR REPLACE on audit-trail tables
- **Plan**: `docs/superpowers/plans/2026-05-18-phase13-charts-patterns-autofill-usability-plan.md`:
  - §C.1 Chart rendering technology LOCK (lines 391-405; renderer function signatures verbatim at line 395-403)
  - §C.2 chart_renders cache architecture LOCK (lines 407-419; cache key shapes verbatim)
  - §B.7 Constant placement LOCK (per Codex R2 Major #1 closure)
  - §H.3 cross-bundle pin schedule rows 10 + 11
- **T3.SB3 return report** at `docs/phase13-t3-sb3-return-report.md` §6 — 4 forward-binding lessons inherited; particularly #4 pre-Codex orchestrator-side review with BOTH scope expansions is load-bearing.
- **T2.SB5 return report** at `docs/phase13-t2-sb5-return-report.md` §8 — bad-exemplar isolation lesson (applies to `render_theme2_annotated_svg` exemplar_thumbnails iteration per §1.2 #5 above).
- **CLAUDE.md gotchas relevant to T2.SB6a**:
  - Matplotlib mathtext LOCK (BINDING per L6)
  - `Literal[...]` not runtime-enforced
  - Schema-CHECK widening MUST audit ALL Python-side surface guards (per T3.SB2 hotfix `cf3c489`)
  - External-API empty-result must be treated as transient when write-through-caching

---

## §8 Post-dispatch housekeeping checklist (orchestrator-inline)

When T2.SB6a merge ships:

1. **CLAUDE.md line 3 refresh** — update HEAD reference + mention T2.SB6a SHIPPED (substrate; partial-completion follow-up) + 23rd cumulative C.C lesson #6 validation (if CLEAN); mention any NEW gotchas surfaced; note remainder pending at T2.SB6b.
2. **phase3e-todo.md** — new top entry for T2.SB6a SHIPPED with Codex chain shape + ACCEPT-WITH-RATIONALE banks + forward-binding lessons + cross-bundle pin row 10 confirmation + T2.SB6b pending status.
3. **orchestrator-context.md** — refresh current state; demote former current (T3.SB3) to Prior #1; archive-split per size-check trigger (Prior count post-this-demote will be 11 — over cap; archive oldest per the established T2.SB5 + T3.SB3 housekeeping precedent).
4. **orchestrator-context-archive.md** — new "Appended 2026-05-2X" section with archived Prior verbatim.
5. **Streaks update** — bank 23rd cumulative C.C lesson #6 validation (if CLEAN); bank ~340+ cumulative ZERO Co-Authored-By streak.
6. **Phase 13 dispatch sequence forward state** — T2.SB6a SHIPPED (substrate); **T2.SB6b NEXT** (6 remaining tasks: review form + queue + metric tile + chart-surface integration + exemplars enhancement + closer). PAUSE-FOR-LIST-ADDITIONS BINDING at T2.SB6b SHIPPED + housekeeping boundary BEFORE T4.SB dispatch.

**Forward action after housekeeping**: orchestrator drafts T2.SB6b dispatch brief covering the 6 deferred tasks. Estimated ~T2.SB5-sized (6 tasks; +80-130 fast tests + 1 fast E2E + 1 cross-bundle pin row 11 un-skip + 1 E2E happy-path). 24th cumulative C.C lesson #6 validation expected at T2.SB6b dispatch.

---

## §9 Forward-binding to T2.SB6b + T4.SB closer

T2.SB6b = the 6 deferred tasks from T2.SB6 original brief — review form + queue + metric tile + chart-surface integration + exemplars enhancement + closer. Branches from main HEAD AFTER T2.SB6a merge. Consumes:
- `swing/web/charts.py` 5 renderer functions (substrate-locked API surface)
- `swing/data/repos/chart_renders.py` cache helpers (substrate-locked API surface)
- `pattern_evaluations` rows (T2.SB3 + T2.SB4 substrate)
- `template_match_nearest_exemplar_ids_json` (T2.SB5 substrate)
- `auto_populated_field_keys_json` (T3.SB3 substrate)

**Forward-binding lessons expected from T2.SB6a to T2.SB6b**:
- Substrate API surface FROZEN post-substrate-Codex (T2.SB6b consumes verbatim; no signature changes).
- Pre-Codex review BOTH scope expansions discipline durable.
- Cross-bundle pin row 11 (`test_repo_caller_tx_contract_invariant`) un-skip at T2.SB6b closer per plan §H.3.
- E2E happy-path test moves from substrate to T2.SB6b closer (substrate's component tests are sufficient; full happy-path requires routes which substrate lacks).

**T4.SB closer** dispatches AFTER T2.SB6b merge + PAUSE-FOR-LIST-ADDITIONS per `project_phase13_t4_sb_pause_for_list_additions` memory.

**NEW forward-binding observation from this partial-completion experience**: brief estimate of 12-18 operator wall-clock hours for a single sub-bundle was the early signal but didn't trigger split-at-dispatch-time. Banked as V2 brief-drafting candidate: "if brief estimate exceeds 8h operator-paced, consider pre-emptive split at dispatch-time rather than reactive split at partial-completion-time". The substrate-vs-downstream natural cleavage was visible in the original T2.SB6 brief §3 file scope (T-A.6.1 + T-A.6.2 are pure-function/data-layer; T-A.6.3-T-A.6.6b are route handlers) — V2 dispatch heuristic could pre-empt this kind of partial completion.

---

*End of dispatch brief. Phase 13 T2.SB6a substrate Codex completion (3 tasks: pre-Codex review + Codex MCP chain + return report extension; expected 2-3 Codex rounds based on T2.SB5 + T3.SB3 precedent). Substrate code FROZEN at HEAD `a9838a7`; Codex fix-bundles only. Inherits T3.SB3 + T2.SB5 forward-binding lessons (pre-Codex BOTH expansions BINDING + bad-exemplar isolation applies to render_theme2_annotated_svg exemplar iteration). **23rd cumulative C.C lesson #6 validation expected with BOTH SCOPE EXPANSIONS BINDING**. T2.SB6b (6 deferred tasks) dispatches AFTER T2.SB6a merge + housekeeping. PAUSE-FOR-LIST-ADDITIONS BINDING at T2.SB6b SHIPPED + housekeeping boundary BEFORE T4.SB dispatch. ZERO Co-Authored-By footer drift streak (~330+ commits at handoff) preserved.*
