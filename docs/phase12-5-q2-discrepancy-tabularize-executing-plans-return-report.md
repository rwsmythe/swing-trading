# Phase 12.5 Q2 — Discrepancy resolution comparison tabularize (web + CLI) — Executing-plans return report

**Dispatch:** `docs/phase12-5-q2-discrepancy-tabularize-dispatch-brief.md` (brief plays plan-role).
**Branch:** `phase12-5-q2-discrepancy-tabularize` (worktree).
**Baseline SHA:** `50cf1b593e3a573b8b8fa7fc49c33279d0b91f88` (`50cf1b5` — dispatch brief commit).
**Final HEAD:** TBD post-final-commit (this report + Codex R3 minor inline comment).
**Date:** 2026-05-18.

---

## 1. Final HEAD + commit breakdown

| # | SHA | Stem |
|---|-----|------|
| 1 | `1f1596a` | feat(trades): T-Q2.1 — NEW `reconciliation_render.py` ASCII table helper |
| 2 | `afb3220` | feat(trades): T-Q2.2 Part A — `build_compared_pairs` dispatch + 8 per-type extractors |
| 3 | `b6a843b` | test(web): T-Q2.2 Part B — failing tests for `compared_pairs` field |
| 4 | `58ac806` | feat(web): T-Q2.2 Part B — `compared_pairs` field on `ReconcilePreResolutionContext` |
| 5 | `1785f0c` | feat(web/template): T-Q2.3 — `<table>` render + CSS in `app.css` |
| 6 | `8e89bfe` | feat(cli): T-Q2.4 — `show-ambiguity` renders ASCII journal/Schwab comparison table |
| 7 | `631b5fa` | fix(trades+web): pre-Codex fixes — equity_delta envelope shape, xdist-safe import audit, CSS hex-to-var |
| 8 | `3531407` | fix(trades+web+cli): Codex R1 fixes — envelope drift on stop_mismatch + position_qty_mismatch, empty-pairs placeholder, control-char sanitization |
| 9 | `679dff3` | fix(web): Codex R2 — unmatched_*_fill envelope shape drift (pre-existing Phase 12.5 #2 defect) |
| 10 | TBD | docs(phase12-5-q2): Codex R3 minor advisory comment + return report |

**Total:** 10 commits = 6 task-impl + 1 pre-Codex fix + 2 Codex-driven fix + 1 return report.

ZERO Co-Authored-By footer drift across all 10 commits (~175+ project-cumulative streak preserved).

## 2. Codex round chain

| Round | Critical | Major | Minor | Verdict | Notes |
|------:|---------:|------:|------:|---------|-------|
| pre-Codex | 0 | 1 (HIGH) | — | (orchestrator review) | equity_delta envelope drift surfaced + resolved at `631b5fa` |
| R1 | 0 | 4 | 2 | ISSUES_FOUND | tuple-vs-list, envelope drift on stop+qty, None-vs-empty semantics, subprocess scope; +control-char, +synthetic fixtures |
| R2 | 0 | 1 | 0 | ISSUES_FOUND | unmatched_*_fill envelope drift (pre-existing Phase 12.5 #2 defect) |
| R3 | 0 | 0 | 1 | NO_NEW_CRITICAL_MAJOR | snapshot_mismatch speculative shape advisory |

**Convergent shape:** monotonic Major taper 1→4→1→0 (counting pre-Codex Major), monotonic Critical 0→0→0→0. Sealed at R3 within the default MAX_ROUNDS=5 budget.

**ZERO Critical findings** entire chain.

**2 ACCEPT-WITH-RATIONALE banked on Majors** (both R1):
- R1 Major #1 — `compared_pairs` tuple vs list type (frozen-dataclass invariant); banked as V2.1 §VII.F amendment to brief §1.2 (update to `tuple[tuple[str, Any, Any], ...] | None`).
- R1 Major #4 — subprocess test scope (script-eval covers OS encoder; full E2E CLI testing requires ~150 LOC tmp-DB fixture plumbing for marginal coverage); banked as V2.1 §VII.F amendment to brief §A.4 (endorse script-eval as canonical pattern).

All remaining findings (4 Major + 3 Minor) resolved with code-content fixes.

## 3. Per-task delivery summary

### T-Q2.1 — `swing/trades/reconciliation_render.py` ASCII table helper

`render_journal_schwab_comparison_table_ascii(pairs, *, journal_label="Journal", schwab_label="Schwab") -> str` ships with cell sanitization (non-ASCII → `?`; control chars → space per R1 Minor #1) + truncation at 40 chars with `...` indicator + numeric `:.2f` for floats/Decimals + None → `-` placeholder. Defense-in-depth ASCII assertion at end. 14 initial tests + 4 added during R1/R2 fixes.

### T-Q2.2 — `build_compared_pairs` dispatch + VM `compared_pairs` field

8 per-type extractors in `swing/trades/reconciliation_render.py:build_compared_pairs` (entry/close_price + stop + position_qty + cash_movement + snapshot + equity_delta + sector_tamper); unmatched_*_fill explicitly return None (no comparable Schwab side). `ReconcilePreResolutionContext` gains 16th field `compared_pairs: tuple[tuple[str, Any, Any], ...] | None = None`. Dispatch uses `dataclasses.replace(ctx, compared_pairs=...)` AFTER per-type helper runs — single-point integration, no per-helper churn. Generic fallback leaves the field at None.

### T-Q2.3 — Web template HTML `<table>`

`swing/web/templates/reconcile_discrepancy_resolve.html.j2` renders `<table class="reconcile-comparison-table">` with `<th>Field</th><th>Journal</th><th>Schwab</th>` + ARIA label + None→`-` rendering ABOVE the existing `<dl class="context-pairs">`. After R1 fix: outer `is not none` gate + inner `length > 0` distinguishes empty-pairs placeholder rendering from "no tabular support" hidden. CSS rule added to `swing/web/static/app.css` using `var(--border-strong)` (no raw hex — passes theme anti-regression test).

### T-Q2.4 — CLI ASCII table

`swing/cli.py:discrepancy_show_ambiguity_cmd` imports both `build_compared_pairs` + `render_journal_schwab_comparison_table_ascii`. Renders table between disc detail header (after `created_at:`) and choice menu. Defensive JSON parsing + (KeyError, ValueError, TypeError) catch — mirrors web VM contract. After R1 fix: empty-pairs branch renders `(no comparison data)` placeholder; None branch hides entirely. Slow subprocess script-eval test validates OS encoder path (cp1252 safety).

### Pre-Codex + Codex R1+R2 fixes — production envelope shape drift family

Surfaced + resolved **4 distinct envelope-shape drift bugs** (all same CLAUDE.md "synthetic-fixture-vs-production-emitter shape drift" gotcha class):

1. **`equity_delta`** (pre-Codex): production writes `{"equity_dollars": X}` on both sides; old code read `{"journal", "source", "delta"}`. Fixed at `631b5fa`.
2. **`stop_mismatch`** (R1): production writes ASYMMETRIC `{"current_stop": X}` on expected, `{"stop_price": X}` on actual; old code assumed symmetric `{"stop_price"}`. Fixed at `3531407`.
3. **`position_qty_mismatch`** (R1): production writes `{"qty": X}`; old code assumed `{"quantity": X}`. Fixed at `3531407`.
4. **`unmatched_*_fill`** (R2): production writes `{"qty", "price", "action"}`; old code assumed `{"quantity", "price", "fill_datetime"}` (the `fill_datetime` key DID NOT EXIST in any envelope). Fixed at `679dff3`.

All 4 fixes also corrected the corresponding pre-existing Phase 12.5 #2 VM helper bugs (operational defects predating Q2; surfaced as Q2 widened the test coverage on these envelope paths). Each fix shipped with a discriminating production-shape test that pins the fix against re-introduction.

## 4. Codex Major findings ACCEPTED with rationale

| Round | Finding | Rationale |
|------:|---------|-----------|
| R1 #1 | `compared_pairs` typed `tuple[...] | None`, not brief's `list[...] | None` | `@dataclass(frozen=True)` invariant requires immutable sequence; mutable `list` breaks hashability. Matches existing project convention at `ReconcileDiscrepancyResolveVM.choices`. V2.1 §VII.F amendment banked for brief §1.2. |
| R1 #4 | Subprocess test is script-eval, not full CLI invocation | Script-eval exercises the same `sys.stdout.write` OS encoder path that `click.echo` uses. Renderer's ASCII-only guarantee means `click.echo(ascii_string)` cannot introduce non-ASCII bytes. Full E2E CLI testing with tmp DB would add ~150 LOC fixture plumbing for marginal coverage. Brief §A.4 acceptance criterion 6 explicitly permitted accept-with-rationale; V2.1 §VII.F amendment banked. |

## 5. V2 candidates banked

1. **CLI per-discrepancy-type pair extraction extensibility** — when a future dispatch lands `snapshot_mismatch` or `sector_tamper` producers, reconcile the speculative extractor shapes against the actual emitter (same pattern as the 4 drift fixes shipped here). Comment banked inline at `swing/trades/reconciliation_render.py` near `_pairs_snapshot_mismatch`.
2. **Empty-pairs placeholder is currently unreachable in production** — `build_compared_pairs` never returns `[]`; only `None` or `[(...)]`. The placeholder render path (`(no comparison data)`) exists for defense-in-depth + matches brief §4.2 watch-item semantics; will fire if a future extractor returns `[]`. V2 candidate: introduce an extractor that intentionally returns empty pairs for some "data-not-available" condition (e.g., schwab_mismatch with both sides None).
3. **Cell formatting refinements** — currently leaves raw types in pairs (floats render `5.2244`); web template doesn't apply `:.2f` filter. Brief V1 chose presentation-only; future polish could thread a Jinja `floatformat` filter for monetary cells.
4. **CLI full E2E subprocess test** — wire a tmp-DB fixture (~150 LOC) to spawn the actual `swing journal discrepancy show-ambiguity <id>` command path through Click; assert stdout bytes + exit code. Trade off the fixture plumbing complexity vs additional coverage value when stale-fixture risk surfaces.
5. **`snapshot_mismatch` + `sector_tamper` are speculative** — extractors exist but no production emitter writes these types. Bank V2.1 §VII.F amendment OR future-fix when emitter lands.

## 6. V2.1 §VII.F amendments banked

1. **Brief §1.2** — `compared_pairs` field type should be documented as `tuple[tuple[str, Any, Any], ...] | None` (frozen-dataclass invariant); list-typed wording in current brief is incompatible with `@dataclass(frozen=True)`.
2. **Brief §A.4 acceptance criterion 6** — endorse the script-eval pattern as the canonical cp1252 discriminating test form; full E2E CLI testing requires fixture plumbing disproportionate to marginal coverage value.
3. **Phase 12.5 #2 spec §7.1 — `equity_delta` envelope shape** — should document `{"equity_dollars": X}` on BOTH `expected` and `actual` (production emitter at `reconciliation.py:453-457` + `schwab_reconciliation.py:1119-1122`). Earlier spec described `{journal, source, delta}` shape which never matched production.
4. **Phase 12.5 #2 spec §7.1 — `stop_mismatch` envelope shape** — should document the ASYMMETRY: `expected={"current_stop": X}` (journal-side) but `actual={"stop_price": X}` (Schwab-side). Production emitter at `schwab_reconciliation.py:836-844`.
5. **Phase 12.5 #2 spec §7.1 — `position_qty_mismatch` envelope shape** — should document `{"qty": X}` symmetric (NOT `quantity`). Production emitter at `schwab_reconciliation.py:868-878`.
6. **Phase 12.5 #2 spec §7.1 — `unmatched_*_fill` envelope shape** — should document `expected={"qty", "price", "action"}` (NOT `{"quantity", "price", "fill_datetime"}`). Production emitter at `schwab_reconciliation.py:933-944` AND `:971-985` (two emit sites, same shape).

## 7. Forward-binding lessons for future dispatches

### L-Q2.1 — Pre-Codex orchestrator review catches envelope-shape drift cheaply

The pre-Codex review surfaced the `equity_delta` drift bug in <300 words; Codex R1+R2 then surfaced 3 MORE drift bugs of the same class (stop_mismatch / position_qty_mismatch / unmatched_*_fill). All 4 were pre-existing Phase 12.5 #2 defects (operational; classifier dispatch silently degraded to generic fallback). The lesson: when a new dispatch ADDS coverage to existing per-type rendering paths (Q2 added the `build_compared_pairs` extractors), GREP-verify EVERY extractor's envelope assumptions against the production emitter BEFORE the implementer ships. This is the same "synthetic-fixture-vs-production-emitter shape drift" CLAUDE.md gotcha applied at the orchestrator-brief level — orchestrator MUST embed a pre-flight emitter-grep checklist for every per-type extraction touched.

### L-Q2.2 — Drift-fix discriminating tests pin via emitter-snippet copy

Every drift fix shipped here includes a test that plants the EXACT production envelope shape (copied byte-for-byte from the emitter callsite, sanitized) + asserts the extractor produces the expected pair. The R2 fix also added a test pinning the OLD synthetic shape now ROUTES TO GENERIC FALLBACK (`test_unmatched_open_fill_with_old_synthetic_shape_falls_back_to_generic`). This double-pin discipline prevents future "helpful refactor" silent re-introduction. Pattern complement to the CLAUDE.md "synthetic-fixture-vs-production-emitter shape drift" gotcha.

### L-Q2.3 — `dataclass(frozen=True)` + sequence field invariant

Brief LOCKs that prescribe `list[...]` types for fields on a frozen dataclass are inherently inconsistent (frozen requires hashable; mutable list breaks hashable). Future briefs MUST default to `tuple[...]` for sequence fields on frozen dataclasses + explicitly note the type. Watch-item: when the brief author writes "the field is a list of pairs", verify against any existing dataclass convention in the touched module; project precedent at `ReconcileDiscrepancyResolveVM.choices: tuple[...] = ()` should be the default.

### L-Q2.4 — None vs empty-sequence semantics need disambiguation at template + CLI both

Brief watch-item §4.2 prescribed the None vs empty list semantic distinction; initial implementation collapsed both to "hidden" via truthy-check. The fix pattern: template uses `{% if X is not none %}{% if X|length > 0 %}<table>...</table>{% else %}<placeholder>{% endif %}{% endif %}`; CLI uses `if X is not None: if len(X) > 0: <table> else: <placeholder>`. Both paths need the same two-stage branching — implementer should always ship the placeholder branch even if currently unreachable, as a contract preservation discipline.

### L-Q2.5 — `_sanitize` for CLI output should also strip ASCII control characters

Initial sanitization only handled `ord >= 128` (non-ASCII). ASCII control chars (`\n`, `\r`, `\t`, `\x00-\x1F`, `\x7F`) satisfy `ord < 128` but can corrupt row alignment. Pattern: any string sanitizer destined for tabular rendering MUST replace BOTH non-ASCII AND ASCII control chars with safe substitutes. Add to project sanitization guideline; cite in future helper modules.

## 8. CLAUDE.md status-line refresh draft text

```
**Phase 12.5 Q2 (Discrepancy resolution comparison tabularize — web + CLI) SHIPPED 2026-05-18** at `<merge SHA>` (integration merge of `phase12-5-q2-discrepancy-tabularize` via `--no-ff`; 10 task-branch commits = 6 task-impl (T-Q2.1..T-Q2.4) + 1 pre-Codex fix + 2 Codex-driven fixes (R1+R2) + 1 return report; **3 Codex rounds → NO_NEW_CRITICAL_MAJOR** convergent monotonic Major taper (pre-Codex 0C/1M → R1 0C/4M/2m → R2 0C/1M/0m → R3 0C/0M/1m); **ZERO Critical findings** entire chain; **2 ACCEPT-WITH-RATIONALE banked** (R1 #1 tuple-vs-list frozen-dataclass invariant + R1 #4 subprocess test scope script-eval-vs-E2E-CLI); ZERO Co-Authored-By footer drift across all 10 commits (~175+ project-cumulative streak preserved). +70 fast tests (4854 → 4924 main HEAD post-merge); ruff E501 baseline 0 preserved; schema v19 UNCHANGED LOCK preserved. NEW `swing/trades/reconciliation_render.py` exports `render_journal_schwab_comparison_table_ascii` ASCII table helper + `build_compared_pairs` per-type pair extractor. `ReconcilePreResolutionContext` extended with 16th field `compared_pairs: tuple[tuple[str, Any, Any], ...] | None = None`. Web template + CLI both consume the SAME canonical builder (Option A: CLI does NOT cross-import from web). Surfaced + resolved **4 distinct envelope-shape drift bugs** (all pre-existing Phase 12.5 #2 defects; same CLAUDE.md "synthetic-fixture-vs-production-emitter shape drift" gotcha class): equity_delta (`{"equity_dollars"}` not `{journal,source,delta}`); stop_mismatch (ASYMMETRIC `{"current_stop"}/{"stop_price"}`); position_qty_mismatch (`{"qty"}` not `{"quantity"}`); unmatched_*_fill (`{"qty","price","action"}` not `{"quantity","price","fill_datetime"}`). 5 V2.1 §VII.F amendments banked for spec §7.1 envelope-shape documentation + 1 brief-text amendment (tuple-vs-list type). 5 NEW forward-binding lessons (L-Q2.1..L-Q2.5): pre-Codex emitter-grep checklist; drift-fix discriminating tests pin via emitter-snippet copy; frozen-dataclass + sequence-field invariant; None-vs-empty disambiguation at template + CLI both; `_sanitize` for CLI output must also strip ASCII control characters. Phase 13 dispatch UNBLOCKED post operator-witnessed gate (S1 inline pytest + ruff PASS at 4924; S2 web `/reconcile/discrepancy/{id}/resolve` table render; S3 CLI `swing journal discrepancy show-ambiguity` ASCII table; S4 round-trip consistency between web + CLI same-discrepancy-ID).
```

## 9. Schema impact

**Schema v19 UNCHANGED.** Verified via `git diff 50cf1b5..HEAD -- swing/data/migrations/` → empty diff. F1 LOCK preserved entire dispatch.

## 10. Test count delta + Ruff

- Baseline: **4854 fast pass + 1 skipped** on main HEAD (per brief §0.2).
- Final: **4924 fast pass + 1 skipped + 0 failed** on worktree HEAD (verified post-R2 fix; the new docs-only commit + R3 minor comment add zero test delta).
- Net: **+70 fast tests** (above projection +20-45; matches Phase 12.5 arc overshoot precedent — overshoot driven by discriminating production-shape regression tests for the 4 drift fixes).
- Slow tests: +1 new slow `test_show_ambiguity_subprocess_cp1252_safety` (script-eval form per R1 Major #4 accept-with-rationale).
- Ruff: 0 E501 violations (baseline 0 preserved per Phase 12.5 #3 T-3.6 acceptance LOCK; no new violations introduced).

## 11. Worktree teardown

- Branch `phase12-5-q2-discrepancy-tabularize` deleted post-merge (operator-paired post-merge).
- On-disk husk at `.worktrees/phase12-5-q2-discrepancy-tabularize/` matches cleanup-script regex `phase\d+[-_]` — operator-paired cleanup pass post-merge via `cleanup-locked-scratch-dirs.ps1 -DeregisterFirst`.

---

*End of Phase 12.5 Q2 executing-plans return report. Implementation: 6 task commits + 1 pre-Codex fix + 2 Codex-driven fixes (R1+R2) + 1 docs/comment commit = 10 commits total. Codex chain: 3 rounds → NO_NEW_CRITICAL_MAJOR. 2 ACCEPT-WITH-RATIONALE banked. ZERO Co-Authored-By footer drift. ZERO Critical findings. +70 fast tests / 4924 final. Schema v19 UNCHANGED LOCK preserved. Operator-witnessed gate (S1-S4) UNBLOCKED.*
