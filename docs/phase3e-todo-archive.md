# Cross-Phase Operational Backlog — Archive

> **Purpose:** Historical record of SHIPPED / closed / superseded entries previously in `docs/phase3e-todo.md`. Active backlog is `docs/phase3e-todo.md`.
>
> **Bootstrap discipline:** Fresh orchestrator does NOT need to read this file. Grep on demand for specific historical context (commit hashes, lessons learned, prior dispatches).
>
> **Retention:** Items move here at end of next phase ship (one-phase cooldown). See `docs/orchestrator-context.md` §"Maintenance: retention discipline."
>
> **Archive split trigger:** if this file exceeds ~80k tokens, revisit hierarchical decomposition. Suggested categories at trigger time: SHIPPED-by-phase / lessons-by-domain / decisions-by-quarter — defer category invention until trigger fires (data informs categories better than upfront design).

---

## Phase 3e §Dashboard/UX — 3e.1 + 3e.3 (SHIPPED 2026-04-26 in QoL bundle Session 1)

### 3e.1 — Mark-to-market on Account card — **SHIPPED 2026-04-26** (commit `2b5cded`, QoL bundle Session 1)

**Observed:** The dashboard Account card shows `current_equity` (starting equity +
realized P&L + net cash). This is "settled cash" semantics, not "total account
value including unrealized P&L." On open positions with unrealized gains/losses,
the Account card doesn't reflect that.

**Proposed:** Add an "Unrealized P&L" line item under the Account card showing
`sum((snap.price - entry) * remaining_shares)` over open positions. Keep the
existing equity figure (it's important for position-sizing math), but give the
operator a mark-to-market view alongside.

**Rationale:** Brokerage apps show total account value; absence here is
surprising and easy to misread as "my P&L isn't moving."

**Scope:** ~1 template change + VM field. Phase 2 untouched.

---

### 3e.3 — `POST /prices/refresh` also clears OHLCV breaker — **SHIPPED 2026-04-26** (commit `5b56a2d`, QoL bundle Session 1)

**Observed:** The /prices/refresh button bypasses PriceCache's circuit breaker
but doesn't touch OhlcvCache. If the OHLCV breaker is tripped, the operator
sees the "SMA advisories unavailable" banner with no interactive way to force
a retry.

**Proposed:** Extend the prices-refresh handler to also call
`ohlcv_cache.reset_circuit_breaker()`. OR add a separate `/ohlcv/refresh` button.

**Rationale:** Operator UX parity. Currently the OHLCV breaker only clears on
the 60s cooldown timer.

**Scope:** 1 route change + test. Phase 2 untouched.

---

## Phase 3e §Watchlist UX bugs — all SHIPPED / brainstorm-shipped

### 3e.4 — Watchlist entries can expand but cannot collapse — **SHIPPED 2026-04-26** (commit `2c04aa2`, QoL bundle Session 1)

**Observed:** Clicking a watchlist row expands it to show details. Clicking the
expanded row does nothing — no toggle/collapse. Operator has to refresh the
page to reset the view.

**Proposed:** Make the expand trigger a toggle (click again to collapse), OR
add an explicit collapse affordance (close X in the expanded panel).

**Scope:** 1 template + HTMX swap pattern change. Phase 2 untouched.

---

### 3e.5 — Stale placeholder text in expanded watchlist entries — **SHIPPED 2026-04-26** (commit `d5b076c`, QoL bundle Session 1)

**Observed:** Expanded watchlist entries contain the literal string:

> Log entry (CLI — 3b adds button)

This was a Phase 3a/3b placeholder for a "Log entry" button that would let the
operator annotate a watchlist row. The button was scoped to Phase 3b but never
shipped; the placeholder text was left in.

**Proposed:** Either ship the button (open a modal, insert a note row to
watchlist_notes table, display inline), OR remove the placeholder text.

**Recommendation:** Remove the placeholder for now; revisit the annotation
feature in a later phase when the need is clearer.

**Scope:** Simplest case — 1 template edit. Or 2 route + 1 migration + 1
template if we ship the button.

---

### 3e.6 — No graph pattern shape estimation — **BRAINSTORM SHIPPED 2026-04-26** (spec at `docs/superpowers/specs/2026-04-26-chart-pattern-flag-v1-design.md`, commit chain `9583f19..081f689`); writing-plans dispatch queued. V1 scope = `flag_pattern` only; other patterns deferred to V2+. Implementation chain SHIPPED via chart-pattern flag-v1 Phase 1-7 (see archived per-phase handoff sections below).

**Observed:** The app computes VCP tightness via range-CV and bar-ratio checks,
but doesn't emit a structural classification of the chart pattern (flag,
pennant, flat base, tight channel, cup-with-handle, etc.). The operator has to
chart-read each ticker manually to classify.

**Proposed:** Add a pattern classifier that runs on candidates and outputs a
shape tag. Minimal viable:
- Flat base: ≥ 5 weeks, range ≤ ~15%
- Flag: < 3 weeks, range tight, prior trend steep
- Pennant: similar to flag but converging ranges
- Cup-with-handle: multi-month U-shape + shallow pullback near pivot
- Tight channel: 2+ weeks of converging highs/lows

Render as a flag tag on the watchlist + briefing, same mechanism as `TT✓ VCP✓ A+`.

**Rationale:** Chart-reading is the high-value operator step; surfacing a
suggested pattern reduces cognitive load and provides a falsifiable claim
("model says flag — do I agree?").

**Scope:** Significant. New module under `swing/evaluation/patterns/`, likely 50–100
test cases over real historical examples, new flag_tag dictionary. Phase 2
carve-out probably required.

**Reference pattern images already in repo** (correct paths):
- `reference/images/flag_pattern.png`
- `reference/images/pennant_pattern.png`
- `reference/images/tight_channel_flat_base.png`

---

## Phase 3e Summary table (historical)

| ID | Area | Complexity | Phase 2 carve-out? | Status |
|---|---|---|---|---|
| 3e.1 | Unrealized P&L on Account card | Low | No | **Shipped 2026-04-26** |
| 3e.2 | Partial-exit realized in journal total | Low | No | Open (retained in active backlog) |
| 3e.3 | Prices-refresh clears OHLCV breaker | Low | No | **Shipped 2026-04-26** |
| 3e.4 | Watchlist collapse toggle | Low | No | **Shipped 2026-04-26** |
| 3e.5 | Remove stale "Log entry" placeholder | Trivial | No | **Shipped 2026-04-26** |
| 3e.6 | Chart pattern shape estimation | High | Yes | **Brainstormed 2026-04-26**, V1 SHIPPED via chart-pattern flag-v1 Phase 1-7 |

3e.1, 3e.3, 3e.4, 3e.5 shipped in QoL bundle Session 1 (2026-04-26). 3e.2 remains
the only small open item from the original Phase 3d backlog (retained in active backlog).
3e.6 has a complete spec; chart-pattern flag-v1 V1 fully shipped via the per-phase
handoff chain archived below (Phases 1-7).

---

## 2026-04-25 S&P 1500 study follow-ups

Items surfaced during the S&P 1500 universe expansion study (commits `a921e4b..4a372da`) that were deliberately deferred per scope discipline.

- **Newcombe interval on (S&P 1500 1× rate − SPX+NDX 1× rate).** Tier classification used point-estimate uplift per pre-registration; the per-rate Wilson CIs overlap, so a formal difference-of-proportions inference is open. The Newcombe interval would be the proper instrument. Nice-to-have refinement for tighter inference; not load-bearing for the descriptive Tier 2 finding.
- **Multi-window characterization on S&P 1500.** The Tier 2 result is a single-window observation. Rolling-window characterization (e.g., overlapping 6-month windows) would test rate stability across regimes within the broader 2024-04 → 2026-04 period. Operator-decision gated.
- **5× capital cell on S&P 1500.** Pre-registration scoped the study to 1× only (operator's actual capital). A 5× cell would complete a 4-cell matrix analogous to the candidate-sparsity diagnostic. Deferred per capital-sensitivity disposition (capital is informational, not workflow-changing).
- **Capital-binding-on-mid-caps interpretive finding (informational, not a follow-up task).** Production-gated risk_feasibility on S&P 1500 1× was 9.65% (vs SPX+NDX 18.62%, Russell 6.91%). At the operator's $7,500 capital, mid-cap universes fit the sizing budget BETTER than large-cap universes. Worth surfacing in any future operator-facing universe-decision conversation.
- **Byte-identical re-run with patched diagnostic_run for clean-checkout artifact proof.** D5 patch added `git_dirty` field to manifest for FUTURE runs; THIS D3 run's clean-checkout assertion remains procedural. Adversarial review accepted; orchestrator can request stronger artifact-level proof if needed. Low priority.

---

## 2026-04-25 — Proposed next study (SHIPPED 2026-04-25)

- ~~**Per-criterion binding-constraint analysis on operator's actual Finviz pool.**~~ SHIPPED. See `research/studies/finviz-pool-binding-constraints.md` for findings.

---

## 2026-04-25 Finviz-pool study + hypothesis-label follow-ups

Items surfaced during the Finviz-pool per-criterion analysis (commits `618cb9c..6ca6a40`) and trade hypothesis label Phase 3e change (commits `1cec5df..123f83c`).

### From Finviz-pool study:

- ~~**Watch-staging UI surface for near-A+ defensible candidates.**~~ SUBSUMED 2026-04-25 by hypothesis recommendation engine (commits `b24506b` → `fe270a6`). Near-A+ defensible candidates surface in the dashboard "Hypothesis-driven recommendations" section under the "Near-A+ defensible: extension test" hypothesis. SLDB/UCTT-class tickers automatically appear there when they recur as watch-bucket candidates failing only `proximity_20ma`.
- **Longer-window Finviz-pool re-run after 30-60 days more data accumulates.** Same study module (`research/finviz_pool_analysis/`); just re-execute. The 8-day single-ticker SLDB-population caveat resolves naturally as more daily Finviz CSVs accumulate. Estimated 30 minutes once enough data exists; useful for operator to confirm or revise the descriptive findings.
- **Path-resolution policy for renamed-rejected CSVs.** Implementer flagged: 1 evaluation_run skipped because its CSV was renamed to `data/finviz-inbox/rejected/finviz16Apr2026.rejected-20260419T064456.csv`. Strict literal-basename match was implemented; stem-prefix match could include rejected runs. **Defer indefinitely.** 1 run affected; semantics could go either way; not load-bearing.
- **Single-ticker A+ population caveat.** All 3 A+ rows in the 8-day snapshot were SLDB on 2 dates. Inherent limitation of a small window; resolves with longer-window re-run above. Not a follow-up task; documented limitation.

### From hypothesis-label Phase 3e change:

- ~~**Backfill of historical trades (VIR).**~~ DONE 2026-04-25. After `swing db-migrate` applied schema 7, ran `UPDATE trades SET hypothesis_label = 'sub-A+ VCP-not-formed test (proximity_20ma + tightness fails); inaugural trade test' WHERE id = 1;` against production DB. n=1 historical trade now labeled.
- **Future formalization to controlled vocabulary.** Free-text initially per operator confirmation; once 5+ labeled trades reveal natural categories, formalization to enum + validation is a follow-on. Not urgent.

### Cross-cutting: Post-hoc trade analysis CLI tool

- ~~**`swing trade analyze <trade_id>` retrospective tool.**~~ SHIPPED 2026-04-25 (commits `375344f` cross-contaminated + `2815daa` + `4c2fdbd` → `d5b1753`). VIR verification reproduces manual case-study output exactly. Handles both production-recommended and manually-sourced trades.

### Operational hygiene

- ~~**Weekly DB backups during the first pipeline run of the calendar week.**~~ SHIPPED 2026-04-25 (commits `4a565c6` → `1540489`). WAL-safe via `sqlite3.Connection.backup()` API. Auto-backup verified working in operator's mid-session db-migrate.

### Chart-pattern algorithm framing note (cross-reference)

Per `docs/orchestrator-context.md` 2026-04-25 binding-constraint analysis: chart-pattern algorithm (Phase 3e §3e.6) is for **encoding qualitative chart-pattern input into structured feedback-loop data**, NOT for throughput acceleration (operator can manually assess at saturation rate). Important addition; not urgent. Multi-session copowers cycle when ready. Hypothesis-label free-text absorbs qualitative chart-pattern input as interim solution.

---

## 2026-04-26 chart-pattern flag-v1 Phase 1 → Phase 2 handoff items

Items surfaced by Phase 1 execution (commit chain `dffb723..574869f`, 4 adversarial Codex rounds → `NO_NEW_CRITICAL_MAJOR`) that are deferred to Phase 2 or later phases per scope discipline.

### For Phase 2 (persistence layer) implementer:

- **`components_json` schema design point.** Phase 1's `_evaluate_candidate` returns 11 raw measurements (`pole_M, flag_N, pole_gain, pullback_depth, tightness_ratio, volume_ratio, ma_structure, flag_floor_holds, pole_high, flag_low, pivot`). Spec §3.1.1 lists additional EXAMPLE keys (`pole_gain_clearance`, `pullback_clearance`, `tightness_clearance`, `volume_clearance`, `sma10_at_flag_start`, `sma20_at_flag_start`, `sma50_at_flag_start`) that are NOT currently populated. **Phase 2 design decision:** extend Phase 1's `_evaluate_candidate` to also populate clearances + SMAs (cheap — already computed inside helpers), so `components_json` carries them. **Recommendation: extend** — SMA values become unrecoverable once raw bars aren't persisted alongside, and clearances enable retroactive analysis of why a classification fell where it did.
- **Tightness test naming convention.** `test_tightness_ratio_gate_above/below_threshold_*` are detection-outcome regression tests at search-path-dependent boundaries, NOT direct gate-threshold tests. The actual gate-correctness verification is `test_tightness_ratio_gate_is_threshold_sensitive` (cfg-injection). Phase 2-7 detection-outcome regression tests should follow the same naming pattern.
- **Pure-function discipline verified for Phase 1.** `classify_flag(bars)` does NOT mutate the input DataFrame. Phase 3 can safely reuse the same `bars` object for both `render_chart` and `classify_flag` without copy-on-write concerns.
- **Classifier-error path adapter is Phase 3 territory.** Phase 1 Task 1.13 only verifies the type contract (`pattern: str | None`). The actual exception-catching adapter that constructs `FlagClassificationResult(pattern=None, components={"error": ...})` lives in `_step_charts` per spec §3.3 — Phase 3 implements it. Phase 1 classifier itself does NOT catch.
- **`pre_run_bars=50` in `tests/evaluation/patterns/_synthetic.py`.** Required to satisfy gate 5's 55-bar SMA50 lookback floor. Documented inline. Future fixture refactors must preserve `pre_run_bars + pole_bars >= 55`.

### For Phase 5 (trade-entry form + CLI) — performance budget:

- **Classifier hot loop performance.** `_evaluate_candidate` is invoked ~442× per `classify_flag` call; final reviewer measured ~44-49ms per call on a 250-bar DataFrame, ~700ms for a 15-ticker batch. Spec budgets sub-millisecond with 10× tolerance (10ms target). Single-digit-ms is achievable by hoisting the four `bars[col].to_numpy(dtype=float)` conversions out of the inner loop (they are invariant across all (M, N) candidates). **Phase 5 should measure end-to-end pipeline overhead with the live classifier active across 15 chart-scope tickers and tune if total overhead exceeds 1.5s.** Optimization is straightforward and won't change behavior.

### Spec cleanups landed in this housekeeping commit:

- **Spec §3.1.2 step 4 vestigial sentence removed.** Phase 1 implementer (Q1, 2026-04-26) flagged that "When no candidate passes any gate, the (M=5, N=5) pair's measurements are persisted as a deterministic baseline" was structurally unreachable under MIN_BARS=36 (every candidate has data_window passing, so the no-gate-passes condition is impossible). Removed; precise definition now stands alone. Phase 2 implementer should NOT design persistence around the (5,5) fallback case.
- **(M=5, N=5) literal fallback in `swing/evaluation/patterns/flag_classifier.py`.** Retained but unreachable; documented inline. If Phase 7 ever lowers `MIN_BARS`, this branch activates and would benefit from actual (5,5) measurements being computed and returned (current branch returns only `{"pole_M": 5.0, "flag_N": 5.0}`). Surface for spec follow-up if MIN_BARS is ever lowered.

---

## 2026-04-26 chart-pattern flag-v1 Phase 2 → Phase 3 handoff items

Items surfaced by Phase 2 execution (commit chain `8eca791..158efd2` + retro `3d6e03d`, 2 adversarial Codex rounds → `NO_NEW_CRITICAL_MAJOR`) that are deferred to Phase 3 or are housekeeping items.

### For Phase 3 (pipeline integration) implementer:

- **`_step_charts` wiring is the Phase 3 main work.** Both `classify_flag(ohlcv.tail(60))` and `insert_classification(conn, pipeline_run_id=run.id, ticker=t, result=classification, computed_at=...)` call signatures are stable and tested as of Phase 2. Phase 3 wires them into `_step_charts` per-ticker loop; persists classification row in same `lease.fenced_write()` block as the chart_target update.
- **`_serialize_components` handles NaN sanitization at the persistence boundary** (added in Phase 2 commit `115c96b` as Codex R1 Major 2 fix). Phase 3 can pass any `FlagClassificationResult.components` dict (including those from `_enrich_components` with NaN SMAs) without pre-processing — the repo's `insert_classification` handles it.
- **Per spec §3.3 lines 396-401, classifier-error rows MUST be constructed with `components={"error": repr(exc)}`.** The repo does NOT enforce this contract (Codex R1 Minor 1 ACCEPTED rationale: V1 trust model — _step_charts is sole producer; spec §3.3 prescribes the construction; centralizing as repo-layer enforcement is V2 hardening). **Phase 3's `_step_charts` exception handler is the sole owner of that invariant.**
- **`render_chart` `pattern_overlay` kwarg as no-op for Phase 3.** Per the plan, Phase 3 adds the `pattern_overlay: PatternOverlay | None = None` kwarg to `render_chart` but does NOT paint the overlay yet. The actual painting is Phase 6. Phase 3's render_chart change is API-surface-only.

### For Phase 5 (trade-entry form + CLI):

- **Repo-layer cross-column invariant covers ALL spec §3.2.2 joint-NULL invariants now** (Codex R1 Major 1 closure in commit `115c96b`). Phase 5's `record_entry` inherits this guarantee — any invalid combination of (algo, confidence, operator, anchor) at insert time raises `ValueError`.
- **Trade dataclass's 4 chart_pattern fields default to None.** Phase 5's entry form / record_entry will populate them from the cached classification + operator override; the cross-column invariant rejects invalid combinations at insert time (4 invariants enforced).

### Housekeeping items:

- **`tests/data/test_db_v8.py` filename now stale** (schema is v10 after Phase 2 migrations 0009 + 0010). Final code reviewer flagged as Minor — recommend rename to `test_schema_version_pin.py` in a future housekeeping batch.
- **Several scratch directories from Phase 2 parallel-subagent pytest runs remain in repo root.** `.pytest-tmp/`, `.tmp/`, `.tmp-pytest/`, `.tmp_pytest_red/`, `.tmp_pytest_red_run/`, `ptemp/`, `pytest_temp_red/`, `task28_pytest_green/`, `task28_pytest_green2/`, `task28_pytest_tmp/` (10+ directories). Gitignored at runtime (don't show in `git status`) but pollute the working directory. Cleanup in a housekeeping pass.
- **Phase 2 dispatch brief was lost.** Orchestrator drafted `docs/phase3e-chart-pattern-phase2-execution-brief.md` in the orchestrator-thread and left it untracked, expecting the dispatch chain to commit it (as happened with Phase 1's `9f0a778`). Some operation during Phase 2 execution (likely a subagent's working-tree cleanup) deleted the untracked file; brief is not in working tree, not in git history. Lesson captured in orchestrator-context: **commit briefs immediately after writing them; don't rely on the dispatch chain.**

### Process-meta items:

- **Phase 2 surfaced subagent-collision pattern in `subagent-driven-development`.** See orchestrator-context "Lessons captured" entry on `copowers:executing-plans` self-collision. Phase 3 brief addresses this with explicit disjoint-task-partitioning discipline; worktree isolation is the fallback if collision recurs. **If Phase 3 collides again despite the partitioning discipline, escalate to worktree isolation in Phase 4+.**

---

## 2026-04-26 chart-pattern flag-v1 Phase 3 → Phase 4 handoff items

Items surfaced by Phase 3 execution (commit chain `6ac8f56..dd699de` including `b080da9`+`132142c` rogue/revert pair, 4 adversarial Codex rounds → `NO_NEW_CRITICAL_MAJOR`) that are deferred to Phase 4 or are housekeeping items.

### For Phase 4 (watchlist + dashboard read paths) implementer:

- **Task 4.0a — date deserialization fix (Phase 2 carve-out extension; Phase 4 prerequisite).** Codex Phase 3 R3 Major 1 surfaced that `_row_to_classification` returns ISO date strings instead of `date` objects despite the `PipelinePatternClassification` dataclass annotation being `date | None`. Phase 3 was scope-locked OUT of `swing/data/` so the fix was deferred. Phase 4 brief MUST include Task 4.0a as the first task: `date.fromisoformat(row[N])` for the four anchor columns (`pole_start_date`, `pole_end_date`, `flag_start_date`, `flag_end_date`) in `_row_to_classification` AND the analogous parsing in `list_classifications_for_run`'s row mapping. Without this fix, Phase 4's watchlist VM consumption of `cls.pole_start_date` etc. will be ISO strings at runtime; Phase 6 chart overlay painting will trip on the same. Small fix (~5 lines); justified Phase 2 carve-out extension.
- **`_step_charts` per-ticker fenced_write granularity preserved.** Each ticker outcome is its own `lease.fenced_write()` transaction (~15 small transactions per pipeline run for chart-scope tickers). Phase 3 just bundled the classification INSERT into the same transaction as the chart_target update; existing pattern unchanged. If Phase 4+ ever needs end-of-step batching for performance, the existing fenced_write granularity supports refactoring; Phase 3 didn't change it.
- **End-of-step summary log line `flag_classifier: {success}/{attempts} ok, {errors} errors`** is now the operator-facing visibility surface for classifier health per pipeline run. Phase 4's "dashboard banner for classifier-error count" (V2 deferred per spec §3.3) consumes the same counters; if/when that ships, the banner can pull from this log line OR re-aggregate from `pipeline_pattern_classifications` rows where `pattern IS NULL AND components_json LIKE '%"error":%'`.
- **`PatternOverlay.from_classification(r)` filtering rule.** Returns None when `not r.detected or r.pattern != 'flag'`. The `r.pattern != 'flag'` check covers both `'none'` and None (classifier-error rows). Phase 6 painting won't fire on classifier-error rows — matches spec §3.4 design.
- **Test-suite baseline for Phase 4: 1059 fast tests** passing on main at HEAD `dd699de`. Phase 4 can add tests for `WatchlistVM.pattern_tags` field, `_pattern_tags` helper, watchlist template flag-tag rendering, and the sort-neutrality regression test without disturbing Phase 3's 7 new tests.

### For Phase 6 (chart overlay painting):

- **Byte-identity tests will FAIL when Phase 6 lands.** Phase 3 added `test_render_chart_pattern_overlay_none_is_byte_identical_to_default` and `test_render_chart_real_pattern_overlay_is_byte_identical_to_default` to enforce the no-op contract. These tests are LOAD-BEARING for Phase 3's no-op stub design — when Phase 6 implements actual band-painting + algo-pivot annotation, the byte-identity will break. Phase 6 implementer should expect to update or remove these tests as part of the painting work (replace with overlay-rendered equivalence tests).

### Housekeeping items:

- **`tests/data/test_db_v8.py` filename now stale** (schema is v10 after Phase 2 migrations 0009 + 0010). Recommended rename to `test_schema_version_pin.py`. Carry-over from Phase 2 → Phase 3 handoff; still pending.
- **Scratch directories accumulating in repo root.** Phase 2 left 10+ (`.tmp_pytest_red/`, `task28_pytest_*/`, etc.); Phase 3 added 4 more (`.tmp-pytest-phase3-task32/`, `tmp-pytest-phase3/`, `tmp-pytest-phase3-task32/`, `tmp-task32-probe/`). All blocked by Windows ACL on `Remove-Item`. Aggregate cleanup is a privileged-tool task (`takeown` + `icacls`) — defer until convenient or escalate as a separate operator-action item.
- **Phase 2 dispatch brief recovered.** Earlier housekeeping commit `3912ba9` noted the brief was "lost"; post-Phase-3 verification confirmed the file was on disk the whole time (`ls` returned "No such file" due to transient Windows ACL state). Brief committed to repo in this housekeeping batch. Lesson refined in orchestrator-context: untracked files in working tree are vulnerable to TRANSIENT inaccessibility (ACL state, subagent activity, IDE indexing) — the principle of "commit briefs immediately" stands regardless of the specific failure mode.

### Process-meta items:

- **Phase 3 produced one rogue task duplicate** (`b080da9` + revert `132142c`) despite single-subagent dispatch. Bounded noise (~20% of chain vs Phase 2's ~30%); net code state correct; Codex caught it. Operator decision: continue with brief discipline + ADD observable verification (subagent must include `git log --grep="Task X.Y" --oneline` output in commit body before each task commit) for Phase 4. If Phase 4 sees another rogue, escalate to worktree isolation in Phase 5+.
- **Review-fix commit message convention formalized** in orchestrator-context "Binding conventions" section (2026-04-26). Task implementations get task IDs; review-fix commits use round + finding ID format; format-only cleanup commits no task ID needed.

---

## 2026-04-26 chart-pattern flag-v1 Phase 4 → Phase 5 handoff items

Items surfaced by Phase 4 execution (commit chain `195acbc..ad29f9e`, 3 adversarial Codex rounds → `NO_NEW_CRITICAL_MAJOR`, 13 commits, 1059→1102 fast tests +43, ZERO rogue duplicate task commits) that are deferred to Phase 5 or are housekeeping items.

### For Phase 5 (trade-entry form + CLI) implementer:

- **Task 5.0a — `PipelinePatternClassification` dataclass annotation retype (Phase 2 carve-out extension; Phase 5 prerequisite).** Phase 4 Task 4.0a fixed `_row_to_classification` to parse anchor dates as `date` objects at runtime, but the dataclass annotation in `swing/data/models.py:274` still says `str | None`. Type-vs-runtime drift. Phase 5's `build_entry_form_vm` and Phase 6's chart overlay painting both `isinstance(cls.pole_start_date, date)` checks; the annotation should match runtime. Small fix (~4 line annotations); justified Phase 2 carve-out extension; mirrors Phase 4's Task 4.0a pattern (standalone first commit before Phase 5 main work).
- **`pipeline_run_id` resolution pattern.** Phase 5's `build_entry_form_vm` should mirror Phase 4's single-round-trip `SELECT id, evaluation_run_id FROM pipeline_runs WHERE state='complete' ORDER BY finished_ts DESC LIMIT 1` query (avoids the secondary `WHERE evaluation_run_id = ?` lookup which races with concurrent pipeline_runs writes). The `id` IS the parent `pipeline_run_id` by construction.
- **`_pattern_tags` is SIBLING to `_flag_tags`.** Phase 5's per-row resolution for the entry-form Chart-Pattern section uses `_pattern_tags`-style filtering logic if it needs to gate display, NOT touch `_flag_tags`. The `pattern_tags` parallel VM field design is the architectural pattern.
- **Snapshot-at-entry-surface ToCToU pattern (per spec §3.6 + Phase 1 brainstorm Decision 6).** `EntryRequest` carries the resolved snapshot + `pipeline_run_id` audit anchor; `record_entry` persists what's passed AS-IS (no re-resolve at submit). Cache resolution happens ONCE at entry-surface (form/CLI) per the spec ToCToU fix.
- **CLI cached-only refusal gate.** `swing trade entry --chart-pattern-operator` mirrors form's stub gate — refuses for tickers without cached classification (per locked-constraint #5; per spec §3.6 + Phase 1 Codex R1 C1 fix). Symmetric refusal across entry surfaces.
- **Operator override surface (per spec §3.6).** Dropdown {Accept algo / flag / none / other(text)}; default = Accept algo → NULL persisted. Free-text "other" path canonicalized like `hypothesis_label` (NFC + control-byte stripping; reuse the existing canonicalization helper).
- **Repo-layer cross-column invariant** (4 cases enforced in Phase 2). Phase 5's `record_entry` inherits this guarantee — any invalid combination of (algo, confidence, operator, anchor) at insert time raises `ValueError`.
- **Shared seed helper at `tests/web/test_view_models/_pattern_classification_seed.py`** (leading-underscore opts out of pytest collection). Phase 5/6/7 tests can reuse `seed_pipeline_with_classification`, `add_active_watchlist_row`, `delete_all_classifications` rather than rebuilding seed scaffolding.
- **`build_watchlist_row` reuses run-wide classification fetch** (Phase 4 R1 Minor 1 accepted): single-source threshold + format. Trigger threshold for optimization is watchlist > ~100 rows. Phase 5 trade-entry form's per-ticker fetch may want to use `get_classification(pipeline_run_id, ticker)` directly for lighter rendering, but Phase 4's pattern is fine for current scale.
- **Test-suite baseline for Phase 5: 1102 fast tests** passing on main at HEAD `ad29f9e`. Phase 5 can add tests for `TradeEntryFormVM.chart_pattern_*` fields, `EntryRequest.chart_pattern_*` fields, `record_entry` snapshot persistence, CLI flag refusal gate, and operator-override canonicalization.

### Brief discipline updates for Phase 5:

- **Observable verification refined to subject-only anchored grep** (operator decision 2026-04-26): `git log --pretty='%s' --grep='^[a-z]+\([a-z]+\): Task X.Y'`. Eliminates forward-reference false positives that surfaced in Phase 4 (commit bodies cross-referencing future task IDs in narrative prose). Phase 5 brief adopts this refinement.
- **Don't blanket-require 5-VM rule.** CLAUDE.md base-layout VM gotcha applies only when `base.html.j2` dereferences the field. Phase 5's new `chart_pattern_*` fields on `TradeEntryFormVM` are consumer-scoped (entry form only); `base.html.j2` doesn't reference them. Don't blanket-require all 5 base-layout VMs to gain the field.
- **Downstream-test scope acceptance.** When the brief authorizes Task 5.0a Phase 2 carve-out extension (annotation retype touching `swing/data/models.py`), downstream tests of the modified file are naturally in-scope. Brief should explicitly say "downstream tests of carve-out file are in-scope by extension" to pre-empt scope-deviation findings.

### Housekeeping items:

- **Scratch directories accumulating across phases.** Phase 2 left 10+ (`.tmp_pytest_red/`, `task28_pytest_*/`, etc.); Phase 3 added 4 more (`.tmp-pytest-phase3-task32/`, `tmp-pytest-phase3/`, `tmp-pytest-phase3-task32/`, `tmp-task32-probe/`); Phase 4 cleaned its own (`.tmp-phase4/`) but inherited the prior pile remains. All blocked by Windows ACL on `Remove-Item`. Aggregate cleanup is a privileged-tool task (`takeown` + `icacls`) — defer until convenient or escalate as a separate operator-action item.
- **`tests/data/test_db_v8.py` filename now stale** (schema is v10 after Phase 2 migrations 0009 + 0010). Recommended rename to `test_schema_version_pin.py`. Carry-over from Phase 2/3 handoffs; still pending.

### Process-meta items:

- **Phase 4 vindicated single-subagent + observable-verification approach.** ZERO rogue duplicates this phase (vs Phase 3's one and Phase 2's many). Brief discipline + observable evidence is a working alternative to worktree isolation at this scale. Worktree isolation reserved as fallback for future phases if a new failure mode emerges.
- **Codex's adversarial review pattern across 4 phases:** R1 catches structural issues (Phase 1: cfg-injection sensitivity needed; Phase 2: orphan-confidence guard, NaN strict-JSON; Phase 3: log denominator semantics; Phase 4: compounding-confound conflation), R2 catches subtle vacuousness (Phase 4: ticker-symmetry vacuousness), R3+ refine. The 5-round investment is yielding repeated ROI on test-quality dimension; not just spec-fidelity. Worth continuing.

---

## 2026-04-26 chart-pattern flag-v1 Phase 5 → Phase 6 handoff items

Items surfaced by Phase 5 execution (commit chain `9b7908c..27fb060`, 13 commits incl Task 5.0a + 4 review-fixes + 2 post-report R2-minor follow-ups, 2 adversarial Codex rounds → `NO_NEW_CRITICAL_MAJOR`, 1102→1124 fast tests +22, ZERO rogue duplicate task commits) that are deferred to Phase 6 or are housekeeping items.

### For Phase 6 (chart overlay painting) implementer:

- **Phase 6 lights up the chart-overlay painting (no-op stub from Phase 3).** Phase 3 added `pattern_overlay: PatternOverlay | None = None` kwarg to `render_chart` as a no-op stub; Phase 6 implements actual `fill_betweenx` pole/flag bands + algo-pivot horizontal segment + title annotation per spec §3.4. Existing candidate-pivot hline preserved as a separate visual element (algo-pivot is distinct).
- **Phase 3 byte-identity tests WILL FAIL when Phase 6 lands** (`test_render_chart_pattern_overlay_none_is_byte_identical_to_default` + `test_render_chart_real_pattern_overlay_is_byte_identical_to_default` were load-bearing for Phase 3's no-op contract). Phase 6 implementer should expect to UPDATE or REPLACE these with overlay-rendered equivalence tests (e.g., LineCollection count delta from baseline; pole/flag band fill_betweenx presence; title annotation contains classification label).
- **`PatternOverlay.from_classification(r)` filtering rule already in place** (Phase 3): returns None when `not r.detected or r.pattern != 'flag'`. Covers classifier-error rows (`pattern=NULL`) implicitly. No Phase 6 changes needed there.
- **Phase 5 Task 5.0a aligned the dataclass annotation with Phase 4 runtime fix.** Phase 6 painting can `isinstance(cls.pole_start_date, date)` and use `pd.Timestamp(cls.pole_start_date)` directly without TypeError on `str.isoformat()`.
- **Test-suite baseline for Phase 6: 1124 fast tests** passing on main at HEAD `27fb060`.
- **Spec language fidelity** (per 2026-04-26 lesson on `axvspan` vs `fill_betweenx`): spec explicitly specifies `fill_betweenx` for the band painting. Use the spec's API name verbatim even if alternatives are more familiar.

### Brief discipline updates for Phase 6:

- **Continue subject-only grep observable verification** (Phase 4 + Phase 5 both ZERO rogues with this pattern): `git log --pretty='%s' --grep='^[a-z]+\([a-z]+\): Task X.Y'` in commit body before each task implementation commit.
- **Continue 3-tier commit-message convention** (refined Phase 5): task implementations (`feat(area): Task X.Y — ...`); review-fix commits including internal code-review (`fix(area): code-review I1 — ...`) AND Codex (`fix(area): Codex R1 Major 2 — ...`); format-only cleanup (no task ID).
- **Encourage internal code-review BEFORE Codex round.** Per Phase 5 lesson: pre-empts plan-anticipated misses; saves Codex round budget. Brief should explicitly suggest the internal pass after task implementations land but before invoking Codex.
- **Don't blanket-require base-layout 5-VM rule.** Phase 6 touches `swing/rendering/`; doesn't add VM fields. Not applicable.
- **In-scope-by-extension clause** (per Phase 4 + Phase 5 pattern): Phase 6 implicitly authorizes downstream tests of `render_chart` to be updated/replaced (the byte-identity tests from Phase 3 are the obvious case). Brief should explicitly say "Phase 3's byte-identity tests are expected to fail and need to be replaced with overlay-rendered equivalence tests" to pre-empt scope-deviation findings.

### Housekeeping items:

- **Scratch directories accumulating across phases.** Phase 2 left 10+ (`.tmp_pytest_red/`, `task28_pytest_*/`, etc.); Phase 3 added 4 more (`.tmp-pytest-phase3-task32/`, `tmp-pytest-phase3/`, `tmp-pytest-phase3-task32/`, `tmp-task32-probe/`); Phase 4 cleaned its own (`.tmp-phase4/`); Phase 5 cleaned its own (`.tmp-phase5/`); inherited Phase 2-3 pile remains. All blocked by Windows ACL on `Remove-Item`. Aggregate cleanup is a privileged-tool task (`takeown` + `icacls`) — defer until convenient or escalate as a separate operator-action item.
- **`tests/data/test_db_v8.py` filename now stale** (schema is v10 after Phase 2 migrations 0009 + 0010). Recommended rename to `test_schema_version_pin.py`. Carry-over from Phase 2/3/4 handoffs; still pending.

### Process-meta items:

- **Phase 4 + Phase 5 vindicated single-subagent + observable-verification approach.** ZERO rogue duplicates across both phases (vs Phase 3's one and Phase 2's many). Brief discipline + observable evidence + subject-only grep refinement is a working alternative to worktree isolation at this scale. Worktree isolation reserved as fallback for novel failure modes.
- **Codex's 5-phase review pattern shows compound ROI:** R1 catches structural issues; R2 catches subtle vacuousness; R3+ refine; Phase 5 added a NEW class — cross-feature interactions (R1 M2 soft-warn × new chart_pattern fields) that internal review naturally misses. The 5-round investment yields repeated ROI on test-quality + spec-fidelity + cross-feature-integration dimensions.
- **R2 minors closed post-report.** Phase 5 R2 minors (schema-message coupling docs; soft-warn × "other" test) were ACCEPTED with rationale in implementer's return report; commits `4ef9044` + `27fb060` landed post-report addressing them. Net: nothing deferred; Phase 5 → Phase 6 handoff doesn't carry R2-minor advisory follow-ups.

---

## 2026-04-26 chart-pattern flag-v1 Phase 6 → Phase 7 handoff items

Items surfaced by Phase 6 execution (commit chain `bce79b1..13d8cc5` + mathtext follow-up `2fd0ecc`, 7+1 commits, 4 adversarial Codex rounds → `NO_NEW_CRITICAL_MAJOR`, 1124→1127 fast tests +3, ZERO rogue duplicate task commits) plus Q1 + Q2 operator decisions.

### For Phase 7 (operator-labeled fixtures + integration tests + tuning) implementer:

**Phase 7 implementer-side scope is small.** Tasks 7.1 (fixture directory + labeling protocol README) + 7.2 (fixture-loader + parametrized integration test) + 7.4 checkpoint (gated on operator-labeling + tuning). Task 7.3 (≥15 fixtures labeled by operator) is OPERATOR-ONLY work running in parallel with implementer's 7.1/7.2 ship.

- **Phase 7 brief should ship 7.1 + 7.2 immediately.** Task 7.3 operator-labeling can run at any pace alongside; Task 7.4 closes after operator labeling + FP-biased tuning.
- **Chart overlay painting works on in-window portions of any classification's date range.** Phase 6 documented and tested LEFT-truncation (date before chart window snaps to index 0) and RIGHT-truncation (date after last bar — zero-width band at right edge) as intentional. No new edge cases expected from Phase 7 fixture parametrization.
- **Test-suite baseline for Phase 7: 1127 fast tests** passing on main at HEAD `2fd0ecc` (post-mathtext-fix).
- **Two-pivot rendering preserved** per spec §3.4. Operator-labeling work in Task 7.3 will see both candidate-pivot (full-width hline) AND algo-pivot (flag-region segment); they may coincide or differ. Spec deliberately allows visual comparison.
- **Mathtext quirk fixed** (commit `2fd0ecc`). Chart titles now render legibly without mathtext italicization.
- **Manual verification procedure prepared** at `docs/chart-pattern-flag-v1-manual-verification.md`. Operator walks through web + CLI surfaces post Phase 7 implementer ship to confirm everything displays correctly. Procedure will likely surface follow-up items.

### Brief discipline updates for Phase 7:

- **Continue subject-only grep observable verification** (3-phase ZERO-rogue track record: Phases 4 + 5 + 6).
- **Continue 3-tier (now 4-tier with `(internal)` qualifier) commit-message convention.** Internal-Codex commits append `(internal)` qualifier per Q2 decision (2026-04-26 post-Phase-6 triage); orchestrator-Codex commits stay as-is.
- **Encourage internal review BEFORE Codex** at BOTH discipline levels: manual code-review (per Phase 5 lesson) AND internal-Codex round (per Phase 6 lesson). Each layer pre-empts orchestrator round budget.
- **Subagent role-partitioning within a task is collision-safe.** Phase 6 dispatched 7 subagents at different roles within Task 6.1 (implementer / reviewer / fix-implementer) with ZERO rogues. The disjoint-task-partitioning discipline operates at the TASK level, not subagent-count level.
- **Manual visual verification is required for rendering changes.** If Phase 7 fixture parametrization touches chart rendering (e.g., overlay edge cases per the LEFT/RIGHT truncation), manual PNG inspection must accompany structural test verification.

### Housekeeping items:

- **Scratch directories accumulating across phases.** Phase 2: 10+; Phase 3: 4 more; Phase 4: cleaned own; Phase 5: cleaned own; Phase 6: created `.tmp-phase6-*` and similar (ACL-blocked). All blocked by Windows ACL on `Remove-Item`. Aggregate cleanup is a privileged-tool task (`takeown` + `icacls`) — defer until convenient or escalate as a separate operator-action item.
- **`tests/data/test_db_v8.py` filename now stale** (schema is v10). Recommended rename to `test_schema_version_pin.py`. Carry-over from Phase 2-5 handoffs; still pending.

### Process-meta items:

- **Phase 4 + Phase 5 + Phase 6 all produced ZERO rogue duplicate task commits.** Single-subagent + observable verification + subject-only grep refinement is robust at this project's scale. Worktree isolation reserved as fallback for novel failure modes only.
- **Codex's 6-phase review pattern shows compound ROI:** R1 catches structural issues; R2 catches subtle vacuousness; R3+ refine + escalate coupling concerns into explicit contracts; Phase 5 added cross-feature interactions (soft-warn × new fields); Phase 6 added internal-Codex pre-emption. The 5-round investment yields repeated ROI on test-quality + spec-fidelity + cross-feature-integration + visual-correctness + contract-documentation dimensions.
- **Phase 6 commit-message convention surfaced 4th case:** internal-Codex within-task vs orchestrator-Codex post-task. `(internal)` qualifier formalized in Binding conventions for Phase 7+.

---

## 2026-04-27 chart-pattern flag-v1 Phase 7 implementer-side → operator + orchestrator handoff

Phase 7 implementer-side complete (commit chain `528d38b..ca66216`, 11 commits, 5 adversarial Codex rounds → `NO_NEW_CRITICAL_MAJOR`, 1127→1145 fast tests +18 plus +1 gracefully-skipped integration test, 8 subagent dispatches with ZERO rogue duplicate task commits). Operator-labeling boundary preserved end-to-end.

### For OPERATOR — manual verification + Task 7.3 fixture labeling:

**Step 1: Manual verification walkthrough.** Run `docs/chart-pattern-flag-v1-manual-verification.md` end-to-end (~30-45 min thorough; ~10-15 min spot-check). Surfaces any UI bugs in chart-pattern surfaces (dashboard, /watchlist, chart overlay, trade-entry form, CLI) before fixture labeling work begins. Any check failures → surface to orchestrator before proceeding.

**Step 2: Task 7.3 fixture labeling (operator pace).** Per spec §4.2 + Phase 7 implementer's labeling protocol README at `tests/evaluation/patterns/fixtures/README.md`:
- ≥15 fixtures floor = 8 flags + 7 non-flags spanning rejection cases (wide-and-loose, deep base/cup, sideways drift with no pole, late-stage failed breakout, stage-4 with bounce, multi-month flat base, ambiguous edge case).
- File format: paired `<TICKER>_<YYYY-MM-DD>_<label>.csv` (literal yfinance pull) + `.json` (label + notes + optional expected_confidence_min).
- Loader canonicalization: yfinance pull is preserved on disk; helper trims to last 60 bars before classification. Operator's visual labeling should focus on the right edge of the chart.
- JSON schema validation gates (per Codex R1 M2 + R2 M2): label ∈ {flag, none}; notes is required (no silent default); expected_confidence_min must be numeric in [0,1] AND only set on flag fixtures (not none).
- Fixtures immutable: never edit-in-place; retire-and-replace if a label changes.
- Generation procedure example in README §6: `python -c "import yfinance as yf; df = yf.Ticker('TICKER').history(end='YYYY-MM-DD', period='90d'); df.to_csv('tests/evaluation/patterns/fixtures/TICKER_YYYY-MM-DD_flag.csv')"` (or use period='120d' if a holiday-heavy month yields <60 trading days).
- MIN_BARS in classifier is 36; spec's 60-bar contract is more conservative. period='90d' is sufficient for typical months.

**Step 3: Each fixture commit:** `test(patterns): add labeled flag fixture <TICKER>_<DATE>` (or `none` variant). Standard convention; not a "task implementation" so no task-ID prefix needed.

### For ORCHESTRATOR — Task 7.4 checkpoint (gated on operator labeling):

**When Task 7.3 fixtures ship (≥15 committed):**

1. Run `python -m pytest tests/evaluation/patterns/test_flag_classifier_integration.py -v` to execute parametrized integration tests over committed fixtures.
2. Each parametrized test reports `<fixture-name> PASSED/FAILED`; failed assertions include label + actual pattern + notes in the error message.
3. **Operator manually classifies failures as FP (algo says flag, operator labeled none) or FN (algo says none, operator labeled flag).** Per Q2 (2026-04-27): no automated FP/FN aggregator was added in V1; operator does manual classification from pytest output. Acceptable for V1 personal-use scope; if operator needs aggregation tooling, add as a small standalone follow-up.
4. **Tune `cfg.classifier.*` if FP > FN per spec §3.1.4.** FP-biased: prefer false-negatives (algo missing real flags) over false-positives (algo flagging non-flags) — operator's eye is the validating ground truth, so over-flagging wastes operator-review time. Tighten thresholds (raise `flag_pole_gain_min`, lower `flag_pullback_depth_max`, etc.) until FP ≤ FN at default thresholds OR operator accepts the current calibration.
5. **Phase 7 checkpoint criteria:** ≥15 fixtures committed; integration tests run; FP/FN classified; tuning applied (if needed) OR baseline accepted; final test-suite run green.
6. **V1 ship criteria:** Task 7.4 closure marks chart-pattern flag-v1 V1 fully shipped. Document outcome in orchestrator-context "Recent decisions and framings" + lessons captured.

### V1 known limitations (deferred to V2+):

- Manual-trade fallback for out-of-chart-scope tickers (locked-constraint #5; spec §3.6).
- ML / LLM / hybrid classifiers (operator preference: rule-based geometric for V1).
- Multi-timeframe analysis (weekly + daily); currently daily-only.
- Real-time / intraday classification.
- Sort-PARTICIPATING flag tag (sort-neutral in V1 by spec).
- Calibration study (algo vs operator agreement-rate); gated on 20+ overrides.
- Slow-test live-fetch suite (deferred per spec §4.3).
- Tuning-history versioning.
- Schema-layer cross-column constraint hardening on `trades` (CREATE-COPY-DROP-RENAME).
- Hidden form-field tampering hardening (re-resolve at submit + validate).
- Dashboard banner for classifier-error count.
- Additional patterns beyond `flag_pattern` (V1 = single pattern; V2+ extensions via separate dispatch).
- `(M=5, N=5)` literal fallback in classifier (unreachable under MIN_BARS=36; documented inline).
- Automated FP/FN aggregator for Task 7.4 tuning (Q2, 2026-04-27).

### Process-meta items (post-V1):

- **4-phase ZERO-rogue track record (Phases 4 + 5 + 6 + 7).** Single-subagent dispatch + observable verification + 4-tier commit-message convention is the working baseline at this project's scale. Worktree isolation NOT escalated.
- **Codex's 7-phase review pattern shows compound ROI:** R1 catches structural; R2 catches second-order interactions; R3+ catches defense-in-depth; Phase 7 added induced-bug pattern (R3→R4 chain). The 5-round investment yields repeated ROI on test-quality + spec-fidelity + cross-feature-integration + visual-correctness + contract-documentation + induced-bug-detection dimensions.
- **Subject-only grep regex amended to ERE + POSIX** (Q1, 2026-04-27). Past briefs' BRE-incompatible regex was technically non-functional; the discipline still worked because of other partitioning rules. Phase 7+ briefs use the ERE form.

---

## 2026-04-27 chart-pattern flag-v1 manual verification round 1 — findings

Full technical detail in `docs/chart-pattern-flag-v1-manual-verification-results.md`. Summary of action items by tier:

### Tier 1 — V1-quality fix (dispatch BEFORE Task 7.3 fixture labeling)

1. **Mathtext title regression** — commit `2fd0ecc` `\$` escape doesn't prevent matplotlib mathtext entry; rendered title shows `pivot 72.97stop40.69` with "stop" italicized. Fix options: (a) remove `$` from title format, (b) `fig.suptitle(..., parse_math=False)` after `mpf.plot(returnfig=True)`. Recommended: (a) for simplicity. Files: `swing/rendering/charts.py:86`, `tests/rendering/test_chart_overlay.py:270` and `:287`. **Manual visual verification required** before committing — do NOT rely on string-equality tests alone (the lesson from this regression). **SHIPPED** as Tier-1 mathtext fix dispatch (commit `29c93f5`).

### Tier 2 — Operator-workflow improvements (post-V1)

2. **No standalone chart-image route.** ~~Add route in `swing/web/routes/` to serve PNGs from `exports/<session>/charts/`.~~ **SHIPPED 2026-04-27** (chart-access UX dispatch, commit `772d69b`). Date-less `/charts/{ticker}.png` route; 303 redirect to existing date-prefixed StaticFiles URL or chart_scope-aware 404 with operator-facing reason.
3. **Open positions rows don't expand to chart.** ~~UX gap during trade management.~~ **SHIPPED 2026-04-27** (chart-access UX dispatch, commit `f0d13e8`). HTMX click-to-expand on dashboard open-positions rows, mirroring watchlist expand pattern. Chart inline if ticker in chart-scope; "Chart unavailable" message with chart_scope reason otherwise. **Note:** clicking dashboard's "Refresh now" button collapses any expanded rows back to compact form — expected HTMX OOB-swap behavior (the swap replaces the table HTML so transient client-side expansion state resets). Click-to-expand binding survives, but expanded VISUAL state does not. Operator confirmed this is fine.
4. **Chart-scope set misaligned with Phase 4 watchlist sort.** ~~Empirically confirmed during verification: dashboard top-5 watchlist (Phase 4 tag-aware composite sort) only overlaps chart-scope set on 1 of 5 tickers (DHC). Operator-design discussion required before implementation.~~ **SHIPPED 2026-04-28** (chart-scope policy v2 dispatch chain `c4820d0..527e334`, 15 commits). Three-tier policy `aplus > open_position > tag_aware_top_n` with N=10 watchlist top-N (default raised 5 → 10). Cross-surface drift race closed via `PipelineRunBinding` pinned at request-handler entry. Schema migration 0011 extends `pipeline_chart_targets.source` CHECK. Stop-hline omission active for None/0 stops. Wall-time monitoring active (60s WARN / 120s ERROR). Spec at `docs/superpowers/specs/2026-04-27-chart-scope-policy-v2-design.md`; plan at `docs/superpowers/plans/2026-04-27-chart-scope-policy-v2-plan.md`.

### Tier 3 — Operator-design questions (retained in active backlog as operator-paced deferred items; cross-referenced from `docs/orchestrator-context.md` §"Operator-paced items")

5. **Lightning icon trigger logic re-evaluation.** Current rule: `price >= 0.99 × entry_target`. Operator surfaced concern that simple "near pivot" indicator may not be the right "actionability" signal post-Phase-4 (with richer tag tier + pattern classification + hypothesis-recommendation engine). Options enumerated in verification-results doc.
6. **Multiple concurrent advisories vs single price-stop field.** Open positions can show multiple trail-stop advisories (e.g., 10MA + 20MA based) but trade row supports only one stop value. Reconciliation needed: state-machine when stop adjusted to satisfy one but not all advisories. Phase 3d follow-up. _Operator framing recorded 2026-04-27 (verification-results doc §#6): maximum-communication principle — annotate, don't suppress; trade-maturity gating concept (default 20MA early, upgrade to 10MA after ~+1.5-2R)._

### Tier 4 — Verification doc fixes — **SHIPPED 2026-04-27** (this commit)

7-14. Verification doc had SQL queries assuming `sqlite3` CLI on PATH, conflated "error" column SQL, PowerShell-incompatible Python multi-line syntax, missing "conditional on open positions" note for §1.1.a, account-card field-list overstated vs actual UI, §3 chart-image instructions assumed ticker stays in watchlist post-trade, §5.x CLI commands had wrong option names + missing required options (`--entry`/`--entry-price`, `--stop`/`--initial-stop`, missing `--entry-date` + `--shares`, `--rationale` is `click.Choice`), and chart's purple dotted "consolidation marker" lacked operator-facing legend. **All resolved in the Tier-4 doc-fix bundle commit alongside post-mathtext-fix follow-ups (below).** Full details in `docs/chart-pattern-flag-v1-manual-verification-results.md`.

### Verification deferred (re-run when conditions enable)

- §3.2 chart overlay flag-painting — needs flag classifications. Currently zero. Retest post Tier 2 #4 (chart-scope alignment) AND/OR when market produces flag patterns.
- §3.4 classifier-error chart — needs error rows. Currently zero.
- §4.3-4.5 override variants — exercise at next 2-3 trade entries via web form.
- §4.7 soft-warn × chart_pattern — needs 4+ open trades.
- §5.1 + §5.3 CLI variants — exercise at next CLI trade entry.
- §6 full cross-surface consistency — needs `pattern='flag'` ticker.

---

## 2026-04-27 chart-pattern flag-v1 mathtext fix follow-ups

Items surfaced from the Tier-1 mathtext title regression fix dispatch (commit `29c93f5`, single-task implementer dispatch with 2-round Codex review → `NO_NEW_CRITICAL_MAJOR`).

### Mathtext-hardening on the suptitle path (R1 Major; ACCEPTED out-of-scope; defer)

The Tier-1 fix dropped `$` from the chart title format string. Adversarial Codex R1 raised a defense-in-depth concern: the production path passes `title=` to `mpf.plot(...)`, which routes through `fig.suptitle` with default `parse_math=True`. If a future ticker symbol ever contains a mathtext metacharacter (`$`, `^`, `_`, unbalanced `\`), it would re-enter math mode despite the current title format being `$`-free.

Threat-model assessment: real-world US equity tickers use `[A-Z\.\-]` only; none of those characters trigger matplotlib's mathtext interpreter. Numeric formatters (`{:.2f}`) emit only digits + `.`. The current fix is sufficient for the ticker character set the framework actually consumes.

Possible future hardening if the threat model widens:

- **(a)** Switch `mpf.plot(returnfig=True)` and call `fig.suptitle(title, parse_math=False)` explicitly after — disables math-mode parsing on the suptitle entirely. Defense-in-depth at the rendering boundary.
- **(b)** `_sanitize_for_mathtext()` helper that escapes/strips `$ ^ _ \` from the ticker substring at title-construction time. Defense-in-depth at the format-string boundary.

Cheap insurance; not urgent. Pick up if the codebase ever ingests non-US tickers, derivative symbols, or any source that could put metacharacters into the ticker field.

### Mathtext metacharacter gotcha (informational; captured in CLAUDE.md gotchas)

Matplotlib mathtext fires on `$` (paired math mode), `^` (superscript), `_` (subscript), and unbalanced `\`. Future title-format additions (scientific notation, exponents, footnote markers, custom annotations) will need visual re-verification on rendered PNG, NOT just string-equality assertions. Captured in CLAUDE.md gotchas in this same housekeeping commit.

---

## 2026-04-28 chart-scope policy v2 follow-ups

Items surfaced from the chart-scope policy v2 cycle (spec `c52835f` 4-round Codex + plan `d1dc4e4` 5-round Codex + executing-plans chain `c4820d0..527e334` 2-round Codex; 15 commits total). Tier-2 #4 fully shipped; these are forward-looking deferrals or accepted-with-rationale items captured for future dispatches.

### From spec (V1-deferred items, all explicitly out-of-scope):

- **Slow-marked benchmark test for chart-step wall time.** Deterministic log-capture mechanism shipped in Task 7; real-timing benchmark deferred to `-m slow` suite or dedicated benchmark CI. Spec §A "Test instrumentation."
- **`pipeline_runs.charts_wall_time_ms` persisted column** for queryable wall-time history (currently log-only). Would require migration 0012 + write-path threading + consumer audit. Defer until operator builds external monitoring or alerting layer. Spec §A "Future V2 hardening."
- **Tier-based shedding** when wall time projected > soft budget mid-step. Skip remaining `tag_aware_top_n` tickers; add `chart_status='skipped_for_budget'` enum value. Spec §A "Future hardening." Adds complexity; only worth it if wall-time overruns become operationally common.
- **Filter-intersection alignment** between `_sort_watchlist` (web) and `_step_charts` (pipeline). Watchlist rows missing `entry_target` or `last_close` are visible on dashboard but excluded from chart-scope. Future dispatch could align filters bidirectionally. Spec §A "Residual filter-intersection limitation." Small but real coverage gap.
- **Cross-request session pinning** for inter-request races. Currently bindings pin per-request only; user clicking different rows over time may see different `data_asof_date` values across same session. Closing requires server-side cross-request session state. Spec §C "What the binding does NOT close."
- **Future surfaces composing multiple `resolve_chart_scope` calls in one handler** must add explicit shared-binding tests when they emerge. Spec §C "Technical guardrail deferral." YAGNI for V1; convert to test pin when first multi-call surface ships.

### From executing-plans dispatch (R1/R2 ACCEPTED-with-rationale):

- **Tag-aware sort `flag_tags` lookup canonicalization beyond dedup boundary** (executing-plans R1 Minor 1). `.upper()` discipline applied at dedup boundary in `_step_charts`; the flag_tags lookup keyed by raw `c.ticker` / `entry.ticker` (no `.upper()`) is acceptable in V1 because production data is consistently upper-case per spec. Defense-in-depth tightening (extend `.upper()` to all ticker references) deferred until/unless mixed-case watchlist/candidate data appears.
- **Rendered-surface (route or HTMX template) test for `out-of-scope-legacy` reason code** (executing-plans R2 Minor 2). Currently pinned only at resolver/unit-test level. Future dispatch could add a TestClient-level test asserting the rendered "Chart unavailable" surface displays the `out-of-scope-legacy` reason text. Additional test coverage; not a regression.

### Plan-implementation completed (was tracked as deferred; now resolved):

- ~~**Reviewer-checklist hardening for binding contract enforcement.**~~ INCORPORATED into plan Task 10 Step 3 (writing-plans phase R4 Minor 2 fix). Shipped as part of executing-plans Task 10 phase checkpoint.

### Future deferrals: Chart-scope policy v3 — retained in active backlog as small standalone entry.

### Hyp-recs trade-prep expansion (SHIPPED 2026-04-29 at `a29a592`)

Operator surfaced the workflow gap during CC-pivot-mismatch bug triage (2026-04-28): hyp-rec rows are evaluated row-by-row against chart pattern + buy-window proximity before pulling the trigger; current dashboard surface lacks at-a-glance trade-preparation snapshot. Proposal: HTMX click-to-expand on hyp-rec rows showing the full trade-prep view, mirroring the watchlist/open-positions expand pattern but with trade-prep semantics.

Q1 disposition (2026-04-28): pure-trigger discipline conditional on price being inside the buy window — formal version of "wait for pivot, don't chase >1% above" entry-discipline (2026-04-25). The expansion makes "in-window?" check at-a-glance rather than ad-hoc.

**Brainstorm dispatch pattern:** implementer-dispatched (operator preference + brainstorm-pattern threshold met — multiple medium-complexity decisions, cross-surface scope, likely spec ≥500 lines).

#### Locked decisions (operator, 2026-04-28; brainstorm uses these as framing input):

1. **Chase factor.** 1% per recorded discipline for V1, but MUST be configurable — not hard-coded. Implementation hooks into the future configuration-page work (separate todo below); for V1 the 1% lives in a config field with a sensible default. Toml-shadowing audit applies (per `aeb2084` lesson) — if a tracked toml override exists at ship time, must update in the same commit OR explicitly accept as operator opt-in.
2. **Chart in expansion when ticker is out-of-chart-scope.** "Chart unavailable" message reusing the chart-access UX pattern — same behavior as current `/charts/<TICKER>.png` handler when ticker not in chart-scope. NO chart-scope policy change for this dispatch. Operator will give explicit direction if/when chart-scope rules need adjustment.
3. **Cost-display semantics.** Show two cost numbers: risk-based (using $7,500 floor sizing) AND cash-feasible (capped at actual balance). **Cash-feasible cap uses CURRENT ACCOUNT BALANCE ONLY**, NOT total liquidity (balance + open positions). May add a risk display for both ends in V2; V1 ships shares + total cost for the two cases.
4. **Lightning icon.** Keep as-is for now. Do NOT hide or strip in this dispatch. Operator may repurpose later (Tier-3 #5 stays open as a separate conversation); the explicit reason is so the icon remains visible as a reminder for that future decision rather than evaporating.
5. **Cross-surface scope.** Hyp-recs ONLY in this dispatch. Watchlist + open-positions snapshot extensions deferred. (Watchlist's existing expand stays chart-only; open-positions' existing expand stays chart-only.)
6. **CC pivot bug bundled into this dispatch (Option C).** Watchlist `Pivot` column header currently renders `WatchlistEntry.entry_target` (frozen at add time) under a header that says "Pivot." Fix renders `candidates.pivot` (current eval-run pivot) instead — matches what hyp-recs already does. Cross-surface consistency on what "Pivot" means becomes part of this dispatch's done-criteria. Investigation already complete (survey result captured in this conversation; see CC-pivot-mismatch findings below).

#### Snapshot fields to design:

The expansion content should include (V1 scope):

- **Buy stop** = `candidates.pivot` (already in hyp-rec VM)
- **Buy limit** = pivot × (1 + chase_factor); default 1%, configurable
- **Sell stop** = framework-computed initial stop (verify field — likely `stop_loss` on candidate row OR computed via existing sizing pipeline)
- **# shares (risk-based)** = risk-based position size from `compute_shares` (uses max($7,500 floor, balance) per project memory)
- **# shares (cash-feasible)** = same calc capped at floor(account_balance / pivot) — based on CURRENT BALANCE ONLY, not balance + open positions
- **Total cost (risk-based)** = risk-based-shares × pivot
- **Total cost (cash-feasible)** = cash-feasible-shares × pivot
- **Chart** = inline if ticker in chart-scope; "Chart unavailable" with reason if not (current chart-access UX behavior, no policy change)

#### CC pivot mismatch bug (bundled — investigation already complete):

- **Symptom:** Watchlist row for ticker CC shows "$24.13" under "Pivot" column header; hyp-recs table shows "$26.98" for same ticker. Same price ($25.70 stale in both), divergent pivot.
- **Root cause:** Watchlist row partial at `swing/web/templates/partials/watchlist_row.html.j2:16` renders `w.entry_target` (frozen at add time, immutable) under a column header at `swing/web/templates/partials/watchlist_top5_section.html.j2:4` that says "Pivot." `WatchlistEntry.last_pivot` field exists in the model but is never rendered. Hyp-recs correctly renders `candidates.pivot` from the latest eval run.
- **NOT mixed-anchor:** Both surfaces bind to the same evaluation_run via `latest_evaluation_run_id`. The 2026-04-25 mixed-anchor closure was anchor-focused and missed cross-surface field-rendering audit.
- **Fix as part of this dispatch (Option C):** watchlist row partial renders current pivot from candidates dict (joined by ticker, same as hyp-recs does) under "Pivot" header. Header label stays "Pivot," semantics align across both surfaces.
- **Lightning icon (per Q4):** trigger logic stays bound to `entry_target` unchanged. Fix scope is column-display only (`watchlist_row.html.j2:16`); lightning trigger at `watchlist_row.html.j2:7` is NOT touched. Behavioral consequence: CC's lightning continues firing post-fix (price $25.70 ≥ 0.99 × $24.13 entry_target). **Semantic side-effect operator should be aware of:** column header "Pivot" will render `candidates.pivot` ($26.98) while lightning math uses the unshown `entry_target` ($24.13), so a row may show "lightning fires" without the displayed pivot supporting the math. This is the deliberate cost of preserving lightning behavior (Q4) independently of column-display semantics (Q6). Tier-3 #5 (lightning re-evaluation) remains the venue for revisiting trigger field; this dispatch does NOT touch it.

#### New lesson (capture in housekeeping when this dispatch ships):

**Anchor closure surveys must also audit template field rendering, not just query anchors.** The 2026-04-25 mixed-anchor closure verified `MAX(run_ts) FROM evaluation_runs` was gone from the web layer, but did not audit which fields were rendered in templates under shared column names. Same anchor with different rendered fields still produces operator-visible cross-surface divergence (CC pivot mismatch is the canonical example). For future cross-surface consistency reviews: anchor parity AND field-rendering parity are independent audit dimensions.

#### Cross-references:

- Tier-3 #5 lightning re-evaluation (`docs/phase3e-todo.md` 2026-04-27 manual-verification findings) — stays separate per operator; expansion redesign supersedes some of its scope but operator wants the lightning visible for now.
- Configuration-page future feature (separate todo below).
- Sub-A+ VCP-not-formed hypothesis trade discipline (orchestrator-context 2026-04-25 "Entry discipline for hypothesis trades: wait for pivot").
- Capital-risk-floor convention (project memory `project_capital_risk_floor.md`) — sizing uses max($7,500, balance); cash-feasibility uses balance only.

---

## 2026-04-28 configuration page for operator-tunable settings — **SHIPPED 2026-05-02 at `3a4195c`**

Operator surfaced 2026-04-28: as small operator-tunable settings accumulate (chase_factor, chart_top_n_watch, risk_pct floor, account balance cap rules, etc.), each currently lives as a Python default + tracked toml override in `swing.config.toml`. Future feature: dashboard configuration page where operator can view + edit these values without manual toml-editing.

**Locked decisions** (operator + orchestrator 2026-05-01): see `docs/phase5-configuration-page-writing-plans-brief.md` §2 — separate user-config file at `%USERPROFILE%/swing-data/user-config.toml`; precedence default → tracked toml → user-config → page-write; per-request read; dedicated `/config` page; CLI parity (`swing config show|set|reset`); 3 V1 fields.

**V1 field set (3 fields; canonical paths from plan §A consumer audit, NOT the speculative paths in the brief):**

- `cfg.web.chase_factor` (default `0.01`; consumed at 2 sites — hyp-recs trade-prep expansion view-model). NOT top-level as the brief originally speculated.
- `cfg.pipeline.chart_top_n_watch` (default `10`; consumed at 7 sites). NOT under `web.` as the brief originally speculated.
- `cfg.account.risk_equity_floor` (default `7500.0`; **already** present in tracked `swing.config.toml:22`; consumed at 3 production sites — `swing/pipeline/runner.py:424`, `:558`, `swing/web/view_models/dashboard.py:496`). Brief's "currently a code constant" assertion was WRONG; Task 0a became a no-op.

**Toml-shadowing audit (binding):** any field surfaced via the config page MUST honor the toml-shadowing lesson (`aeb2084`, 2026-04-28). Read order resolved 2026-05-01: Python default → tracked `swing.config.toml` → user-config.toml → page-write (which writes user-config.toml). User-config strictly overrides tracked-toml per-field. Pre-flight `grep -rn "<field_name>" .` audit on every field surfaced (canonicalized into plan §C).

**Future field additions:** small per-field follow-ups — V1 infrastructure ships ready for them. Candidates surveyed but explicitly NOT V1: `risk_pct`, `pipeline_lease_wait_seconds`, `current_balance`, advisory thresholds (10MA / 20MA / etc.), other `cfg.web.*` settings.

**Executing-plans first attempt** (commit chain `dff70ca..2278e97`, 2026-05-01): landed Tasks 1.0/1.1/1.2/2.0 plan-aligned (`dff70ca`, `db1bf0f`, `0b85046`, `e42f5be`); fifth commit `2278e97` was a rogue Task 1.2 rewrite (overwrote landed plan-aligned `swing/config_overrides.py` with a non-plan API; absorbed Task 2.1 wiring under wrong subject; created non-plan test file with `Path.cwd()` mkdtemp pattern yielding 66 ACL-locked `.config-overrides-*` dirs at repo root). Diagnosed as extended-time-window subagent self-collision within `subagent-driven-development` (NOT external interference; 9:47 min between duplicate Task 1.2 commits with intervening Task 2.0 commit). Reverted via `git reset --hard e42f5be` + `git push --force-with-lease origin main`.

**Executing-plans re-dispatch (2026-05-02):** worktree-isolated on `phase5-config-page-redispatch` branch with global PreToolUse Codex-blocking hook + marker-file workflow. 7 commits onto branch (`f86eafd..4d3174d`); 2 Codex rounds → NO_NEW_CRITICAL_MAJOR; operator-witnessed 6-step browser gate PASS. Merged via `git merge --no-ff` at `3a4195c` (4 docs commits ahead of base prevented fast-forward). 1381 → 1472 fast tests (+91, exceeds the +75 plan estimate). Browser-gate workaround: PowerShell prefix `$env:PYTHONPATH = "."; python -m swing.cli web` to overcome editable-install-vs-worktree path mismatch.

**V1 follow-ups (out-of-scope discoveries from re-dispatch return report; OPEN):**

- **CSS gap on new config-page surfaces.** `.banner.warn`, `.banner.error`, `.btn`, `.btn-secondary` classes referenced in `swing/web/templates/config.html.j2` + `partials/config_hard_refuse.html.j2` + `partials/config_soft_warn_confirm.html.j2` may not be defined in `swing/web/static/app.css`. Page is functional; banners may render as plain text instead of styled. Cosmetic polish ticket.
- **`ConfigPageVM.session_date` inconsistency.** Uses `date.today().isoformat()` instead of `action_session_for_run(datetime.now())` like other base-layout VMs. Cosmetic — affects topbar date display only on weekends/holidays/HST. Fix would touch landed Task 4.0 file (Watch item #12 prohibited within-dispatch); now post-merge it's safe to fix.
- **Route-layer integration smoke gap.** Task 2.1 override-applied test exercises the VM helper directly (not via TestClient round-trip). The 26 route-wiring sites are grep-verifiable; future task could add a TestClient-based smoke that POSTs/GETs one of the patched routes after writing user-config to assert the rendered response reflects the override. Not blocking V1 ship.
- **Schema-valid wrong-type user-config crashes `_get`.** R1 Minor 1 advisory. V2 hardening: add `isinstance(section_obj, dict)` guard. Surfaces as visible 500 (not silent corruption); operator hand-edit error scope only.
- **Lost-update race across two browser tabs** (R1 Major 3 ACCEPTED). Single-operator scope per CLAUDE.md + brief §3.2; two-tab race operationally implausible. V2 may add file locking if multi-user surface ever emerges.

**Cleanup deferred (operational housekeeping; bundled):** 66 ACL-locked `.config-overrides-*` dirs + `.codex-pytest-6681924b-*` dir + `.tmp` + `.tmp_pytest` + `pytest-run-*` dir + `.worktrees/phase5-config-page-redispatch/` (worktree branch + git registration removed; directory removal blocked by file handles when tested 2026-05-02). All owned by `AughtSevernIII\CodexSandboxOffline` per the dry-run output. `cleanup-locked-scratch-dirs.ps1` allowlist extended 2026-05-02 to recognize the new patterns; needs operator-elevated PowerShell to execute.

**Cross-references:**
- Brief (writing-plans): `docs/phase5-configuration-page-writing-plans-brief.md` (commit `3fde496`).
- Plan: `docs/superpowers/plans/2026-05-01-configuration-page-plan.md` (HEAD `e8c6396`; ~75 new tests planned; 5 Codex rounds → NO_NEW_CRITICAL_MAJOR).
- Brief (executing-plans, REVISED): `docs/phase5-configuration-page-executing-plans-brief.md` (`671451f`; worktree isolation + Task 2.1+ starting point).
- toml-shadowing lesson in `docs/orchestrator-context.md` Lessons captured (post-`aeb2084`).
- Subagent self-collision lessons in `docs/orchestrator-context.md` Lessons captured (chart-pattern Phase 2 tight-window 2026-04-26; Phase 5 extended-window 2026-05-01).
- `project_capital_risk_floor.md` memory.

---

## 2026-04-28 OHLCV archive consolidation — **SHIPPED 2026-04-30 at `3335d6c`** (Phase 3 of 6-phase operator sequence; 696 tickers consolidated; migration ran cleanly)

Operator surfaced 2026-04-28 during research-resource discussion: "are we archiving any of the yfinance data we are pulling down? One way to improve throughput would be to start creating a local history which could be queried for all historical data, only using yfinance to pull down the most recent OHLCV numbers." Survey of current code found three caching paths with inconsistent semantics:

### Current state (orchestrator survey 2026-04-28):

1. **`swing/prices.py PriceFetcher` → `~/swing-data/prices-cache/`.** On-disk parquet cache. Used by pipeline runner, CLI commands, weather runner. **53 MB, 5,521 files.** Keying is wasteful: `{ticker}_{lookback_days}d_asof-{YYYY-MM-DD}.parquet` produces a new file per as_of_date even when 99% of the data overlaps. AAPL alone has separate parquets for 8+ as-of-dates over 2 weeks; same 120-day window re-stored each session. ~200-300 unique tickers represented across 5,521 redundant snapshots.
2. **`swing/pipeline/ohlcv.py` (chart-step OHLCV).** Used by `_step_charts` to feed chart rendering AND chart-pattern flag-v1 classifier. **No disk cache.** Fresh `yf.Ticker.history(...)` pull every pipeline run for chart-scope tickers (open positions + tag-aware top-N + A+ ≈ 5-15 tickers/run, all re-pulled).
3. **`swing/web/ohlcv_cache.py OhlcvCache`.** TTL-cached in-memory (3600s default), sliding-window circuit breaker. Used for dashboard SMA advisories on open positions. **Restart-flushed.** Not persisted.
4. **`~/swing-data/research-cache/ohlcv/`** (research branch). **92 MB across 2,603 ticker files.** One file per ticker (NOT per as_of_date) — the proper incremental-archive pattern. Used by research-branch harness; production paths don't consume it.

### The architectural gap:

Production paths (#1 + #2) re-fetch from yfinance every run for data that's already on disk in the research cache (#4). The proper incremental-archive pattern exists in the codebase — just not used by production. Migration to per-ticker incremental cache cuts per-run yfinance call volume by ~99% for established tickers.

### V1 scope (this dispatch):

1. **Consolidate `prices-cache/` keying.** Switch `PriceFetcher` from per-as-of-date parquet files to per-ticker parquets with date-range tracking. New file format: `{TICKER}.parquet` with `as_of_max` metadata or column. One-time migration script consolidates the 5,521 redundant files into ~200-300 per-ticker files.
2. **Add disk archive to `_step_charts` chart-fetch path.** Wrap `swing/pipeline/ohlcv.py`'s `yf.Ticker(t).history(...)` in a per-ticker incremental-fetch helper. On each call: read latest stored bar for ticker; pull yfinance for `latest+1` → today; append. New tickers get full history pull.
3. **(Optional V1) Back `OhlcvCache` with the disk archive for warm-restart.** Currently the in-memory TTL flushes on every web restart. Backing it with the same disk archive eliminates the cold-start fetch storm after restart.

### Open design questions for brainstorm/spec:

- **Corporate-action retroactive adjustment policy.** yfinance retroactively adjusts splits/dividends. A "permanent archive" with stale adjustments diverges from current yfinance over time. Mitigation options:
  - (a) **Periodic full-refresh on active tickers** (e.g., weekly cron OR on first-pull-of-session detection). Simple; small wasted bandwidth.
  - (b) **Store both raw + adjustment-factor columns separately**; recompute adjustments on access from the latest known split/dividend ratios. More complex; closer to a real time-series database.
  - (c) **Accept staleness on tickers without recent corporate actions; explicit refresh on operator-flagged tickers.** Pragmatic; requires corporate-action detection or operator-driven invalidation.
  - Default-recommendation for V1: (a) — simplest, wastes ~10-20% bandwidth on weekly full-refresh of active tickers, but tolerates the asymmetry.
- **Cache-coherence policy.** Need explicit rule for "trust archive" vs "re-fetch fresh." Probably keyed on (ticker, last_corporate_action_check_date) with explicit TTL on the corporate-action check.
- **Migration strategy for 5,521 redundant files.** One-time consolidation script; runs once, then archived/deleted. Preserve any uniquely-historic data (oldest as_of_date per ticker) before consolidation.
- **Schema location.** Is the archive a per-ticker parquet (current research-cache pattern), or a single SQLite table with composite key (ticker, date)? Parquet is faster for long history scans; SQLite integrates with existing infrastructure. Both fit; design choice.

### V1-deferred / V2:

- 1-min intraday bars (would multiply storage by ~390× — ~37 GB for full universe; out of V1 scope; framework is daily-cycle).
- Cross-platform sync (Drive-synced archive would require careful WAL-mode handling per the SQLite-DB-location invariant). Out of V1 scope.
- Automatic universe expansion (auto-archiving tickers operator hasn't asked about). V1 archives only what production paths request; demand-driven not pre-emptive.

### Storage budget (concrete):

| Universe | Tickers | 5-year history | Notes |
|---|---|---|---|
| Operator's Finviz pool only | ~500 | ~18 MB | Demand-driven minimum |
| SPX + NDX + S&P 1500 | ~1,500-2,000 | ~70-100 MB | Reasonable target |
| Full Russell 3000 | ~3,000 | ~110 MB | Comprehensive |
| 10-year Russell 3000 | ~3,000 | ~220 MB | Decadal coverage |

Storage is essentially free at all scales relevant to this project. Real value is yfinance rate-limit relief + pipeline speed + research-branch parity + diagnostic capability for any-time-window analysis.

### Cross-references:
- yfinance rate-limit + threading gotcha in CLAUDE.md gotchas.
- `swing/prices.py:24` `PriceFetcher` (Phase 2 carve-out territory).
- `swing/pipeline/ohlcv.py` (no current cache).
- `swing/web/ohlcv_cache.py` (in-memory TTL).
- `~/swing-data/research-cache/ohlcv/` existing pattern (use as architectural reference).

---

## 2026-04-28 sector/industry capture + display — **SHIPPED 2026-04-29 at `09ad4bd`** (Phase 1 of 6-phase operator sequence; production-verified)

Operator-recall surfaced 2026-04-28: "At some point several days ago there was a discussion about capturing which industry the tickers fall under and displaying/capturing that as a data point which might be useful for making a trade determination." Orchestrator survey confirmed: data is INGESTED but DROPPED on the production path. Never persisted, displayed, or used in decision logic.

### Current state (orchestrator survey 2026-04-28):

- **Ingested.** Finviz CSV schema validator at `swing/pipeline/finviz_schema.py:12` requires both `Sector` and `Industry` columns. CSV is rejected to `data/finviz-inbox/rejected/` if either column is missing.
- **Not persisted.** Zero hits for `sector`/`industry` columns anywhere in `swing/data/` (11 migrations + repo files + dataclass models surveyed). The fields are read from the CSV and discarded.
- **Not displayed.** No template, VM, or route consumes sector/industry data.
- **Not used in decision logic.** Only mention in production code outside the Finviz schema is a comment in `swing/trades/stop_adjust.py:31` about the "news" rationale enum value.
- **But the framework PRESUMES sector analysis happens.** orchestrator-context.md lines 156–157 explicitly include sector in operator's manual decision process: "Operator validates the recommendation (chart pattern, risk, **sector preference**)..." — operator currently has to look up sector externally per ticker because the framework drops the data.

### V1 scope (this dispatch):

Mirrors the `hypothesis_label` and `chart_pattern_*` patterns already shipped (snapshot-at-entry-surface frozen-at-entry):

1. **Schema migration 0012** — add `sector TEXT NOT NULL DEFAULT ''` and `industry TEXT NOT NULL DEFAULT ''` columns to `candidates` table (refreshed each pipeline run from Finviz CSV). Add same columns to `trades` table (frozen at entry, mirrors `hypothesis_label`).
2. **Pipeline ingestion** — `_step_evaluate` writes Sector/Industry from each Finviz CSV row into the candidate row. Already-validated by schema; just needs to flow to persistence.
3. **VM + template surface** — display sector/industry on the surfaces where operator decision happens:
   - Hyp-recs row expansion (NEW; coordinates with hyp-recs trade-prep expansion dispatch — see "Sequencing question" below).
   - Watchlist row expansion.
   - Trade entry form (read-only field showing the snapshot value to be persisted).
   - Open positions row (informational; operator can confirm what they bought).
4. **Trade entry capture** — frozen-at-entry like `hypothesis_label`. Captured via the snapshot-at-entry-surface ToCToU pattern (spec §3.6 / Phase 5). `EntryRequest` carries `sector` + `industry`; `record_entry` persists what's passed AS-IS.

### Open design questions for brainstorm/spec:

1. **Granularity.** Finviz provides Sector (~11 broad: Technology, Healthcare, Financial Services, Energy, etc.) AND Industry (~150 narrow: Software-Infrastructure, Biotechnology, Banks-Regional, Oil-Gas-E&P, etc.). Show both? Show only sector? Show industry but group by sector? Recommendation: persist both, display both — sector for grouping/concentration, industry for context. Cheap to defer the granularity decision to display-time.
2. **Display surfaces.** Hyp-recs row expansion is obvious. Watchlist row expansion likewise. Trade entry form likely. Open positions row? Journal review? Each surface is a small-incremental cost. Suggested V1 scope: 4 surfaces (hyp-recs expansion, watchlist expansion, trade entry, open positions). Defer journal review aggregation to V2.
3. **Snapshot vs always-current.** Sector/industry are very stable for a ticker (rarely change — corporate restructuring is the main driver). Both approaches work:
   - **Frozen-at-entry** (matches `hypothesis_label` / `chart_pattern_*` patterns; consistent with framework's pre-registration discipline).
   - **Always-current** (read from latest candidate row at display time; no persistence on `trades`).
   - Recommendation: frozen-at-entry per the existing pattern. If sector data drifts post-entry due to ticker reclassification, that's information worth preserving (the operator entered when this ticker was Tech; it's now Industrials — the analysis should know that).
4. **Sector source-of-truth.** Finviz only. yfinance has its own sector taxonomy that differs from Finviz. Don't reconcile across sources in V1 — Finviz is the single authoritative source for the framework's sector view.

### V2 follow-up (gated on V1 shipping):

- **Sector concentration warning surface.** Once sector is captured on `trades`, dashboard could surface "you have 3 open positions in Technology, max-sector-concentration N% of risk" warnings. Prevents over-concentration in a single sector. Configurable cap (e.g., max 50% of total open risk in a single sector). Separate dispatch; ungated on V1 shipping.
- **Industry-level concentration** (probably NOT useful for a $7,500 account at 5 concurrent positions; sector-level is the right granularity at this scale).
- **Sector-level analytics on `swing trade analyze`.** Group historical trades by sector; per-sector expectancy, win rate, R-multiple. Useful for identifying operator's per-sector edge (or anti-edge). Separate dispatch.

### Sequencing question:

Sector/industry display surfaces include **hyp-recs row expansion** — which is the central artifact of the just-queued hyp-recs trade-prep expansion brainstorm (`docs/phase3e-todo.md` 2026-04-28 hyp-recs trade-prep expansion section). Two ways to sequence:

- **(A) Fold sector/industry into the hyp-recs expansion brainstorm** — the snapshot expansion already designs a multi-line context display for hyp-rec rows; sector/industry fits naturally as additional context fields. Avoids a second dispatch on overlapping surface. Sector-capture migration becomes a prerequisite (Task 0a) of the hyp-recs expansion plan.
- **(B) Ship sector/industry capture FIRST as a small standalone migration** — schema 0012 + pipeline ingestion + minimal display (4 surfaces, all read-only). Then hyp-recs expansion brainstorm starts with sector data already captured and queryable.

Recommendation: **(B)**. Sector capture is a tighter, more bounded scope (just data flow + display); hyp-recs expansion can consume the captured field without scope creep on its brainstorm. Keeps the brainstorm focused on its own design questions (chase factor, cost-display semantics, etc.) without adding sector-granularity questions.

### Cross-references:
- `swing/pipeline/finviz_schema.py:12` (validator requires both columns; data flows in this far and stops).
- orchestrator-context.md lines 156-157 (framework-presumes-sector-analysis already in decision-making).
- `hypothesis_label` and `chart_pattern_*` patterns (snapshot-at-entry-surface frozen-at-entry; existing repo precedent).
- 2026-04-28 hyp-recs trade-prep expansion section above (sequencing-question dependency).

---

## 2026-05-01 Journal v1.2 incorporation — Phase 6 SHIPPED 2026-05-04 at `51c79ed`

> Cross-cutting framing for journal v1.2 incorporation (Phases 6-9), plus Phase 8/9 prospective scope, retained in active backlog. This entry captures the SHIPPED Phase 6 detail.

### Phase 6 — Post-trade review surface — **SHIPPED 2026-05-04 at `51c79ed`**

**Bundle:** Mistake_Tags + Process Grade A-F + `mistake_cost_R` / `lucky_violation_R` + `lesson_learned` + Review_Log cadence skeleton.

**Why first:** Highest-value piece; ships independently of state-machine work; closes a real gap (operator memory + ad-hoc review today is the only behavioral discipline measurement). Cheap and additive — touches the post-close path only, no schema disruption to open-trade flow.

**Scope:**
- New schema migration: `mistake_tags TEXT` (JSON-list) + `process_grade TEXT (A/B/C/D/F)` + `entry_grade` + `management_grade` + `exit_grade` + `disqualifying_process_violation BOOLEAN` + `mistake_cost_R REAL` + `lucky_violation_R REAL` + `mistake_cost_confidence TEXT (high/medium/low)` + `lesson_learned TEXT` + `reviewed_at DATETIME` on `trades`. All nullable until reviewed.
- New `Review_Log` entity: `review_id, review_type (daily/weekly/monthly/quarterly), period_start, period_end, scheduled_date, completed_date, skipped, duration_minutes, n_trades_reviewed, total_mistake_cost_R, total_lucky_violation_R, primary_lesson, next_period_focus`. Cadence compliance dashboard surface.
- Mistake_Tags taxonomy from v1.2 §7.10: 5 categories (entry / risk / management / psychology / reconciliation) + `none_observed`. Adopted nearly as-is; this is sound classification work the operator shouldn't re-derive.
- Process Grade computation per v1.2 §9.2: weighted (entry 0.40 / management 0.35 / exit 0.25) with disqualifying floor (any-stage-F → F; disqualifying_process_violation → max D).
- `swing trade review <trade_id>` CLI command + web `/trades/<id>/review` form. Required at close + within 7 days (configurable).

**Estimated dispatches:** 2 (one for the schema + repo + CLI; one for the web form + dashboard surface). Brainstorm-skip viable; copowers:writing-plans direct.

**Actually shipped as:** single executing-plans dispatch on worktree branch `phase6-post-trade-review` (not split). 24 commits (16 task-impl + 1 code-review I2 + 4 R1 Codex fixes + 1 R2 Codex minor + 1 mid-verification I3 fix). 2 Codex rounds → NO_NEW_CRITICAL_MAJOR. Operator-witnessed 6-surface browser gate PASS. Test count 1472 → 1587 (+115 vs plan's +30-45 estimate; ~3x due to Codex compound-ROI on discriminating-test-discipline). Ruff 98 → 80 (incidental cleanup). 0 rogue commits — first all-clean executing-plans dispatch since Phase 4.

**V1 follow-ups (out-of-scope discoveries from executing-plans return + operator-witnessed verification gate; OPEN):**

- **Cadence card lacks clickable "Complete review" link.** Operator-witnessed gate finding 2026-05-04. Cadence cards at `swing/web/templates/partials/cadence_cards.html.j2` render period + scheduled/completed status but have NO link to the completion form. Operator navigated via direct URL (`/reviews/{review_id}/complete`) for verification. Cosmetic UX gap; non-blocking. Fix: add `<a href="/reviews/{{ card.review_id }}/complete">Complete review</a>` when `card.is_pending`.
- **Completion route 404s for already-completed Review_Logs (no read-only view).** Operator-witnessed gate finding 2026-05-04. `GET /reviews/{id}/complete` at `swing/web/routes/trades.py:1126` explicitly checks completion state and returns 404 with `"Review #N not found or already completed"`. Operator could not revisit completed Review_Log via UI to verify frozen aggregates (verification done via direct DB query instead). Fix options: (a) modify the existing GET handler to render read-only view for completed rows, OR (b) add new `GET /reviews/{id}` route for read-only display.
- **`ReviewsPendingVM.window_days` field stale after Codex R1 Major 1 fix.** Codex R2 Minor 3 ACCEPTED-with-rationale 2026-05-04. R1 Major 1 fix changed `/reviews/pending` list view from "overdue only" to "ALL closed unreviewed" semantic; the `window_days` field is no longer rendered on the page but still carried on the VM. Future cleanup: drop the field OR re-purpose for "highlight trades older than the badge threshold" UI surface.
- **Migration head-version test consolidation needed.** Phase 6 Task 1 code-review finding 2026-05-04 (pre-existing structural debt amplified by every schema bump). `tests/data/test_migration_0010_trade_chart_pattern.py` has hard-coded `assert version == 13` inside a migration-0010-specific test; same inline assertion exists in other migration-specific tests. Each schema bump requires retroactive updates across multiple test files (Phase 6 had to update 3). Fix: extract head-version assertions into a single `tests/data/test_expected_schema_version_is_current` test and drop the in-line versions from migration-specific tests.
- **Soft-warn dismiss-link uses raw onclick.** Phase 6 review_soft_warn_close partial uses `onclick="..."` for the dismiss action (existing project pattern; not Phase 6's introduction). Flag for future HTMX-everywhere migration when the project's JS posture solidifies.
- **HX-Redirect target route must be verified to exist (test pattern strengthening).** Operator-witnessed gate found Phase 6 review POST emitted `HX-Redirect: /trades` but no `GET /trades` route was registered (fixed inline as code-review I3 to `/reviews/pending`). Future tests for HX-Redirect-emitting handlers should either (a) assert target route is registered in app's route table (e.g., `assert any(r.path == target for r in app.routes)`), OR (b) follow the redirect with a second TestClient call and assert 200. Add to writing-plans phase as checklist item for any HX-Redirect-emitting handler.

**Process-meta items captured (out-of-scope for Phase 6 V1 follow-up; informational):**

- **Copowers session state file convention doesn't share across worktrees of the same repo.** Implementer return-report observation 2026-05-04. Convention uses `sha256(repo_root_path)[:12]` for the session-state filename at `/tmp/.copowers-session-<hash>.json`; worktree paths produce different hashes than main paths, so each worktree gets its own session state file. Could be improved with `git rev-parse --git-common-dir` for shared state across worktrees of the same repo. Upstream improvement note for the copowers plugin; not Phase 6 work.
- **Subagent monthly usage limits forced 2 completions to orchestrator-session fallback.** Implementer return-report observation 2026-05-04. Two subagent dispatches hit "monthly usage limit" mid-task (one during ruff cleanup, one during Codex R1 fixes); implementer completed those workflows directly from the orchestrator session with the same end-state. Resource-awareness flag for org-budget if dispatching again soon.

**Cross-references:**
- `reference/Future Work/Trading Journal/swing_trading_journal_ai_ingestion_v1.2.md` §7.10 (Mistake_Tags), §7.11 (Review_Log), §9.2 (Process Grade), §8.8 (Mistake Cost / Lucky Violation), §10.4 (Post-Trade Review workflow).
- Existing primitive precursor: `swing trade analyze <trade_id>` (Phase 3e 2026-04-25) — manual case-study output. Phase 6 upgrades this to structured + persisted.
- Existing audit-log: `trade_events` — keep distinct from Review_Log (events are state changes; reviews are aggregations).
- Writing-plans brief: `docs/phase6-post-trade-review-writing-plans-brief.md` (`441e22a`).
- Plan: `docs/superpowers/plans/2026-05-02-phase6-post-trade-review-plan.md` (commit chain `1be4622..e976d64`; 5 Codex rounds → NO_NEW_CRITICAL_MAJOR).
- Executing-plans brief: `docs/phase6-post-trade-review-executing-plans-brief.md` (`a7c4bda`).
- Ad-hoc DB cleanups: 2026-05-04 SPY test entries removed (`swing-pre-spy-cleanup-20260504T022932.db`); see orchestrator-context.md.

---

## 2026-05-01 Journal v1.2 incorporation — Phase 7 SHIPPED 2026-05-05 at `c617777`

### Phase 7 — Trade lifecycle state machine + Fills first-class (SHIPPED to main 2026-05-05 at `c617777`)

**Phase 7 SHIPPED** to main 2026-05-05 at integration merge `c617777` (single `git merge --no-ff phase7-sub-c-web` brought all 3 sub-dispatches' work in: Sub-A 14 + Sub-B 15 + Sub-C 24 + 2 hotfixes = 56 commits; pushed to origin same day). Production DB at v14 with 4 trades (VIR/DHC/CC/YOU FIRM-backfill values) + 5 fills + 11 trade_events; GPRE test trade cleaned post-gate. Operator-witnessed verification gate: 11/11 surfaces PASS post-hotfix. Worktrees + branches cleaned 2026-05-05 via cleanup-script extension (4-step takeown+icacls/reset+icacls/grant+Remove-Item; resolved Phase 6 leftover too).

**Two hotfixes landed at Sub-C integration layer** (operator-authorized chained-branch posture exception per hard-conflict escape — Sub-A territory mods authorized for these specific cases):

1. **`283d4fa` migration-runner FK CASCADE fix.** Sub-A migration 0014 step 10's `DROP TABLE trades` triggered ON DELETE CASCADE on `fills.trade_id` + `trade_events.trade_id` under production's `foreign_keys=ON`, wiping 5 fills + 11 trade_events during the table-rebuild. Sub-A T9 + T10 tests passed under sqlite3's default `foreign_keys=OFF` so the divergence wasn't caught. Hotfix patched `swing/data/db.py:_apply_migration` to toggle foreign_keys=OFF for the duration (per SQLite docs §11.2). 2 discriminating regression tests added; verified discriminating by stash + run pre-fix (test fails with `fill_count == 0`); post-fix passes. Lessons captured to orchestrator-context.

2. **`5e9981c` operator-gate hotfix bundle.** (a) Entry duplicate trade_events: `record_entry` called both `insert_trade_with_event` AND `insert_fill_with_event`; both auto-emitted `'entry'` audit row; result was 2 duplicate trade_events per entry. Fix: added `emit_event=False` parameter to `insert_fill_with_event`; record_entry suppresses the second emission. (b) Review state transition `closed → reviewed` missing: web review POST at `swing/web/routes/trades.py:1370` called `update_trade_review_fields` directly, bypassing the `complete_trade_review` service that wraps the state_transition. Sub-B return report explicitly flagged this as Sub-C T1 territory; implementation didn't switch. Hotfix routes through complete_trade_review. 2 discriminating regression tests added; both verified discriminating. Lessons captured.

**Findings deferred as backlog** (cosmetic; not blocking; Phase 7 ships without these):
- State badge per-state colors not differentiated (Sub-C C.5 CSS gap; only text labels render). Backlog.
- "Needs review" badge predicate uses Phase 6's `reviewed_at IS NULL` rather than Phase 7 brainstorm spec's `state == 'closed'` (plan §2.1 didn't enumerate this badge predicate for rewrite; UX-correct outcome). Backlog.

**Phase 8 + 9 unblocked** — operator decides timing.

**Sub-A SHIPPED status** (historical, pre-merge): Sub-A SHIPPED 2026-05-04 on worktree branch `phase7-sub-a-schema` (HEAD `78c7005`).

**Sub-C SHIPPED** 2026-05-05 on chained worktree `phase7-sub-c-web` (HEAD `b867f00`; baseline `71ddb95`; 24 commits = 17 task-anchored + 7 fix/test polish; 3 Codex rounds → NO_NEW_CRITICAL_MAJOR; suite 1605→1873 passed [+268 net; ~112 truly new + 156 transitioned from RED/errored/skipped → GREEN]; ZERO failed + ZERO errored + 1 skipped (operator-task-gated); ruff baseline 79→78). Final shim deletion at C.14 (Exit class + list_all_exits + list_exits_for_trade + insert_exit_with_event + _ExitLikeRow). Extended scope per operator COA B included web extended consumers + 5 out-of-Phase-7 module migrations (review_log, pipeline, recommendations/hypothesis, equity, review) + CLI list migration + journal aggregation migration + 4 test-fixture migration commits (C.13a-d). One C.3 plan deviation surfaced transparently: kept existing OOB-swap success-path pattern (200 + dashboard chunks) instead of plan sketch's "204 + HX-Redirect" — preserved operator UX + ~20 existing tests; lesson captured. Production bug surfaced + fixed during C.13: soft-warn confirm fragment was missing 18 Phase 7 pre-trade fields (commit `eebb0e6`).

**Operator-witnessed browser verification gate PENDING (FINAL binding step before merge).** 11 surfaces enumerated in executing-plans brief §6 (entry form 7 fieldsets / HTMX submit + HX-Request propagation / success-path / exit form / stop-adjust / review form / state badges 5 colors / dashboard state-aware filtering / dashboard "needs review" badge / cadence cards / no-regressions). Operator runs `swing web` against worktree using `$env:PYTHONPATH = "."; python -m swing.cli web` per editable-install convention; reports PASS/FAIL per surface.

**After gate PASS: integration merge protocol.**
```bash
cd c:/Users/rwsmy/swing-trading
git checkout main
git pull
git merge --no-ff phase7-sub-c-web -m "Merge phase7-sub-c-web into main: Phase 7 (Sub-A + Sub-B + Sub-C integrated)"
git push
```
Single merge brings all 53 commits in (Sub-A 14 + Sub-B 15 + Sub-C 24). Production DB triggers 0014 migration on first post-merge `swing` invocation; backup-runner discipline auto-fires (Sub-A T1 wired the 4 integrity checks); 4 production trades (VIR/DHC/CC/YOU) backfilled per Sub-A T10 FIRM values.

**Worktree cleanup (operator-paced post-merge):**
```bash
git worktree remove .worktrees/phase7-sub-c-web
git worktree remove .worktrees/phase7-sub-b-services
git worktree remove .worktrees/phase7-sub-a-schema
git branch -d phase7-sub-c-web phase7-sub-b-services phase7-sub-a-schema
```
If `.tmp/pytest-of-rwsmy/` ACL-locks block removal: trigger-gated entry below at "2026-05-04 Worktree cleanup script: pytest-of-rwsmy ACL-lock pattern recurrence check" applies — 3 worktree-cleanup data points from Phase 7 inform whether cleanup-script extension is warranted.

---

#### Sub-A SHIPPED status (historical)

**Sub-A SHIPPED** 2026-05-04 on worktree branch `phase7-sub-a-schema` (HEAD `78c7005`; baseline `eba1625`; 14 commits = 11 task + 2 code-review fix + 1 Codex fix; 2 Codex rounds → NO_NEW_CRITICAL_MAJOR). Migration 0014 verified working on production-shape fixture (VIR/DHC/CC/YOU FIRM values reproduced exactly); 4 preservation invariant fixtures green; backup-runner discipline operationalized with 4 integrity checks + rollback-on-partial-failure. Test delta: +102 new tests (vs ~+87 plan estimate) but 217 failed + 20 errors remain across Sub-B/Sub-C territory (web view models, journal predicate rewrites, exit/stop_adjust/review services, CLI predicate rewrites — see binding-green-gate-vs-carve-out conflict below). Ruff baseline preserved at 80.

**Chained-branch posture decision** (operator 2026-05-04): Sub-A's binding green gate at T6 was structurally impossible given plan §3 carve-out assigning predicate rewrites to Sub-B/Sub-C. Implementer surfaced the conflict; operator chose option (a) — Sub-A NOT merged to main; Sub-B + Sub-C dispatch from chained worktree branches based on Sub-A; integration `git merge --no-ff phase7-sub-c-web` to main only after Sub-C ships full suite green. **Production DB stays at v13 throughout** (no migration triggered until merge); operator's trade workflows (DHC/CC/YOU stop-adjusts, exits, reviews) continue working unaffected. Lesson captured in orchestrator-context lessons-captured 2026-05-04.

**Sub-B SHIPPED** 2026-05-04 on chained worktree branch `phase7-sub-b-services` (HEAD `71ddb95`; baseline `78c7005`; 15 commits = 9 task + 6 Codex fix; 6 Codex rounds → NO_NEW_CRITICAL_MAJOR; suite 1450→1605 passed [+155]; 217→130 failed [Sub-B territory closed]; 20→6 errors; ruff baseline 79 [-1 from 80]; zero web modifications; one authorized Sub-A territory exception — 8-line docstring at `swing/data/repos/trades.py:insert_trade_with_event` per R2 Minor 1 deferral). 6-round Codex chain was convergence (datetime canonicalization touched 5 service entry points), NOT thrash — lesson captured.

**Shim removal status (Sub-B partial; full deletion deferred to Sub-C scope decision):**
- Exit service consumption: DELETED in B.4 (`swing/trades/exit.py` no longer imports Exit/insert_exit_with_event/list_exits_for_trade).
- `tos_import.py` exits-table reads: MIGRATED to fills repo in B.9.
- Other shim consumers: ~18 files PRESERVED (web extended + review_log + pipeline + recommendations/hypothesis + journal aggregation + cli list + trades/equity + 3 test fixtures). Full shim deletion blocked on these consumer migrations — see Sub-C scope decision below.

**Sub-C scope decision (operator-paced)** — implementer's open question 2026-05-04: shim full-deletion requires migrating ~18 out-of-original-Sub-C-scope consumer files. Options:
- (A) Sub-C nominal scope (web only per plan §3); shims remain alive permanently or via future cleanup dispatch.
- (B) Sub-C extended scope: web migration + shim cleanup sweep + shim deletion in single dispatch (~12-14 tasks; ~4-7 Codex rounds; clean Phase 7 endgame).
- (C) Sub-C nominal scope ships first; separate Sub-D dispatch handles shim cleanup sweep + deletion.
Operator decision required before drafting Sub-C brief.

**Sub-C pre-conditions (binding for future dispatch after scope decision):**
1. **BASELINE_SHA = `71ddb95`** (Sub-B worktree HEAD).
2. **Worktree branch `phase7-sub-c-web`** based on `phase7-sub-b-services` (chained from Sub-B).
3. **Sub-C's done criteria gate is FULL-SUITE-GREEN** (this is the integration gate; restoring main to green via the final merge).
4. **Operator-witnessed browser verification gate is BINDING for Sub-C end** (per Phase 7 binding convention; HTMX-driven UX cannot be verified by TestClient alone).
5. **Final integration merge after Sub-C ships green**: `git checkout main && git merge --no-ff phase7-sub-c-web -m "Merge phase7-sub-c-web into main: Phase 7 (Sub-A + Sub-B + Sub-C integrated)"`. Brings all 3 sub-dispatches' work in single merge commit. Production DB triggers 0014 migration on first `swing` invocation post-merge (backup-runner discipline applies).

**Sub-B pre-conditions** (historical; SATISFIED at dispatch time):
1. ✅ BASELINE_SHA = `78c7005` (Sub-A worktree HEAD).
2. ✅ Worktree branch `phase7-sub-b-services` chained from `phase7-sub-a-schema`.
3. ✅ Done criteria gate: partial-suite-green met (Sub-A + Sub-B tests GREEN; Sub-C tests stay RED until Sub-C).
4. ✅ Shim removal partial per implementer constraint (B.4 exit service migrated; full deletion deferred per scope of remaining consumers).
5. ✅ R2 Minor 1 deferral handled at B.1 (defensive docstring) + B.3 (atomic record_entry flow).
6. ✅ Vocabulary already locked.
7. ✅ Main during Sub-B window: only docs-only commits per discipline (operator-aware Sub-B-pre-empt YOU-trade migration `eba1625` was pre-dispatch; no in-flight commits).

**Sub-C pre-conditions (binding for future dispatch after Sub-B):**
1. **BASELINE_SHA = Sub-B worktree HEAD** (chained from `phase7-sub-b-services`).
2. **Worktree branch `phase7-sub-c-web`** based on `phase7-sub-b-services`.
3. **Sub-C's done criteria gate is FULL-SUITE-GREEN** (this is the integration gate; restoring main to green via the final merge).
4. **Shim deletion completes at Sub-C T1** (web view models — final consumer).
5. **Operator-witnessed browser verification gate is BINDING for Sub-C end** (per Phase 7 binding convention; HTMX-driven UX cannot be verified by TestClient alone).
6. **Final integration merge after Sub-C ships green**: `git checkout main && git merge --no-ff phase7-sub-c-web -m "Merge phase7-sub-c-web into main: Phase 7 (Sub-A + Sub-B + Sub-C integrated)"`. Brings all 3 sub-dispatches' work in single merge commit. Production DB triggers 0014 migration on first `swing` invocation post-merge (backup-runner discipline applies).

**Plan-shipped status** (2026-05-04, historical): plan at `docs/superpowers/plans/2026-05-04-phase7-trade-lifecycle-state-machine-plan.md` (commits `18bb35e..251cc35`; 4172 lines; 4 Codex rounds → NO_NEW_CRITICAL_MAJOR with 13 substantive findings + 2 advisory). Writing-plans dispatch brief at `docs/phase7-trade-lifecycle-state-machine-writing-plans-brief.md` (`3f7d5c1`). Plan organizes into 3 sub-dispatches (Sub-A schema/repos/state — 11 tasks; Sub-B services/CLI — 9 tasks; Sub-C web/UX — 8 tasks). Carve-out ~45 files. Total expected new fast tests: +150-250 wide band.

**Sub-A pre-conditions** (historical; SATISFIED at dispatch time):
1. ✅ Vocabulary operator-confirm (catalyst-9 / emotional_state-8 / event_type-7 — confirmed 2026-05-04).
2. ✅ Production DB backup verified to off-Drive path before migration.
3. ✅ Main at BASELINE_SHA `aa2dd60` with full fast suite green at dispatch start.
4. ✅ Marker-file Codex-blocking workflow per binding convention 2026-05-02.

**Brainstorm-shipped status:** 3 Codex rounds → NO_NEW_CRITICAL_MAJOR. Spec at `docs/superpowers/specs/2026-05-04-phase7-trade-lifecycle-state-machine-design.md` (commits `2c5fd34` initial → `c926f01` 3-round revisions). Brainstorm dispatch brief at `docs/phase7-trade-lifecycle-state-machine-brainstorm-brief.md` (`db6727d` + `9e4a761` hard-conflict-escape addition).

**Locked design decisions (from spec; do NOT relitigate at writing-plans):**
- **5-state minimal:** `entered → managing → partial_exited → closed → reviewed`. NO `planned/triggered/canceled` — `watchlist + watchlist_archive` already serves "plan and abandon." Cheap A→B expansion preserved via table-driven required-fields validator.
- **Unidirectional graph:** no `partial_exited → managing` (no pyramiding per locked constraint). Same-day stop-out = `entered → managing → closed` atomic double-transition.
- **`status` DROPPED entirely** (12 production files + 43 test files identified; full enumeration deferred to plan). 4 operation-specific predicate categories: active-trade / closed-but-not-reviewed / closed-or-reviewed / write-paths. Migration 0004 partial unique index recreated against new state predicate.
- **Fills replaces exits:** 4-action enum (`entry/trim/exit/stop`; drops `cover/add`). 1:1 backfill with `ORDER BY exit_date ASC, id ASC` deterministic ordering + 4-fixture preservation invariant test gate.
- **Aggregate denormalization on `trades`:** `current_size REAL NOT NULL`, `current_avg_cost`, `last_fill_at` — recomputed by fills-write service after every insert (single-write-path consistency).
- **`pre_trade_locked_at`:** set atomically at first `action='entry'` fill. V1 ships READ-ONLY display + audit visible; edit UI deferred to V2 (schema fully supports).
- **Premortem schema:** 3 named NULLABLE TEXT columns (technical/market_sector/execution) + 1 optional. Min-1-per-category enforced at app layer.
- **Thesis fields:** 18 KEPT + 12 DROPPED (per-field rationale in spec). All schema-NULLABLE; app-layer enforces non-empty for new entries; legacy NULL persists.
- **Pre-trade gate:** existing checks preserved + new `MissingPreTradeFieldsException` (NOT force-bypassable). Phase 9 deferred: portfolio_heat / consecutive_loss / drawdown_breaker.
- **trade_origin derivation:** 5-bucket × 4-entry-path → 4-value enum; `EntryPath` enum on `EntryRequest`; frozen-at-entry per `hypothesis_label` precedent.

**Operation-contextual validation** (added Codex R1 fix): `entry_create` enforces full required set; `transition_managing/partial_exited/closed` triggers suffice; `transition_reviewed` uses Phase 6 review-completion fields only; legacy rows exempt by NULLABLE schema.

**In-flight migration plan (verify at writing-plans dispatch):**
- VIR (closed+reviewed): `state='reviewed'`, `pre_trade_locked_at = entry_date+T16:00:00`, `trade_origin='manual_off_pipeline'` (pre-engine), 1 entry-fill + 1 exit-fill backfilled.
- DHC (open 2026-04-27, $7.58×39): `state='managing'`, `pre_trade_locked_at='2026-04-27T16:00:00'`, `trade_origin='pipeline_watch_hyp_recs'` (FIRM — operator confirmed 2026-05-04: DHC entered via Take-this-trade-equivalent on hyp-rec row with label "Sub-A+ VCP-not-formed (watch); failed: proximity_20ma, tightness"; bucket=`watch` confirmed empirically in candidates), 1 entry-fill, current_size=39.
- CC (open 2026-04-30, $26.97×5): `state='managing'`, `pre_trade_locked_at='2026-04-30T16:00:00'`, `trade_origin='pipeline_watch_hyp_recs'` (FIRM — phase3e-todo entry "Entry form stop-value populated incorrectly during CC entry... Take-this-trade button on hyp-recs expansion" confirms entry path), 1 entry-fill, current_size=5.
- **YOU (open 2026-05-04, $56.29×2; ADDED 2026-05-04 between writing-plans and Sub-A dispatch):** `state='managing'`, `pre_trade_locked_at='2026-05-04T16:00:00'`, `trade_origin='pipeline_aplus'` (FIRM — bucket=`aplus` confirmed in candidates table action_session 2026-05-04 + present in daily_recommendations as `today_decision`; rationale='aplus-setup' in trade_events; hypothesis_label='A+ baseline (aplus)'; operator notes "Below calculated pivot, asses pivot was aberration, went when above next highest pivot."), 1 entry-fill, current_size=2.

**Phase carve-out (~37 files; full enumeration in spec §15):** schema/data 0014.sql NEW + models.py + db.py MOD; repos trades.py MOD + fills.py NEW; services state.py NEW + entry/exit/stop_adjust/review.py MOD + origin.py NEW + derived_metrics.py NEW; web routes/trades.py + 2 view_models + 3 templates MOD; CLI MOD; journal carve-out (stats/flags/analyze/tos_import.py predicate rewrites — no schema-shape work); 4 NEW + 7 MOD test files.

**Open questions for writing-plans dispatch:**
- DHC trade_origin best-guess weak — operator may have direct recall of CLI vs web vs Take-this-trade entry path (orchestrator could not disambiguate from `trade_events.payload_json` alone; both DHC + CC have `rationale='other'`). If operator confirms otherwise, plan adjusts migration UPDATE.
- Vocabulary lists sketched (catalyst 9 / emotional_state 8 / event_type 7 values) committed as recommendations; final operator-confirm at writing-plans spec-review checkpoint.

**Estimated implementation dispatches (post-writing-plans):** 2-3 executing-plans sub-dispatches (Sub-A schema+repos+state-machine; Sub-B services+CLI; Sub-C web) + 1 verification dispatch. Total 4-6 downstream of brainstorm.

**Test count band (rough; per Phase 6 lesson "test-count-projections-bias-high"):** +150-250 fast tests (wide band; parameterization decisions affect raw count).

**Cross-references:**
- `reference/Future Work/Trading Journal/swing_trading_journal_ai_ingestion_v1.2.md` §5 (state machine), §7.5 (Trade_Log), §7.6 (Fills), §10.2 (Pre-Trade Lock).
- Spec: `docs/superpowers/specs/2026-05-04-phase7-trade-lifecycle-state-machine-design.md`.
- Brainstorm brief: `docs/phase7-trade-lifecycle-state-machine-brainstorm-brief.md`.
- Existing entry-form architecture: `swing/web/view_models/trades.py` + `swing/web/routes/trades.py` (Phase 4.5 `f9a07bf`).

---

## 2026-05-04 Worktree cleanup script: pytest-of-rwsmy ACL-lock pattern recurrence check (TRIGGER FIRED + RESOLVED 2026-05-05)

**Trigger fired 2026-05-05** during Phase 7 integration cleanup. Recurrence count: **5/5 worktrees affected** (Phase 5 + Phase 6 + Phase 7 Sub-A + Sub-B + Sub-C). Pattern durably confirmed; script extension landed at commit `5430c1c`.

**Script extension implemented** (`cleanup-locked-scratch-dirs.ps1`):
1. Added orphaned-worktree discovery branch: reads `.worktrees/` subdirs; parses `git worktree list` to identify orphaned (deregistered-but-on-disk) ones; admits them via two-track allowlist (scratch-name pattern OR `.worktrees/...` path-prefix + Reason-tag).
2. Strengthened cleanup sequence from 3-step (takeown / icacls grant / Remove-Item) to 4-step (takeown / **icacls /reset /T /C /Q** / icacls grant / Remove-Item). The /reset step forces inheritance from parent before /grant adds explicit operator perms — handles the deeply-locked `.tmp/pytest-of-rwsmy/` subdirs that resisted /grant-only treatment in Phase 6 manual cleanup attempt 2026-05-04 (which got 1196/1198; 2 stuck files remained).
3. Added `-SkipWorktrees` switch (default $false = include) for backward-compat; legacy callers can opt out.
4. Updated doc-comment block at top to describe dual-discovery + recurrence-trigger fired note.

**Verified-empirical execution 2026-05-05:** elevated-PS run cleaned **4/4 dirs** (3 Phase 7 worktrees + leftover Phase 6 worktree from prior incomplete manual cleanup). The /reset step resolved Phase 6's 2-stuck-files issue too. `git worktree list` shows only main; `.worktrees/` directory empty post-execution.

**Status: V1 SCOPE COMPLETE.** Future cleanup runs use the extended script. If a NEW lock pattern emerges (different from pytest-of-rwsmy/Codex-sandbox), extend allowlist as needed.

---

## 2026-05-04 Worktree cleanup script: pytest-of-rwsmy ACL-lock pattern recurrence check (HISTORICAL — superseded by 2026-05-05 RESOLVED entry above)

**Trigger:** AFTER Phase 7 ships (all 3 sub-dispatches A/B/C merged to main). At that point, attempt to cleanup `.worktrees/phase7-sub-a-schema/`, `.worktrees/phase7-sub-b-services/`, `.worktrees/phase7-sub-c-web/`. If any of them surface the same `.tmp/pytest-of-rwsmy/` ACL-lock pattern that Phase 5 + Phase 6 hit, the issue is durable across phases and the cleanup script needs a permanent extension.

**Background.** Phase 5's `.worktrees/phase5-config-page-redispatch/` and Phase 6's `.worktrees/phase6-post-trade-review/` both left orphaned on-disk directories after `git worktree remove` failed with `Permission denied on .tmp/pytest-of-rwsmy/` — Windows ACL inheritance from the pytest subprocess's tmp dir. The 2026-05-02 `cleanup-locked-scratch-dirs.ps1` extension added Codex-sandbox naming patterns but does NOT match `pytest-of-rwsmy/`. Phase 6 cleanup attempt 2026-05-04 (`takeown /F ... /R /D Y` + `icacls ... /reset /T /C /Q` + `Remove-Item -Recurse -Force`) succeeded on 1196/1198 files but 2 files in `.tmp/pytest-of-rwsmy/` remained ACL-locked.

**Why deferred to post-Phase-7:** Phase 7 has 3 worktrees (Sub-A/B/C). After all 3 ship, we have 5 data points (Phases 4 + 5 + 6 + Phase 7 sub-dispatches) on whether this is recurring. If Sub-A/B/C all hit it, the pattern is durable + the cleanup script needs the extension. If only some hit it, the pattern correlates with something other than just Windows ACL inheritance (test runner state? subagent isolation?) and a deeper investigation is warranted before the script extension.

**V1 scope (when triggered):**
1. Document the recurrence count post-Phase-7 (how many of A/B/C hit the lock; commands attempted; success rate per cleanup approach).
2. Extend `cleanup-locked-scratch-dirs.ps1` to handle `.tmp/pytest-of-rwsmy/**` patterns: ownership transfer + ACL reset + retry-with-elevation if still locked.
3. Add a corresponding gotcha entry to CLAUDE.md (Windows-section): pytest tmp-dir ACL-inheritance breaking worktree cleanup.
4. Verify the script handles all 3 Phase 7 sub-dispatch worktrees in actual mode (not just DryRun).

**Out-of-scope:**
- Modifying pytest's tmp-dir creation behavior (upstream concern; would need pytest config change).
- Eliminating the `.tmp` dir creation in worktrees entirely (pytest needs it for parallel-test scratch).
- Investigating WHY Windows ACL inheritance produces immutable subdirs (deep Windows-internals work; not productive).

**Cross-references:**
- `docs/orchestrator-context.md` §"Active orchestrator-side housekeeping" — Phase 6 cleanup state recorded.
- `cleanup-locked-scratch-dirs.ps1` (project root) — current script; needs `.tmp/pytest-of-rwsmy/` pattern addition.
- Phase 5 cleanup pattern recurrence (orchestrator-context lessons captured 2026-05-02).
- Phase 6 cleanup partial-success record (orchestrator-context "Active orchestrator-side housekeeping" 2026-05-04).

---

## 2026-05-04 Handoff document growth — structural separation + retention discipline (TRIGGER FIRED + RESOLVED 2026-05-05)

**Trigger fired 2026-05-05.** Operator chose to pre-empt despite the formal 300k-token tripwire not yet firing (~167k full-bootstrap), citing operational friction: both `docs/orchestrator-context.md` (~81k tokens, 565 lines) and `docs/phase3e-todo.md` (~79k tokens, 1452 lines) had crossed the Read-tool 25k single-call cap, requiring chunked reads to bootstrap. **Resolved** via this dispatch — structural separation into `*-active` + `*-archive` pairs + retention-discipline maintenance section in `docs/orchestrator-context.md`. Original entry retained below for context.

### Original entry (2026-05-04)

Operator-surfaced 2026-05-04 during Phase 7 brainstorm dispatch prep. The fresh-orchestrator handoff pattern (start a new conversation instance before each major iteration to minimize accumulated tool-result noise) loses leverage as the persisted handoff documents themselves grow.

### Problem

`docs/orchestrator-context.md` (~71k tokens) and `docs/phase3e-todo.md` (~65k tokens) accrete monotonically — lessons captured, recent decisions, in-flight prose, SHIPPED items. Fresh-orchestrator bootstrap currently consumes ~200-250k tokens to load context (the two accreting docs + `CLAUDE.md` + system prompt + initial `git status`/`git log`). Growth rate ~30-50k tokens/phase. Beyond a threshold, bootstrap consumes enough of the working window that the savings vs continuing a long conversation are largely defeated.

### Trigger

Fire the project when total bootstrap consumption (after a fresh orchestrator reads `docs/orchestrator-context.md` + `docs/phase3e-todo.md` + `CLAUDE.md` + runs `git status` + `git log --oneline -20`) exceeds **300k tokens** (~30% of Opus 1M window). Measured by the orchestrator's reported context utilization after standard bootstrap (e.g., `/cost` or equivalent context-check). Below threshold: bank the observation, defer.

Operator-paced verification: any fresh orchestrator can sanity-check bootstrap consumption against this trigger; if exceeded, surface to operator as project-readiness signal.

### Recommended approach (subject to re-evaluation when triggered)

1. **Structural separation (one-time refactor; dominant cost).** Split each accreting doc into `*-active` + `*-archive`:
   - `orchestrator-context-active.md` (current state, immediate next moves, currently-binding framings — capped) + `orchestrator-context-archive.md` (historical narrative, older captured lessons, superseded decisions).
   - `phase3e-todo-active.md` (open backlog) + `phase3e-todo-archive.md` (SHIPPED items + closed entries).
   - Bootstrap discipline: fresh orchestrator reads only `-active` files; archive is searchable on demand via grep / Read.
2. **Light retention discipline (ongoing; minor curation cost).**
   - SHIPPED items in `phase3e-todo.md` move to archive when the next phase ships (one-phase cooldown).
   - "Lessons captured" caps at last ~30 entries; older lessons promote to `CLAUDE.md` (when durable code-failure prevention) or archive (when process-only).
   - "Recent decisions and framings" entries that have been superseded migrate to archive.

### Out-of-scope alternatives considered

- Pure compression (replace prose with terse cross-refs to per-phase briefs) — sacrifices "everything in one file" without structural clarity benefit.
- Bootstrap-discipline change alone (cap reading without splitting) — discipline-failure risk; silent recurrence.
- Tooling-based auto-summary script (regenerate snapshot from git log + DB) — premature; structural separation is simpler and lower-maintenance.

### Estimated effort

1 dispatch — one-time refactor (split docs, write the cross-reference scaffolding, populate active vs archive) + write the retention-discipline rules into `orchestrator-context-active.md` as a maintenance section. Probably writing-plans-skip viable; copowers:executing-plans direct.

### Cross-references

- `docs/orchestrator-context.md` §"Lessons captured" + §"Currently in-flight work" (especially the per-phase prose paragraphs) + §"Recent decisions and framings" — three highest-velocity growth surfaces.
- `docs/phase3e-todo.md` — entire file; SHIPPED items 3e.1 / 3e.3 / 3e.4 / 3e.5 (2026-04-26) still inline a week later, illustrating the cooldown-archival opportunity.
- This entry's tripwire mechanism is itself a precedent for trigger-gated backlog items (vs always-active or operator-paced-deferred). If useful, document the pattern in `orchestrator-context.md` after first activation.

### Resolution outcome (2026-05-05)

- `docs/phase3e-todo-archive.md` created (this file); SHIPPED + closed sections migrated.
- `docs/orchestrator-context-archive.md` created; older lessons + settled framings migrated.
- `docs/orchestrator-context.md` gained §"Maintenance: retention discipline" section.
- `CLAUDE.md` bootstrap pointer updated to mention archive companions.
- Naming convention chosen: canonical filenames preserved as active (`docs/phase3e-todo.md`, `docs/orchestrator-context.md`) + `-archive.md` suffix on companions; preserves ~46 cross-references in shipped briefs.
- Archive-split-trigger captured in retention-discipline maintenance section: revisit hierarchical decomposition if any archive file exceeds ~80k tokens.
