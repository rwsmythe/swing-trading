# Phase 13 T2.SB1 — T-A.1.5b Hotfix Dispatch Brief

**Audience:** Fresh Claude Code instance dispatched as the T-A.1.5b hotfix implementer. No prior conversation context.

**Mission:** Land a surgical hotfix on the T2.SB1 worktree branch closing 3 production defects + 1 workflow scaffolding gap surfaced when the T-A.1.7 operator-paired labeling session ABORTED at first persist. T-A.1.5b is a NEW task between T-A.1.5 / T-A.1.6 (already shipped) and T-A.1.7 (retry pending your closure). After T-A.1.5b ships + Codex/QA closes, the operator redispatches the T-A.1.7 paired-session retry.

**Brief:** `docs/phase13-t2-sb1-t-a-1-5b-hotfix-dispatch-brief.md` (THIS file; committed on the worktree branch).

**Scope envelope:** ~80-150 LOC production + ~120-200 LOC test + 1 helper-script-OR-CLI-fetch-wiring. ~2-3 Codex rounds expected.

---

## §0 Status at session start

- **Worktree:** `.worktrees/phase13-t2-sb1-dev-time-labeling-infra/` (you operate here).
- **Branch:** `phase13-t2-sb1-dev-time-labeling-infra` (HEAD `caa628f` = T-A.1.7 labeling briefing committed; previously `8cbb1a5` = T-A.1.6 SHIPPED).
- **Schema:** v20 (UNCHANGED — T-A.1.5b is application-layer hotfix only).
- **Baseline:** 5013 fast tests passing / 6 skipped / ruff 0 errors / ZERO Co-Authored-By footer drift across 11 worktree commits.
- **Branch base:** main HEAD `6383cfa` (pre-dispatch).
- **T-A.1.1 SHA (for T3.SB1 coordination; unchanged):** `4cfd5f2`. T3.SB1 is SHIPPED on a sibling worktree awaiting T2.SB1 merge per OQ-12 Option E.

The T-A.1.7 labeling session attempted SNAP 2020-07-01 → 2020-09-30 vcp + ABORTED at Step C persist when `sqlite3.ProgrammingError: type 'dict' is not supported` fired. Three production defects + one workflow scaffolding gap escalated for fix BEFORE the T-A.1.7 retry.

---

## §0.5 Skill posture

- Invoke **`copowers:executing-plans`** (wraps `superpowers:subagent-driven-development` + adversarial Codex review). Iterate to `NO_NEW_CRITICAL_MAJOR`. Expected 2-3 Codex rounds (smaller-scope hotfix than the original T2.SB1 chain).
- Use **`superpowers:test-driven-development`** per task. Discriminating tests use REAL-SHAPE subagent output (the tmp artifacts at `tmp/phase13-labeling/silver_1_SNAP_vcp.json` are production-shape captures and SHOULD become the test fixture).
- Pre-Codex orchestrator-side review per **C.C lesson #6 BINDING** before invoking `copowers:adversarial-critic` at each round. This is the 15th cumulative validation expected (14x precedent CLEAN).

---

## §1 The 3 defects + 1 scaffolding gap

### §1.1 Defect 1 (BLOCKER) — CLI dict→str shape drift

**Root cause:** `_SilverLabelResponse.structural_evidence_json` is typed `str` at `swing/patterns/labeling.py:67` (comment says "serialized JSON dict"), but the subagent's documented output contract at `.claude/agents/pattern-labeler.md:28` emits a **JSON OBJECT** (dict), not a string-in-a-string. The CLI at `swing/cli.py:3826-3833` calls `json.loads(...)` on the response file then passes the dict value at `["structural_evidence_json"]` DIRECTLY into the dataclass without re-serializing. The downstream repo INSERT at `swing/data/repos/pattern_exemplars.py` then raises `sqlite3.ProgrammingError: type 'dict' is not supported`.

**Test fixture masks the bug:** `tests/cli/test_patterns_label_exemplars_cli.py:50, 160` writes the fixture with `"structural_evidence_json": json.dumps({...})` — a pre-serialized string-in-a-string. The fixture shape DIVERGES from the subagent's documented contract. Canonical "synthetic-fixture-vs-production-emitter shape drift" gotcha family (CLAUDE.md; Phase 12 C.D 2026-05-17; T1.SB0 gate-fix byte-parity 2026-05-19). THIRD instance in two days.

**Fix (BINDING; precise shape):**

At `swing/cli.py:3826-3834` (the response-file parse + dataclass construction block), coerce dict-or-string:

```python
response_raw = _json.loads(
    Path(silver_response_file).read_text(encoding="utf-8")
)
raw_evidence = response_raw["structural_evidence_json"]
if isinstance(raw_evidence, dict):
    raw_evidence = _json.dumps(raw_evidence, sort_keys=True)
# (Optional defense-in-depth: reject other types with a clear error;
#  dict and str are the two valid shapes per the subagent contract +
#  the existing test fixture convention.)
try:
    response = _SilverLabelResponse(
        evaluation=response_raw["evaluation"],
        confidence=response_raw["confidence"],
        structural_evidence_json=raw_evidence,
        geometric_evidence_narrative=(
            response_raw["geometric_evidence_narrative"]
        ),
    )
```

If `_SilverLabelResponse` has additional kwargs (e.g., `alternative_structural_evidence_json` is also typed `str`), apply the same coercion pattern to ANY field that mirrors the subagent's contract as a dict-or-string. Audit `swing/patterns/labeling.py` for every field that could carry a JSON object.

**Discriminating test (BINDING):**

Add a test to `tests/cli/test_patterns_label_exemplars_cli.py` that:

1. Writes a silver-response file with `"structural_evidence_json": {...as a dict, NOT json.dumps...}` matching the documented subagent contract verbatim. Use the captured artifact at `tmp/phase13-labeling/silver_1_SNAP_vcp.json` as the canonical real-shape fixture (copy/sanitize/commit to `tests/fixtures/pattern_labeler/` if persisted).
2. Invokes the CLI with `--silver-response-file` pointing at this dict-shaped file.
3. Asserts the persist succeeds (no `sqlite3.ProgrammingError`).
4. Reads the persisted row's `structural_evidence_json` column from `pattern_exemplars`.
5. Asserts `json.loads(row.structural_evidence_json)` returns the EXACT original dict (round-trip integrity).

The pre-fix code MUST raise on this test; the post-fix code MUST pass. Verify via temporary local revert.

### §1.2 Defect 2 (DESIGN GAP) — placeholder rule_criteria + structural_evidence_schema

**Root cause:** `swing/cli.py:3794-3810` emits placeholder rule_criteria + structural_evidence_schema:

```python
rule_criteria: dict = {
    "_note": (
        "Rule criteria placeholder; populated by T2.SB3+/SB4 "
        "detector module landings."
    ),
}
structural_evidence_schema: dict = {
    "_note": ...
}
```

The subagent (Read/Glob/Grep only, no compute) cannot enrich these from the dispatch payload itself. The operator-paired session has to manually paste spec §5.2-§5.6 criteria + structural-evidence schema for EACH candidate's payload, which is undocumented in the labeling briefing's per-candidate Step A.

**Fix (BINDING):**

Ship spec §5.2-§5.6 rule_criteria + structural_evidence_schema as **static module data inlined by the CLI emit path**. Create or extend a module (`swing/patterns/spec_static.py` is one candidate location; reuse an existing file in `swing/patterns/` if shape-appropriate). Encode the criteria + schema for each of the 5 V1 pattern classes:

- `vcp` — Volatility Contraction Pattern (spec §5.2)
- `flat_base` — Flat-base consolidation (spec §5.3)
- `cup_with_handle` — O'Neil cup-with-handle (spec §5.4)
- `high_tight_flag` — High-tight flag (spec §5.5)
- `double_bottom_w` — W-shaped double bottom (spec §5.6)

The exact content of each criteria set + schema comes from `docs/superpowers/specs/2026-05-18-phase13-charts-patterns-autofill-usability-design.md` §5.2-§5.6. Read each section verbatim + encode as Python data (dict or dataclass — your call; favor minimal additional surface). CLI `swing/cli.py` then dispatches the class-keyed lookup at emit time and inlines the resolved criteria + schema into the dispatch payload.

**Lock:** This is V1 PATCH scope only. Do NOT pre-empt the T2.SB3+/SB4 detector module landing — when those land, they MAY rebase the criteria/schema onto compute-derived defaults; T-A.1.5b ships static-encoded VERSION-1 data only.

**Discriminating tests (BINDING):**

Per-pattern-class test asserting the CLI emit's `rule_criteria` + `structural_evidence_schema` are non-placeholder + contain class-specific fields. E.g., for `vcp` the criteria MUST mention "contractions" + "pivot_price" + "prior_trend_pct" per spec §5.2. Use a parametrized test over the 5 V1 classes.

### §1.3 Defect 3 (DESIGN GAP) — bars optional / not auto-fetched

**Root cause:** `swing/cli.py:3781-3786` defaults bars to `[]` when `--window-bars-file` not provided; comment claims "the operator-paired session at T-A.1.7 wires real OhlcvCache fetch" — but no scaffolding ships to wire it. The subagent cannot label without real OHLCV.

**Fix options (implementer-pick; prefer Option B per operator's expressed preference):**

- **Option A** (simpler; require operator-side fetch): make `--window-bars-file` REQUIRED whenever `--silver-response-file` is NOT set (i.e., on the emit-payload path). Error message MUST direct the operator to the helper script in §1.4. ~3 LOC + error-path discriminating test.

- **Option B** (preferred; auto-fetch in CLI): wire `OhlcvCache.get_or_fetch(...)` (or `read_or_fetch_archive(...)` if the date-range shape is cleaner) at the CLI emit path so bars are populated automatically given `(ticker, start_date, end_date, timeframe)`. Operator can still override via `--window-bars-file` for fixture pinning. Behavior matches Phase 11 + T1.SB0 wiring discipline; respects sandbox short-circuit per spec §A.11. ~10-15 LOC + happy-path + sandbox-short-circuit + override-via-file discriminating tests.

**Option B recommendation rationale:** the original brief implied this shape ("real OhlcvCache fetch"); operator-paired session ergonomics improve significantly with auto-fetch; the helper script becomes optional rather than required. Adopt Option A only if Option B's coupling to OhlcvCache infrastructure raises scope concerns.

**Discriminating tests (BINDING regardless of option):**

- Option A: assert CLI emit raises a clear error when `--window-bars-file` absent + `--silver-response-file` absent (i.e., on the emit-payload path).
- Option B: assert CLI emit produces non-empty bars in the dispatch payload when given a real ticker + date range via mocked OhlcvCache; assert `--window-bars-file` override path still works; assert sandbox short-circuit produces a clear advisory + does not call Schwab.

### §1.4 Scaffolding gap — corpus-labeling helper script

**Root cause:** the aborted T-A.1.7 paired session had no per-candidate helper. Operator had to hand-build `tmp/phase13-labeling/SNAP_2020-07-01_2020-09-30_enriched_dispatch.json` after observing the CLI's placeholder rule_criteria + empty bars. T-A.1.5b should remove that friction.

**Fix (CONDITIONAL on §1.3 choice):**

- **If Option B (auto-fetch) lands at §1.3:** scaffolding script is OPTIONAL. The CLI emit becomes self-contained; the operator-paired session just invokes the CLI + receives a fully-populated dispatch payload. Skip §1.4 production work; instead, UPDATE `docs/phase13-t2-sb1-t-a-1-7-labeling-briefing.md` §1 Step A to reflect the auto-fetch behavior + remove any "manual enrichment" caveats. Optionally land a thin convenience wrapper script if it adds operator UX clarity.

- **If Option A (require --window-bars-file) lands at §1.3:** ship `scripts/phase13_t_a_1_7_labeling_helper.py` (or similar; mirror existing scripts/* naming) that runs per (ticker, start, end, pattern_class) tuple and produces:
  - `<ticker>_<start>_<end>_bars.json` — bars file matching CLI's expected shape, fetched via OhlcvCache / read_or_fetch_archive
  - `<ticker>_<start>_<end>_dispatch.json` — the full enriched dispatch payload ready for Step B subagent invocation
  
  Script honors `cfg.integrations.schwab.environment == 'sandbox'` short-circuit + `apply_overrides(cfg)` discipline. Read-only relative to swing.db; no DB writes from the script.

In EITHER case: update `docs/phase13-t2-sb1-t-a-1-7-labeling-briefing.md` §1 + §8 (Subagent invocation example) to reflect the new operator-paired workflow.

---

## §2 Task structure

### T-1.5b.1 — Defect 1 fix + discriminating test (BLOCKER)

Surgical coercion at `swing/cli.py:3826-3834`. Discriminating test using dict-shaped silver-response fixture from `tmp/phase13-labeling/silver_1_SNAP_vcp.json` (sanitize + commit as test fixture under `tests/fixtures/pattern_labeler/` if persistence is desired). Audit `swing/patterns/labeling.py` for additional `str` fields that mirror subagent dict-output (e.g., `alternative_structural_evidence_json`) and extend coercion symmetrically.

**Commit message:**
```
fix(phase13): T-A.1.5b - CLI dict-or-str coercion at structural_evidence_json (Defect 1)
```

### T-1.5b.2 — Defect 2 fix + per-class discriminating tests

Ship static spec §5.2-§5.6 rule_criteria + structural_evidence_schema for all 5 V1 classes. CLI emit dispatches class-keyed lookup. Parametrized test over all 5 classes asserts non-placeholder shape + class-specific fields.

**Commit message:**
```
feat(phase13): T-A.1.5b - inline spec section 5.2 through 5.6 rule_criteria + structural_evidence_schema (Defect 2)
```

### T-1.5b.3 — Defect 3 fix + discriminating tests

Implementer chooses Option A or B per §1.3. Recommend Option B. Discriminating tests per option (emit-path error vs auto-fetch behavior).

**Commit message (Option B):**
```
feat(phase13): T-A.1.5b - auto-fetch bars via OhlcvCache at CLI emit path (Defect 3 Option B)
```

**Commit message (Option A):**
```
feat(phase13): T-A.1.5b - require --window-bars-file on emit path (Defect 3 Option A)
```

### T-1.5b.4 — Scaffolding + briefing update

Per §1.4: either ship the helper script (Option A path) OR update the labeling briefing to reflect auto-fetch (Option B path). Always update briefing §1 Step A + §8 to reflect actual workflow.

**Commit message:**
```
docs(phase13): T-A.1.5b - labeling briefing refresh + helper scaffolding (post-Defect-3 fix)
```

### T-1.5b.5 — Closer (ruff sweep + cross-bundle pin audit + post-fix verification)

Full-suite verification: pytest fast (expect 5013 baseline + N tests added across T-1.5b.1..T-1.5b.4) + ruff 0 errors on `swing/`. No new cross-bundle pins land at T-A.1.5b (cross-bundle pin schedule is unaffected).

**Commit message:**
```
test(phase13): T-A.1.5b closer - full-suite verification + ruff sweep
```

---

## §3 Inherited LOCKS + DROPS

- **Schema v20 UNCHANGED.** Hotfix is application-layer only. Migration 0020 stays as-is.
- **Subagent definition `.claude/agents/pattern-labeler.md` UNCHANGED.** The subagent is correct; the CLI is what mis-handles the contract. If you find yourself wanting to change the subagent contract, STOP — that's the WRONG direction.
- **Web routes (T-A.1.6 surface) UNCHANGED.** `/patterns/exemplars` works fine; this hotfix is upstream of the web surface.
- **Repo modules (T-A.1.1b) UNCHANGED.** `swing/data/repos/pattern_exemplars.py` is correctly typed for `str`; the CLI must produce strings, not change the column type.
- **§A.14 LOCK preserved.** No constants move.
- **§A.15 LOCK preserved.** No `INSERT OR REPLACE` introduced.
- **§B.6 escalation rule.** NO new schema beyond plan §G.1 + spec §3. STOP + escalate if you find yourself needing a new column.
- **L1 LOCK preserved.** Subagent is DEV-TIME ONLY; no run-time AI inferencing introduced.
- **T-A.1.7 retry waits.** Do NOT proceed past T-1.5b.5; the T-A.1.7 paired session retries AFTER your closure + orchestrator QA + Codex chain.

---

## §4 Adversarial review watch items

1. **Defect 1 fix is sufficient:** does the dict-or-string coercion handle EVERY field in `_SilverLabelResponse` that the subagent contract emits as a dict? Audit each field.
2. **Defect 1 discriminating test FAILS pre-fix:** verify by temporary local revert that the dict-shaped fixture causes `sqlite3.ProgrammingError` pre-fix.
3. **Test fixture provenance:** the production-shape fixture should derive from `tmp/phase13-labeling/silver_1_SNAP_vcp.json` (or a clean re-capture); document the provenance inline in the test file.
4. **Existing pre-serialized test fixtures stay green:** the `json.dumps({...})` pattern at `tests/cli/test_patterns_label_exemplars_cli.py:50, 160` continues to pass — coercion is dict-OR-string, not dict-only.
5. **Defect 2 spec source verified:** rule_criteria + structural_evidence_schema match spec §5.2-§5.6 VERBATIM per pattern class. Cite section number in test docstring per class.
6. **Defect 2 all 5 V1 classes covered:** parametrized test enumerates all 5 (`vcp` + `flat_base` + `cup_with_handle` + `high_tight_flag` + `double_bottom_w`).
7. **Defect 3 Option B (preferred): sandbox short-circuit honored.** Auto-fetch under `environment='sandbox'` does NOT call Schwab API; emits clear advisory in payload OR raises a sandbox-suitable error.
8. **Defect 3 Option B: `--window-bars-file` override still works.** Operator can still pin a specific bars file (for fixture-pinned reproducibility) without the auto-fetch firing.
9. **Defect 3 Option A: error message directs operator.** If Option A chosen, the missing-`--window-bars-file` error MUST direct the operator to the helper script.
10. **Scaffolding helper (Option A path): script is read-only.** No DB writes from the helper. ASCII-only stdout.
11. **Labeling briefing updated.** `docs/phase13-t2-sb1-t-a-1-7-labeling-briefing.md` §1 Step A + §8 Subagent invocation example reflect the actual post-fix workflow (auto-fetch OR required-bars-file).
12. **No subagent contract changes.** Subagent definition `.claude/agents/pattern-labeler.md` UNTOUCHED.
13. **No schema changes.** v20 UNCHANGED.
14. **Test fixture round-trip integrity.** `json.loads(persisted_row.structural_evidence_json) == original_dict` exact equality after CLI persist.
15. **ASCII-only on CLI output.** Windows cp1252 stdout discipline preserved.
16. **ZERO Co-Authored-By footer trailer drift.** ~219+ cumulative streak.
17. **Implementer self-report accuracy gate.** Return report cites file:line evidence + test counts pre/post + commit SHAs verbatim.
18. **Pre-Codex orchestrator-side review at every Codex round (C.C lesson #6 BINDING).** 15th cumulative validation expected.

---

## §5 Done criteria

1. Branch `phase13-t2-sb1-dev-time-labeling-infra`; 5 task-commits (T-1.5b.1 through T-1.5b.5) + optional Codex-fix commits + 1 return report commit.
2. 5 tasks T-1.5b.1..T-1.5b.5 executed per §2 verbatim.
3. ≥2 Codex rounds → NO_NEW_CRITICAL_MAJOR (2-3 rounds expected for hotfix scope).
4. Defect 1 fix verified: dict-shaped fixture + persist + round-trip integrity test PASSES post-fix.
5. Defect 2 fix verified: all 5 V1 pattern classes have non-placeholder rule_criteria + structural_evidence_schema; parametrized test passes.
6. Defect 3 fix verified: per chosen option (A or B); discriminating tests pass.
7. Scaffolding gap closed per §1.4 chosen path.
8. Labeling briefing updated to reflect actual post-fix workflow.
9. Operator-witnessed gate: S1 inline pytest+ruff PASS via implementer; baseline 5013 → ~5018-5030 post-fix.
10. Return report at `docs/phase13-t2-sb1-t-a-1-5b-return-report.md` per §6.
11. ZERO Co-Authored-By footer trailer drift across all commits.

---

## §6 Return report format

```
## Return report — Phase 13 T2.SB1 T-A.1.5b

### Sub-bundle location
Worktree branch: `phase13-t2-sb1-dev-time-labeling-infra` at `.worktrees/phase13-t2-sb1-dev-time-labeling-infra/`
Commits on branch (per task; verbatim plan-provided commit messages):
- {sha} T-1.5b.1 — Defect 1 fix + discriminating test
- {sha} T-1.5b.2 — Defect 2 fix + per-class discriminating tests
- {sha} T-1.5b.3 — Defect 3 fix + discriminating tests (Option {A|B})
- {sha} T-1.5b.4 — Scaffolding + briefing update
- {sha} T-1.5b.5 — Closer (ruff + verification)
- (optional) {sha} Codex R<N> fix bundles
- {sha} Return report

### Codex review history
- Pre-Codex (C.C lesson #6 BINDING): {N findings absorbed; 15th cumulative validation}
- R1..RN: ... (2-3 rounds expected)
- Final verdict: NO_NEW_CRITICAL_MAJOR

### Defect closure verification
- Defect 1 (dict→str): {file:line of fix}; discriminating test at {file:line}; pre-fix revert verification confirmed.
- Defect 2 (placeholder criteria/schema): static module at {file}; all 5 V1 classes covered; per-class tests pass.
- Defect 3 ({A|B}): {file:line of fix}; discriminating tests pass; sandbox short-circuit verified (Option B path).
- Scaffolding gap: {helper script path OR briefing update path}.

### Test count pre/post
- Pre-baseline (T-A.1.7 briefing `caa628f`): 5013 fast
- Post-T-A.1.5b: {fast count} (delta: +{N}; within +5-15 projection)

### Operator-witnessed gate results
- S1 (inline pytest+ruff): PASS/FAIL
- T-A.1.7 retry: PENDING (operator will redispatch the paired session post-T-A.1.5b-closure)

### Forward-binding lessons for downstream sub-bundles
### Capture-needs for next sub-bundle dispatch (T-A.1.7 retry + T-A.1.8 closer)
### Outstanding capture-needs that DEFER
```

---

## §7 If you get stuck

- If the dict-or-string coercion breaks ANY existing test, STOP — backward-compat is BINDING.
- If a `_SilverLabelResponse` field beyond `structural_evidence_json` mirrors the subagent's dict-output and needs coercion, surface it in the return report.
- If spec §5.2-§5.6 rule_criteria or structural_evidence_schema content is ambiguous or contradictory between sections, STOP + escalate to orchestrator (do NOT invent).
- If Option B (auto-fetch) reveals an OhlcvCache contract mismatch (date-range vs window_days shape), prefer using `swing/data/ohlcv_archive.py:read_or_fetch_archive` directly + slicing by date range, mirroring `_bars_hook` patterns established at T1.SB0 gate-fix.
- If Codex review surfaces a SCHEMA need beyond v20, STOP — §B.6 escalation rule.
- If you find yourself wanting to change `.claude/agents/pattern-labeler.md`, STOP — subagent is correct; CLI is what needs the fix.
- If a test fixture refactor would touch >2 files outside the hotfix scope, STOP + escalate.

---

## §8 Artifacts available for fixture provenance

The aborted T-A.1.7 session left captured artifacts in the worktree at `tmp/phase13-labeling/`:

- `SNAP_2020-07-01_2020-09-30_bars.json` — real OHLCV bars file (Schwab + yfinance ladder + archive)
- `SNAP_2020-07-01_2020-09-30_payload.json` — original CLI emit (with placeholder rule_criteria + empty bars; shows what V1 ships)
- `SNAP_2020-07-01_2020-09-30_enriched_dispatch.json` — manually enriched dispatch payload (operator's workaround; useful as Option-B-auto-fetch reference shape)
- `silver_1_SNAP_vcp.json` — real-shape subagent response (dict-shaped `structural_evidence_json` matching the documented contract verbatim)

These artifacts are gold for fixture provenance. Use `silver_1_SNAP_vcp.json` (sanitized as needed) as the canonical real-shape fixture for the Defect 1 discriminating test. Commit sanitized fixtures under `tests/fixtures/pattern_labeler/` if persisted.

---

*End of brief. Phase 13 T2.SB1 T-A.1.5b hotfix dispatch. 5 tasks T-1.5b.1..T-1.5b.5 closing 3 production defects + 1 scaffolding gap. Branch `phase13-t2-sb1-dev-time-labeling-infra` HEAD `caa628f`. Expected 2-3 Codex rounds. ZERO ACCEPT-WITH-RATIONALE preferred. Pre-Codex orchestrator-side review BINDING per C.C lesson #6 (15th cumulative validation). After T-A.1.5b closes, operator redispatches the T-A.1.7 paired-session retry.*
