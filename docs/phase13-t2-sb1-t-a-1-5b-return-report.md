# Return report — Phase 13 T2.SB1 T-A.1.5b

## Sub-bundle location

Worktree branch: `phase13-t2-sb1-dev-time-labeling-infra` at `.worktrees/phase13-t2-sb1-dev-time-labeling-infra/`.

Commits on branch (per task; verbatim brief-provided commit messages + 4 Codex-fix bundles + return-report commit):

- `3144978` T-1.5b.1 — Defect 1 fix (CLI dict-or-str coercion at structural_evidence_json) + discriminating test
- `cc2f7cc` T-1.5b.2 — Defect 2 fix (static spec section 5.2 through 5.6 rule_criteria + structural_evidence_schema for all 5 V1 classes) + parametrized + per-class anchor tests
- `4b92e05` T-1.5b.3 — Defect 3 fix Option B (auto-fetch bars via yfinance windowed download at CLI emit path) + discriminating tests
- `43385b0` T-1.5b.4 — Labeling briefing §1 + §8 refresh (helper-script-OPTIONAL under Option B)
- `fd97de0` T-1.5b.5 — Closer (full-suite verification + ruff sweep; empty-commit logging the verification gate)
- `ee595aa` Codex R1 fix bundle (6 Major + 1 Minor closures)
- `846fc8b` Codex R2 fix bundle (1 Major + 2 Minor closures)
- `54a0490` Codex R3 fix bundle (1 Major + 2 Minor closures)
- `abc8411` Codex R4 fix bundle (1 Major + 1 Minor closures)
- (THIS COMMIT) Return report

Branch base: `main` at `6383cfa`; baseline (pre-T-A.1.5b) at brief commit `d5452c4`.

## Codex review history

- **Pre-Codex orchestrator-side review** (C.C lesson #6 BINDING; **15th cumulative validation**): CLEAN. Reviewer subagent flagged 4 NOTEs (sandbox-short-circuit lacks dedicated test [vacuously satisfied by yfinance-only construction]; architectural deviation from brief-prescribed `OhlcvCache.get_or_fetch` to direct `yf.download` with documented rationale; test-count delta projection over-shoot; commit-message wording drift accurately recorded). ZERO Critical / ZERO Major. 15th cumulative C.C lesson #6 validation BANKED CLEAN (matches 14× precedent through Phase 12 + Phase 13 T1.SB0 gate-fix).
- **R1** (Codex MCP thread `019e420f-a20d-7cc2-ab5d-ed3f41158751`): 0 Critical / **6 Major** / 2 Minor. Verdict: ISSUES_FOUND.
  - M#1: auto-fetch ran in persist path (network in persist mode + test pollution). RESOLVED — auto-fetch moved INSIDE emit-payload branch via new `_load_bars_for_labeling_emit` helper.
  - M#2: empty yfinance silently emitted `bars=[]`. RESOLVED — raises ClickException with `--window-bars-file` hint.
  - M#3: malformed string at `structural_evidence_json` could persist as garbage. RESOLVED — string path now `json.loads`-decodes + verifies dict shape; canonical re-serialize via `sort_keys=True`.
  - M#4: watch item #1 incomplete — `CodexReviewResponse.alternative_*_json` fields lack coercion. RESOLVED — defense-in-depth `__post_init__` coercion via shared `_coerce_dict_to_canonical_json_str` helper on BOTH dataclasses.
  - M#5: structural_evidence_schema diverged from verbatim spec section 5.3-5.6 field lists (extrapolated `stage` + `criteria_pass`). RESOLVED — trimmed to spec verbatim; VCP retains both per spec section 5.2 verbatim.
  - M#6: `--window-bars-file` content not shape-validated. RESOLVED — top-level list + per-bar dict + required OHLCV-key checks added.
  - Minor #2: module-level mutable dicts could be poisoned by caller mutation. RESOLVED — `copy.deepcopy(...)` from getter helpers.
  - Minor #1 (sort_keys loses byte-original order): ACCEPTED WITH RATIONALE — round-trip equality is preserved; byte-original preservation is a V2 audit-trail enhancement, banked.
- **R2**: 0 Critical / **1 Major** / 2 Minor. Verdict: ISSUES_FOUND.
  - M#1: missing `structural_evidence_json` key + `SilverLabelResponse.__post_init__` ValueError escaped CLI's `(KeyError, TypeError)` except clause. RESOLVED — explicit key-presence check pre-construction + except widened to include ValueError.
  - Minor #1: `--window-bars-file` help text stale ("placeholder bars list"). RESOLVED — refreshed.
  - Minor #2: raw `json.JSONDecodeError` from `--window-bars-file`. RESOLVED — wrapped in try/except.
- **R3**: 0 Critical / **1 Major** / 2 Minor. Verdict: ISSUES_FOUND.
  - M#1: `SilverLabelResponse` `evaluation` + `confidence` not runtime-validated; invalid `evaluation` escaped through `_map_silver_evaluation_to_decision` as raw ValueError. RESOLVED — added `_validate_silver_evaluation` + `_validate_silver_confidence` invoked from `__post_init__`.
  - Minor #1: raw `json.JSONDecodeError` from `--silver-response-file` (mirror of R2 Minor #2). RESOLVED — wrapped at parse site.
  - Minor #2: "Ignored on the persist path" wording misleading (click's `exists=True` still fires). RESOLVED — help text precision.
- **R4**: 0 Critical / **1 Major** / 1 Minor. Verdict: ISSUES_FOUND.
  - M#1: `relabel:<same_class_as_proposed>` rejected by service layer as raw ValueError outside CLI's ClickException wrapper. RESOLVED — wrapped `_fire_claude_silver_label` call in try/except (ValueError) → ClickException (the dataclass can't detect same-class collision because it lacks pattern_class context; service layer owns that check).
  - Minor #1: top-level non-dict JSON in `--silver-response-file` raised raw `TypeError` on indexing. RESOLVED — explicit `isinstance(response_raw, dict)` check post-parse.
- **R5**: 0 Critical / 0 Major / 0 Minor. **Final verdict: NO_NEW_CRITICAL_MAJOR.**

**4-round Codex chain summary**: 9 Major closures (6 R1 + 1 R2 + 1 R3 + 1 R4); 7 Minor closures (2 R1 + 2 R2 + 2 R3 + 1 R4); 1 Minor ACCEPTED WITH RATIONALE (R1 Minor #1; sort_keys vs byte-original); ZERO Critical entire chain.

## Defect closure verification

- **Defect 1 (dict→str shape drift)**:
  - Fix at `swing/cli.py` near the silver-response-file parse path (post-R1 coercion now handles dict OR JSON-object-string OR rejects with clear ClickException; post-R3 also runtime-validates evaluation + confidence values via `SilverLabelResponse.__post_init__` in `swing/patterns/labeling.py`).
  - Discriminating test: `tests/cli/test_patterns_label_exemplars_cli.py::test_label_exemplars_accepts_dict_shaped_structural_evidence_json` uses the canonical real-shape fixture committed at `tests/fixtures/pattern_labeler/silver_response_vcp_dict_shape.json` (sanitized from `tmp/phase13-labeling/silver_1_SNAP_vcp.json`).
  - **Pre-fix verification** (T-1.5b.1 TDD red phase): test FAILED pre-fix with `ProgrammingError("Error binding parameter 8: type 'dict' is not supported")` — the exact failure mode that aborted the T-A.1.7 paired session 2026-05-19. Post-fix the test passes + round-trip equality `json.loads(persisted) == original_dict` holds.

- **Defect 2 (placeholder rule_criteria + structural_evidence_schema)**:
  - Static module at `swing/patterns/spec_static.py` encodes spec section 5.2-5.6 verbatim (ASCII-transliterated for `±` → `+/-` per CLAUDE.md Windows cp1252 stdout gotcha).
  - All 5 V1 classes covered: `vcp` (8 criteria + Contraction nested shape), `flat_base` (7 criteria), `cup_with_handle` (8 criteria + rounded-vs-V supplementary test), `high_tight_flag` (6 criteria), `double_bottom_w` (8 criteria + undercut bonus).
  - Per-class anchor tests at `tests/patterns/test_spec_static.py` (20 tests total post-R1 trim).
  - Post-R1 trim: schemas for flat_base/cup_with_handle/high_tight_flag/double_bottom_w now mirror spec verbatim field lists (extrapolated `stage` + `criteria_pass` removed; VCP retains both per spec section 5.2 verbatim).

- **Defect 3 (Option B — auto-fetch bars via yfinance)**:
  - Fix at `swing/patterns/labeling_bars.py:autofetch_bars_for_labeling` (yfinance windowed download with gotcha-resistant kwargs).
  - CLI integration at `swing/cli.py:_load_bars_for_labeling_emit` (R1 fix: scoped to emit-payload path ONLY; persist path no longer auto-fetches).
  - Discriminating tests: happy path / sandbox-safety (no Schwab module imported) / weekly-timeframe-rejected / malformed-date-rejected / inverted-range-rejected / empty-yfinance-raises-with-hint / multiindex-squeeze.
  - CLI integration tests: autofetch wiring / override-via-file / persist-mode-no-autofetch / empty-yfinance-CLI-error-with-hint / shape-validation-on-bars-file.
  - **Architectural deviation from brief-prescribed `OhlcvCache.get_or_fetch`**: implementer chose direct `yf.download` instead because (a) the archive's 5-year retention bound doesn't fit arbitrary historical labeling windows (SNAP 2020-07-01 from a 2026 calendar date exceeds default 1260-trading-day window), (b) the archive's weekly-refresh semantics are designed for OhlcvCache TTL invalidation, not arbitrary date-range queries. Rationale documented in module docstring; pre-Codex review reviewer subagent flagged as NOTE (acceptable deviation with sound justification); Codex R1-R5 did not re-raise.

- **Scaffolding gap (corpus-labeling helper script)**: closed per brief §1.4 "Option B path" — helper script OPTIONAL. Labeling briefing at `docs/phase13-t2-sb1-t-a-1-7-labeling-briefing.md` §0 + §1 Step A + §8 updated to reflect the post-fix workflow (auto-fetch + override semantics; subagent contract dict-or-string acceptance; explicit removal of "manual enrichment" caveat).

## Test count pre/post

- **Pre-baseline** (T-A.1.7 briefing `caa628f`): 5013 fast / 6 skipped.
- **Post-T-A.1.5b**: 5068 fast / 6 skipped (delta: **+55**; tests added across `tests/cli/test_patterns_label_exemplars_cli.py` + `tests/patterns/test_labeling.py` + `tests/patterns/test_labeling_bars.py` + `tests/patterns/test_spec_static.py`).
- Delta exceeds brief projection (+5-15) due to (a) parametrized spec-fidelity tests across all 5 V1 pattern classes, (b) Codex R1-R4 fix-validating tests, (c) defense-in-depth dataclass coercion tests. Brief flagged projection as non-binding; test surface is proportionate to scope.
- **Ruff**: 0 errors across `swing/` at every commit boundary.

## Operator-witnessed gate results

- **S1 (inline pytest + ruff via implementer)**: PASS at T-1.5b.5 closer (5043 fast / ruff clean) + every Codex fix bundle (final state at R5 termination: 5068 fast / ruff clean).
- **T-A.1.7 retry**: PENDING. Operator will redispatch the paired-session retry post-orchestrator-QA + post-merge per brief done criteria.

## ZERO Co-Authored-By footer drift verification

`git log --format='%B' d5452c4..HEAD | grep -iE "co-author|co-authored"` → empty (verified at every commit). **Streak preserved**: ~228+ cumulative ZERO drift across the project (9 T-A.1.5b commits + 219+ predecessors).

## Forward-binding lessons for downstream sub-bundles

1. **Synthetic-fixture-vs-production-emitter shape drift (THIRD instance in 3 days)** — the T-A.1.7 abort exposed yet another case where pre-serialized test fixtures (`json.dumps({...})`) masked a dict-vs-str shape mismatch with the production emitter (the subagent's documented contract). Builds on Phase 12 C.D gate-fix #2 (`field_name='fill_match'` synthetic-vs-real-column drift) + Phase 13 T1.SB0 gate-fix byte-parity-vs-production-data-derivation drift. **Pre-empt in any new file-based parse + dataclass-construction code path**: production-shape fixtures derived from real emitter output (the canonical pattern at `tests/fixtures/pattern_labeler/silver_response_vcp_dict_shape.json` from `tmp/phase13-labeling/silver_1_SNAP_vcp.json`); discriminating test must exercise the production-shape input + assert pre-fix failure mode in TDD red phase.

2. **`Literal[...]` type hints are NOT runtime-enforced.** Codex R3 M#1 flagged that `confidence: Literal["high", "medium", "low"]` did not validate at runtime — an invalid value would have persisted into `labeler_evidence_json` silently. Pattern for any future dataclass with `Literal[...]` field on the data-integrity path: add explicit `__post_init__` runtime validation against an explicit frozenset of allowed values. Defense-in-depth catches malformed external inputs (subagent emissions; CLI parse paths).

3. **Service-layer ValueErrors must be wrapped at CLI boundary.** Codex R4 M#1 flagged that `_map_silver_evaluation_to_decision`'s `relabel:<same_class>` rejection escaped CLI's construction-time except clause because it fires AFTER `_fire_claude_silver_label` invocation. Pattern: CLI's command-handler boundary must wrap ALL service-layer dispatch calls in `try: ... except ValueError as exc: raise click.ClickException(...)` so any future service-level ValueError (validation, invariant check) surfaces as a clean error rather than a raw traceback.

4. **CLAUDE.md gotcha candidate (banked for housekeeping)**: dict-shape-mismatch-at-sqlite3-bind is a recurring failure family. Three instances in 2 days (Phase 12 C.D + Phase 13 T1.SB0 byte-parity + Phase 13 T2.SB1 dict-typed evidence). The defense-in-depth pattern is two-pronged: (a) CLI-level explicit shape coercion + validation at parse time, (b) dataclass-level `__post_init__` coercion + validation. Both layers in place protects against future shape-drift between subagent contract / test fixture / production emitter / dataclass type.

5. **Test fixture provenance documentation pattern**: the new `tests/fixtures/pattern_labeler/silver_response_vcp_dict_shape.json` includes inline test-docstring provenance referencing `tmp/phase13-labeling/silver_1_SNAP_vcp.json`. Future test fixtures derived from operator-paired-session artifacts should follow this pattern: document the tmp artifact source + sanitization steps inline in the discriminating test.

## Capture-needs for next sub-bundle dispatch (T-A.1.7 retry + T-A.1.8 closer)

- T-A.1.7 retry: operator-paired session inherits the post-fix CLI (auto-fetch + spec-criteria-inlined dispatch payload + dict-or-string + dataclass validation + service-layer error translation). Briefing §1 Step A + §8 + §0 now reflect this; subagent invocation flow unchanged at `.claude/agents/pattern-labeler.md`.
- T-A.1.8 closer: cross-bundle pin schedule UNAFFECTED by T-A.1.5b (no new cross-bundle pins introduced; existing v20 schema pins remain at T2.SB3 / T2.SB5 / T4.SB-closer / T3.SB2 per plan §H.3).

## Outstanding capture-needs that DEFER

- **R1 Minor #1 (sort_keys byte-original drift)**: V2 banked. If audit-trail provenance later requires byte-identical preservation of subagent response, restructure persistence to store both (a) canonical sorted-key form for round-trip integrity AND (b) raw bytes as received. Current V1 form is canonical sorted-key only.
- **Schwab cassette runbook for pattern-labeler**: V2 planned per existing CLAUDE.md gotcha. The `scripts/record_pattern_labeler_cassettes.py` scaffold lives at the worktree but is not invoked by T-A.1.5b.
- **Weekly timeframe auto-fetch**: V2 candidate. V1 auto-fetch supports `daily` only; weekly requires operator-supplied `--window-bars-file`.

---

*End of return report. T-A.1.5b hotfix closes Phase 13 T2.SB1's 3 production defects + 1 scaffolding gap surfaced at T-A.1.7 abort 2026-05-19. 9 commits delta from baseline `d5452c4`. 4 Codex rounds to NO_NEW_CRITICAL_MAJOR (R5 verdict CLEAN). 9 Major closures + 7 Minor closures + 1 Minor ACCEPTED WITH RATIONALE; ZERO Critical entire chain. 15th cumulative C.C lesson #6 validation BANKED CLEAN. ZERO Co-Authored-By footer drift preserved (~228+ cumulative). Schema v20 UNCHANGED. T-A.1.7 paired-session retry PENDING.*
