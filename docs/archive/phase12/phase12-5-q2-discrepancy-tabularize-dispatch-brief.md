# Phase 12.5 Q2 — Discrepancy resolution comparison rendering tabularize (web + CLI) — Executing-plans Dispatch Brief

**Audience:** Fresh Claude Code instance with no prior conversation context.

**Mission:** Tabularize the journal-side vs Schwab-side value comparison rendering on BOTH the web `/reconcile/discrepancy/{id}/resolve` form page AND the CLI `swing journal discrepancy show-ambiguity <id>` subcommand. Currently rendered as LIST; operator wants TABLE format for readability. Presentation-only — no behavioral changes; no schema work; no new discrepancy types. Shipped via `copowers:executing-plans`; brief plays plan-role (skip brainstorm + writing-plans per Phase 12 Sub-bundle A precedent).

**Brief:** `docs/phase12-5-q2-discrepancy-tabularize-dispatch-brief.md` (this file).

**Sequencing:** Phase 12.5 #3 CLOSED 2026-05-18 (`b436067`); Q1 reconciliation walkthrough CLOSED at `89971f2` (architectural window-mismatch diagnosis; cfg-bumped `lookback_days` 7→30; 7 dispositions correction_ids 20-26; NEW V2 dynamic-lookback candidate banked). **Q2 is the LAST Phase 12.5 cleanup item before Phase 13 commission.**

**Expected duration:** ~2-4 hr implementation + ~30-60 min Codex chain + 3-4 surface operator-witnessed gate. Total **~1 day operator-paced** (per `feedback_time_estimates_overstated.md` calibration). Schema v19 UNCHANGED LOCK preserved.

**Skill posture:**
- Invoke `copowers:executing-plans` against this brief as PLAN_PATH (brief plays plan-role; no separate writing-plans dispatch).
- The skill wraps `superpowers:subagent-driven-development` + adversarial Codex review.
- Adversarial review runs after all tasks land. Expected **1-2 Codex rounds** (small bounded scope; presentation-only). ZERO ACCEPT-WITH-RATIONALE expected (matches Phase 12.5 arc clean-record streak).

---

## §0 Inputs

### §0.1 Brief plays plan-role

Phase 12.5 Q2 has bounded architectural surface (presentation rendering only; no new discrepancy types; no schema work; ~2-4 tasks). Brief encodes the plan; implementer ships against this brief directly. **Precedent**: Phase 12 Sub-bundle A SHIPPED at `123d27a` ("skipped brainstorm + writing-plans per operator scope decision (brief plays plan-role)").

### §0.2 Project state at dispatch time

- **HEAD on `main`:** `89971f2` (Q1 closure commit). Resolve via `git rev-parse main` at worktree-creation time.
- **Test count:** **4854 fast passing on main** + 3 pre-existing failures eliminated (Phase 12.5 #3 T-3.5 promoted 3 Phase 8 walkthrough tests to passing) + 1 skipped (only `test_flag_classifier_integration.py:21` legitimate-deferred Phase 13 Theme 2). **Phase 12.5 #3 Q3 disposition** redirected 4 net-liq extraction tests from gitignored `thinkorswim/` to sanitized `tests/fixtures/tos/schwab-real-world-*.csv` — those 4 are now PASSING in the 4854 baseline.
- **Ruff baseline:** **0 E501 errors** (Phase 12.5 #3 T-3.6 cleared the 18 baseline). Plan MUST NOT introduce new E501.
- **Schema version:** **v19** (LOCKED since Phase 12 Sub-sub-bundle C.A; F1 LOCK preserved through Phase 12.5 arc). **Q2 MAY NOT widen schema** (this brief §F escalation rule).
- **Production state:** ZERO open discrepancies (Q1 closure dispositioned 7; CFG `lookback_days=30` now in user-config.toml). Banner count=0.
- **Worktree husks:** 8+ pending operator cleanup-script pass; NOT blocking executing-plans dispatch. Q2 adds 1 new husk.

### §0.3 Cross-references (must read at task time)

- **Phase 12.5 #2 spec** at `docs/superpowers/specs/2026-05-18-phase12-5-bundle-2-web-tier2-discrepancy-resolution-design.md` §5.2 (`ReconcilePreResolutionContext` 15-field dataclass; PRIMARY EXTENSION TARGET).
- **Phase 12.5 #2 plan** at `docs/superpowers/plans/2026-05-18-phase12-5-bundle-2-web-tier2-discrepancy-resolution-plan.md` §A T-2.2 (`ReconcilePreResolutionContext` shipped shape; existing 10 per-discrepancy-type render helpers).
- **Shipped surfaces** (read-only; understand contract):
  - `swing/web/view_models/reconcile.py` (~860 LOC; 4 frozen dataclasses + 10 per-type render helpers + dispatch + builder + generic fallback + parametric-pick parser).
  - `swing/web/templates/reconcile_discrepancy_resolve.html.j2` (form template with pre-resolution context section above choice menu).
  - `swing/cli.py:show_ambiguity` (CLI subcommand under `swing journal discrepancy`).
- **CLAUDE.md Gotchas section** — especially:
  - **"Windows PowerShell stdout defaults to cp1252; non-ASCII glyphs ... will raise UnicodeEncodeError and crash the CLI"** — BINDING for CLI table rendering. ASCII-only chars (`|`, `-`, `+`); NO Unicode box-drawing (`┌`, `─`, `│`).
  - "Synthetic-fixture-vs-production-emitter shape drift" — test discipline.
  - "`base.html.j2` is shared — new `vm.foo` field requires adding to EVERY base-layout VM" — N/A here (we're not adding to BaseLayoutVM; we're extending ReconcilePreResolutionContext).

---

## §1 Operator-locked decisions (pre-baked 2026-05-18 post-Q1-closure; DO NOT re-litigate)

### §1.1 Column headers = **"Journal | Schwab"**

Mirrors architectural language: `expected_value_json` = journal-side; `actual_value_json` = Schwab-side. Used verbatim in HTML table headers + CLI table headers.

### §1.2 VM field shape = **restructure with new `compared_pairs` field**

NEW field `compared_pairs: list[tuple[str, Any, Any]] | None = None` (default None for non-tabular discrepancy types) on `ReconcilePreResolutionContext`. Tuple is `(field_label, journal_side_value, schwab_side_value)`. Existing 15 single-side context fields PRESERVED as-is for the non-tabular display portion above/below the table. Per-discrepancy-type render helpers populate the new field by extracting pairs from `expected_value_json` + `actual_value_json` of the underlying discrepancy.

### §1.3 Shared helper location = **NEW `swing/trades/reconciliation_render.py`**

Neutral module (parallel to `reconciliation_classifier.py` + `reconciliation_validators.py` + `reconciliation_auto_correct.py`). Pure functions; ZERO DB access; ZERO Schwab API. Web template + CLI both import from this module. CLI does NOT import from `swing/web/`.

### §1.4 Schema v19 UNCHANGED LOCK (carries from Phase 12.5 arc)

If any task surfaces a schema need (which it should NOT for presentation-only work), STOP + escalate to operator.

### §1.5 ZERO Co-Authored-By footer (durable project invariant)

~165+ project-cumulative streak preserved. Plan author MUST cite explicit suppression in every commit message stem.

---

## §2 Task decomposition (4 tasks; brief §A plays plan-role)

### §A.1 — T-Q2.1: NEW shared helper module `swing/trades/reconciliation_render.py`

**Scope:** Pure-function ASCII-only table renderer for journal-side vs Schwab-side comparison pairs.

**Signature:**
```python
def render_journal_schwab_comparison_table_ascii(
    pairs: list[tuple[str, Any, Any]],
    *,
    journal_label: str = "Journal",
    schwab_label: str = "Schwab",
) -> str:
    """Render comparison pairs as an ASCII-only table.

    Returns a multi-line string with `|` column separators + `-` horizontal
    rules + header row + N data rows. Uses ONLY ASCII chars (`|`, `-`, `+`,
    space) for Windows cp1252 stdout safety (per CLAUDE.md gotcha). Each
    cell is rendered via `repr(value)` if non-string + truncated/wrapped
    sensibly. ZERO third-party dependencies (no `rich`, no `tabulate`)."""
```

**Implementation requirements:**
- ASCII-only chars (`|`, `-`, `+`, space, alphanumerics). NO Unicode box-drawing.
- Column widths: compute from max content width per column; cap at reasonable max (e.g., 40 chars per cell) with truncation indicator `...` if exceeded.
- Header row: `Field | Journal | Schwab` (3 columns).
- Horizontal rule: `------+---------+--------` (separator row using `-` + `+`).
- Empty `pairs` list: return empty string OR single-line "(no comparison data)" placeholder (implementer decides; document in docstring).
- NULL/None values: render as `(null)` or `-` placeholder.
- Numeric values: render with reasonable precision (e.g., 2 decimal places for monetary; default `repr` for others).

**Files:**
- NEW `swing/trades/reconciliation_render.py` (~50-100 LOC; pure functions only).

**Tests:**
- NEW `tests/trades/test_reconciliation_render.py` (~5-10 discriminating tests):
  - Empty pairs list → empty string OR placeholder.
  - Single pair → 3-row output (header + rule + data).
  - Multi-pair with varying widths → column alignment correct.
  - Long values → truncation with `...` indicator.
  - NULL values → `(null)` or `-` placeholder.
  - ASCII-only audit: assert `all(ord(c) < 128 for c in output)`.

**Acceptance:**
- `from swing.trades.reconciliation_render import render_journal_schwab_comparison_table_ascii` imports cleanly.
- All tests PASS.
- ASCII-only audit holds for every test case.
- ZERO third-party imports (no `rich`/`tabulate`).
- ZERO DB / Schwab API / file I/O in module.

**Commit message stem:** `feat(trades): T-Q2.1 — NEW reconciliation_render.py ASCII table helper for journal/Schwab comparison (no Co-Authored-By footer per project invariant)`.

---

### §A.2 — T-Q2.2: VM reshape — `ReconcilePreResolutionContext.compared_pairs` + per-type render helper updates

**Scope:** Extend `ReconcilePreResolutionContext` dataclass with new `compared_pairs` field; update all 10 per-discrepancy-type render helpers to populate it.

**Implementation requirements:**
- NEW field: `compared_pairs: list[tuple[str, Any, Any]] | None = None` (default `None` for discrepancy types that don't naturally compare).
- Per-discrepancy-type render helpers (10 helpers in `swing/web/view_models/reconcile.py`) — each populates `compared_pairs` with the relevant journal-vs-Schwab pairs for that discrepancy type. Examples:
  - `entry_price_mismatch` → `[("price", journal_price, schwab_price), ("quantity", journal_qty, schwab_qty), ("date", journal_date, schwab_date)]`
  - `close_price_mismatch` → similar to entry_price_mismatch.
  - `stop_mismatch` → `[("stop_price", journal_stop, schwab_stop)]`
  - `position_qty_mismatch` → `[("position_qty", journal_qty, schwab_qty)]`
  - `cash_movement_mismatch` → relevant cash fields.
  - `unmatched_open_fill` / `unmatched_close_fill` → MAY or MAY NOT populate (the "matched": null sentinel means there's no Schwab side); implementer decides; if not populated, `compared_pairs = None` → table section hidden.
  - `sector_tamper` / `industry_tamper` → operator-claim vs cached value (3-tuple).
  - `equity_delta` → `[("equity_dollars", journal_equity, source_equity)]`.
- Existing 15 single-side context fields PRESERVED unchanged.
- Generic fallback (`build_reconcile_pre_resolution_context_generic`) sets `compared_pairs = None`.

**Files:**
- MODIFY `swing/web/view_models/reconcile.py` (~+30-60 LOC across dataclass + 10 helpers).

**Tests:**
- EXTEND existing tests at `tests/web/test_view_models/test_reconcile.py` (or equivalent path):
  - Per-discrepancy-type helper test: assert `compared_pairs` populated with expected tuples.
  - Generic fallback test: assert `compared_pairs = None`.
  - Spec §5.2 field-count audit: existing 15 fields + 1 new field = 16; verify dataclass `__dataclass_fields__` count.

**Acceptance:**
- `ReconcilePreResolutionContext` dataclass has new `compared_pairs` field with safe default `None`.
- All 10 per-discrepancy-type render helpers populate the field (or explicitly set None for types where comparison doesn't apply).
- All existing tests STILL PASS.
- NEW field-population tests PASS.

**Commit message stem:** `feat(web/vm): T-Q2.2 — ReconcilePreResolutionContext.compared_pairs field + populate across 10 per-type render helpers (no Co-Authored-By footer per project invariant)`.

---

### §A.3 — T-Q2.3: Web template renders compared_pairs as HTML `<table>`

**Scope:** Update `swing/web/templates/reconcile_discrepancy_resolve.html.j2` to render `compared_pairs` as ARIA-compliant HTML table.

**Implementation requirements:**
- Place table BEFORE the existing single-side context list (operator wants comparison visible-above-list).
- Use `<table class="reconcile-comparison-table">` + `<thead><tr><th>Field</th><th>Journal</th><th>Schwab</th></tr></thead>` + `<tbody>` with one `<tr>` per pair.
- ASCII-only labels (Phase 12.5 #2 F20 LOCK preserved).
- Conditional render: only emit table if `vm.compared_pairs is not None and vm.compared_pairs|length > 0`; otherwise skip the table section entirely.
- ARIA: `<table aria-label="Journal vs Schwab comparison for {{ vm.discrepancy_type }}">` for screen reader support.
- Style class lives in existing CSS (if needed for spacing/borders, add to existing CSS file; do NOT inline-style).
- The existing single-side context list stays AS-IS below the table.

**Files:**
- MODIFY `swing/web/templates/reconcile_discrepancy_resolve.html.j2` (~+10-20 LOC).
- OPTIONAL: MODIFY existing CSS file if styling needed (orchestrator decides at task time; implementer may inline a minimal `style` if no shared CSS exists for the page).

**Tests:**
- EXTEND existing tests at `tests/web/test_routes/test_reconcile_resolve.py` (or equivalent):
  - Discrepancy type with compared_pairs populated → assert response contains `<table class="reconcile-comparison-table">` + `<th>Field</th><th>Journal</th><th>Schwab</th>` + N `<tr>` data rows.
  - Discrepancy type with `compared_pairs = None` → assert table absent from response.
  - ARIA label present.

**Acceptance:**
- Web template renders HTML table for tabular-capable discrepancy types.
- Table absent for `compared_pairs = None` types.
- All existing route tests STILL PASS.
- NEW table-render tests PASS.
- ASCII-only audit on rendered template strings.

**Commit message stem:** `feat(web/template): T-Q2.3 — reconcile_discrepancy_resolve.html.j2 renders compared_pairs as HTML <table> with Journal | Schwab columns (no Co-Authored-By footer per project invariant)`.

---

### §A.4 — T-Q2.4: CLI integration — `swing journal discrepancy show-ambiguity <id>` renders ASCII table

**Scope:** Update CLI subcommand to import shared helper + render ASCII table on stdout when discrepancy has `compared_pairs`.

**Implementation requirements:**
- Locate the CLI surface for `swing journal discrepancy show-ambiguity` (likely under `swing/cli.py` discrepancy command group; search via `grep -n "show.ambiguity\|show_ambiguity" swing/cli.py`).
- Build a `compared_pairs` list inline (CLI doesn't go through the web VM — it queries the DB directly OR uses a shared builder). Two implementation options:
  - **Option A**: extract a builder helper (e.g., `build_compared_pairs_for_discrepancy(conn, discrepancy_id) -> list[tuple] | None`) and move it from VM-only to `swing/trades/reconciliation_render.py` OR a sibling. CLI imports the builder.
  - **Option B**: build inline in the CLI using same logic as the per-type VM helpers. Higher risk of drift.
- **Implementer chooses + Codex reviews**; prefer Option A for less drift.
- Print the ASCII table via `click.echo(render_journal_schwab_comparison_table_ascii(pairs))`.
- Render position: BEFORE the existing single-side context list (matches web rendering order).
- Conditional: only render table if `compared_pairs` non-empty; otherwise skip.

**Files:**
- MODIFY `swing/cli.py` (or wherever `show_ambiguity` lives; ~+10-20 LOC).
- POSSIBLY MODIFY `swing/trades/reconciliation_render.py` to add builder helper if Option A chosen.

**Tests:**
- EXTEND existing tests at `tests/cli/test_discrepancy_show_ambiguity.py` (or equivalent):
  - Discrepancy with `compared_pairs` populated → captured stdout contains `|` separators + `Journal` + `Schwab` headers + expected row content.
  - Discrepancy with no compared_pairs → no table in output.
  - **Subprocess test for cp1252 validation** (per CLAUDE.md "Discriminating-test gap" note): construct a subprocess invocation through PowerShell (Windows-only OR cross-platform-equivalent) + capture stdout + assert no UnicodeEncodeError + assert table content present. May be slow-marked (~+1 slow test) if subprocess-spawn is heavy.

**Acceptance:**
- CLI renders ASCII table for tabular-capable discrepancy types.
- Table absent for non-tabular types.
- All existing CLI tests STILL PASS.
- NEW table-render tests PASS.
- Subprocess cp1252-encoding test PASSES (or operator-accepted SKIP-with-rationale if cross-platform constraints intervene).

**Commit message stem:** `feat(cli): T-Q2.4 — show-ambiguity renders ASCII journal/Schwab comparison table via shared helper (no Co-Authored-By footer per project invariant)`.

---

## §3 Test projection + Codex chain

### §3.1 Projected test delta

- T-Q2.1: ~+5-10 tests (helper unit tests).
- T-Q2.2: ~+5-15 tests (VM field population per-type + dataclass audit).
- T-Q2.3: ~+5-10 tests (web template render assertions).
- T-Q2.4: ~+5-10 tests + 1 slow subprocess test (CLI render + cp1252 validation).
- **Total: ~+20-45 fast tests + 1 slow test** (presentation-only work; modest projection).
- Baseline 4854 fast → projected ~4874-4900 post-merge.

### §3.2 Codex chain expectation

**1-2 Codex rounds** (small bounded scope; presentation-only; ZERO architectural ambiguity post-operator-locks; ZERO schema work).

ZERO ACCEPT-WITH-RATIONALE expected (matches Phase 12.5 #1 + #2 + #3 + finviz-fix + post-Phase-12 Sub-bundle arc clean-record streak).

---

## §4 Adversarial review watch items (pass as targeted prompts to `copowers:adversarial-critic`)

1. **ASCII-only invariant** (CLAUDE.md cp1252 gotcha) — render helper output MUST contain only `ord(c) < 128` characters. Discriminating test: synthetic input with Unicode-named field labels + assert renderer emits ASCII-only (either escapes or rejects).
2. **`compared_pairs is None` vs empty list semantics** — None means "discrepancy type doesn't support tabular comparison" (table section hidden); empty list means "tabular-capable but no data" (placeholder rendered). Plan author MUST disambiguate per discrepancy type + discriminating test asserts the distinction.
3. **Cross-document consistency** — column headers verbatim "Journal" + "Schwab" across HTML + CLI + CSS class names. Codex verifies no string-literal drift.
4. **Builder helper location** (Option A vs B) — if Option A chosen (preferred), Codex verifies the builder lives in `swing/trades/reconciliation_render.py` (NEW module) NOT in `swing/web/view_models/reconcile.py` (avoids CLI cross-import from web).
5. **`Co-Authored-By` footer suppression** — every commit message explicitly cites suppression. Project invariant; ~165+ commits cumulative ZERO drift.
6. **Pre-Codex orchestrator-side review (NEW C.C lesson #6 — BINDING)** — before invoking `copowers:adversarial-critic`, dispatch a focused reviewer subagent with §1 operator-locks + §A task decomposition as anchors; ask deviation list ≤300 words. Cumulative validation 8x as of 2026-05-18; durable pattern.
7. **Subprocess cp1252 validation gap** (T-Q2.4) — pytest `capsys` bypasses the Windows OS encoder; only subprocess-spawned CLI invocations validate cp1252 encoding works. Codex verifies the slow subprocess test is present OR accept-with-rationale documents the cross-platform constraint.
8. **Schema v19 UNCHANGED** — verify task-level (per §1.4 LOCK). If any task surfaces a schema need, escalate.

---

## §5 If you get stuck

- If Codex pushes back on the 3 operator-locks at §1 (column headers; VM reshape; helper location), HOLD THE LINE — operator-decided 2026-05-18.
- If T-Q2.2 VM reshape requires more than ~60 LOC OR touches more than 10 helpers, escalate (scope-cap).
- If T-Q2.4 CLI builder requires querying `expected_value_json` + `actual_value_json` from DB in a way that duplicates VM logic, prefer Option A (extract builder to neutral module).
- If subprocess cp1252 test (T-Q2.4) requires Windows-only infra that doesn't run in cross-platform CI, mark slow + skip on non-Windows + document.
- If implementer surfaces a need for V2.1 §VII.F amendment, bank in dispatch return report §6.
- **DO NOT propose new architectural surfaces** within Q2 scope.
- **DO NOT add `Co-Authored-By` footer** to any commit message.

---

## §6 Return report shape

After Codex chain converges + before final commit, draft a return report at `docs/phase12-5-q2-discrepancy-tabularize-executing-plans-return-report.md`:

1. Final HEAD on branch + commit count breakdown.
2. Codex round chain (R1-RN summary table + convergent shape; finding-count taper).
3. Per-task delivery summary (T-Q2.1..T-Q2.4).
4. Codex Major findings ACCEPTED with rationale (if any). Expectation: ZERO.
5. V2 candidates banked (any surfaced).
6. V2.1 §VII.F amendments banked (any new surfaced during Codex chain).
7. Forward-binding lessons for future dispatches.
8. CLAUDE.md status-line refresh draft text (orchestrator paste-in; ~150-300 chars).
9. Schema impact verdict (v19 UNCHANGED expected).
10. Test count delta + Ruff post-cleanup count (expect baseline 0 E501 preserved).
11. Worktree teardown status.

---

## §7 Operator-witnessed gate (3-4 surfaces; orchestrator-driven post-merge)

- **S1**: Inline pytest + ruff PASS — `python -m pytest -m "not slow" -q -n auto` returns baseline + projected delta (~4874-4900 fast pass); `ruff check swing/ --select E501 --statistics` returns 0; T-Q2.4 slow subprocess test PASS (or accept-with-rationale skip).
- **S2**: Web visual verification — `swing web --port 8081` + browse to `/reconcile/discrepancy/{id}/resolve` for a tabular-capable discrepancy → table renders ABOVE the existing context list; `Field | Journal | Schwab` header columns; ARIA label present; no console errors. **Note: production currently has ZERO open discrepancies post-Q1**; gate may require planting a synthetic discrepancy OR exercise via slow E2E test instead. Operator-decides at gate time.
- **S3**: CLI visual verification — `python -m swing.cli journal discrepancy show-ambiguity <id>` for a tabular-capable discrepancy in PowerShell terminal → ASCII table renders without cp1252 crash; column alignment correct; matches web S2 data shape. Same caveat re: production zero-discrepancy state; planted-discrepancy path acceptable.
- **S4**: Round-trip consistency — same discrepancy ID renders the SAME `compared_pairs` data shape in web S2 + CLI S3 (different formatting, same content).

---

## §8 Dispatch metadata

- **Subagent type:** `general-purpose` (full tool surface needed).
- **Foreground vs background:** foreground (default).
- **Worktree:** YES — branch `phase12-5-q2-discrepancy-tabularize` (matches cleanup-script regex `phase\d+[-_]`). Worktree directory `.worktrees/phase12-5-q2-discrepancy-tabularize/`.
- **Model:** defer to harness default.
- **Expected duration:** ~2-4 hr implementation + ~30-60 min Codex chain. Total **~1 day operator-paced** (per `feedback_time_estimates_overstated.md` calibration; smaller scope than Phase 12.5 #3).

---

*End of brief. Phase 12.5 Q2 executing-plans dispatch — 4 tasks (helper + VM reshape + web template + CLI integration); 3 operator-locks pre-baked (Journal|Schwab columns + compared_pairs field + neutral render module); 3-4 surface operator-witnessed gate; 1-2 Codex round expectation; ZERO ACCEPT-WITH-RATIONALE expected; ~+20-45 fast tests + 1 slow subprocess test; schema v19 UNCHANGED LOCK; ~165+ ZERO Co-Authored-By footer drift streak preserved. OUTPUT: tabular journal/Schwab comparison rendering on web + CLI surfaces; closes the LAST Phase 12.5 cleanup item before Phase 13 commission.*
