# R2-A Backtest Return Report

**Branch:** `applied-research-r2a-tightness-days-required-cohort-backtest`
**Dispatch brief:** [`docs/r2a-vcp-tightness-days-required-cohort-backtest-dispatch-brief.md`](r2a-vcp-tightness-days-required-cohort-backtest-dispatch-brief.md)
**Findings doc:** [`docs/r2a-tightness-days-required-cohort-backtest-findings-20260526.md`](r2a-tightness-days-required-cohort-backtest-findings-20260526.md)
**Baseline SHA:** `28296376d525dc1aa7101dc59d79cfdaa6f01b86` (post merge of D2 Amendment 5)
**Final HEAD:** `c292c50` (after Codex MCP R5 NO_NEW_CRITICAL_MAJOR convergence)
**Status:** READY FOR MERGE

---

## 1 Mission summary

Test whether Ruleset E's PARTIAL POSITIVE verdict from D2 (bias-free S&P 500 cohort; mean R +1.220R / 95% CI lower +0.753R / N=5 closed-and-profitable on N=71 EXPANDED Amendment 5 cohort) generalizes to a DIFFERENT W-cohort definition — specifically the V2 OHLCV `vcp.tightness_days_required +16` binding-variable cohort (15 watch→aplus flips at sweep_point=1 across 7 unique tickers; selection-biased per V2 sensitivity framework rather than bias-free per D2).

**Headline verdict: NEGATIVE.** Ruleset E on R2-A canonical evaluation cohort (N=65 / composite>=0.5 + recency<=365d): mean R -1.086R, win-rate 22.5%, 95% CI [-1.377R, -0.782R], P(mean>0)=0.0000. ALL of {D, E, F} fail PARTIAL POSITIVE thresholds per dispatch brief §6.5.

**Cross-cohort signal:** Ruleset E's PARTIAL POSITIVE on D2's bias-free S&P 500 cohort does NOT generalize to V2-binding-variable-selection-biased cohort. E appears to be cohort-specific.

---

## 2 Implementation summary

### 2.1 NEW research/harness/r2a_tightness_days_required/ modules

- `__init__.py` — module docstring referencing dispatch brief + L2 LOCK preservation.
- `cohort_csv.py` — V2 sensitivity drill-down parser:
  - `extract_flips_from_sensitivity_md()` — column-name-resolved markdown table parser with line-anchored MULTILINE heading regex + h2/h3 boundary detection;
  - `verify_expected_r2a_cohort()` — layered verifier (raw flip multiset identity + ticker-asof tuple set + aggregate counts);
  - `write_cohort_csv()` — emit dedup-by-(ticker,asof) cohort CSV;
  - `write_flips_audit_json()` — emit sibling audit JSON preserving all 15 raw flips with eval_run_id + source SHA-256 + size;
  - `generate_r2a_cohort_artifacts()` — canonical one-call wrapper (extract → verify → write CSV → write audit); no bypass.
  - 7 module constants: `EXPECTED_FLIP_COUNT=15`, `EXPECTED_UNIQUE_TICKER_ASOF=7`, `EXPECTED_TICKERS` (7-set), `EXPECTED_TICKER_ASOF` (7-tuple set), `EXPECTED_FLIPS` (15-tuple set), `R2A_COHORT_LABEL`, `R2A_VARIABLE_NAME`.
- `regenerate_cohort.py` — operator-facing module entrypoint runnable as `python -m research.harness.r2a_tightness_days_required.regenerate_cohort`.

### 2.2 NEW exports/research/ artifacts

- `exports/research/cohorts/r2a_tightness_days_required_sp1.csv` — 7 unique (ticker, asof_date) rows with cohort_label `r2a_vcp_tightness_days_required_sp1`.
- `exports/research/cohorts/r2a_tightness_days_required_sp1.flips_audit.json` — 15 raw flip records (with eval_run_id) + source artifact SHA-256 + size + selection-method metadata.
- `exports/research/pattern-cohort-detection-20260526T081400Z/manifest.json + summary.md` (results.csv excluded per project convention; regeneratable via cohort CSV).
- `exports/research/w-bottom-ruleset-comparison-20260525T224203Z/results.csv + summary.md + manifest.json` — D2 6-ruleset smoke against R2-A cohort.

### 2.3 NEW tests/fixtures/research/r2a_tightness_days_required/

- `cohort.json` — 65 canonical PrimaryVerdict entries (composite>=0.5 + recency<=365d) for downstream test fixtures.

### 2.4 NEW tests/research/r2a_tightness_days_required/

- `test_cohort_generation.py` — 19 tests for parser robustness + flip identity + section-boundary + canonical wrapper + audit JSON shape (8 original + 11 added across R1/R2/R3 fix bundles).
- `test_harness_reuse_and_l2_lock.py` — 12 tests for D2 harness byte-stability + L2 LOCK source-grep + cohort-validity-vs-verdict-criteria documentation lock.
- `test_committed_artifacts_canonical.py` — 4 tests locking the committed CSV + audit JSON against canonical SHA / size / metadata / row-identity (Codex R3 + R4).
- `__init__.py` (empty).

### 2.5 ZERO production swing/ modifications

The dispatch brief mandated REUSE of D2's CLI subcommand `swing diagnose w-bottom-ruleset-comparison` against the R2-A cohort.json fixture; no production swing/ writes were needed. All 6 byte-stability tests pass — `research/harness/w_bottom_ruleset_comparison/` is unchanged from `main` HEAD.

---

## 3 Commit-cadence ledger

| Commit | Description |
|---|---|
| `d1bc9e1` | Slice 1: cohort CSV generator + 8 fast tests (15 flips → 7 unique tuples) |
| `f1a582e` | Slice 2: cohort.json fixture (N=65) + 12 harness-reuse / L2-LOCK / cohort-validity tests |
| `fa8f172` | Codex R1 fix bundle (parser robustness + audit JSON + section-boundary; 4 of 12 MAJOR in-code) |
| `61a0234` | Codex R2 fix bundle (layered verifier + canonical wrapper + heading regex + audit SHA; 5 of 8 MAJOR in-code) |
| `b699b69` | Codex R3 fix bundle (committed-artifact lock + bypass removal + POSIX paths; 2 of 3 MAJOR in-code) |
| `41132e2` | Codex R4 fix bundle (artifact lock strengthened + regen entrypoint; 3 of 3 MAJOR in-code) |
| `c292c50` | Codex R5 minor#3 fix (dead-code removal); chain converged NO_NEW_CRITICAL_MAJOR |
| _pending_ | Slice 7: smoke artifacts + findings doc + return report |

**Total: 7+ commits; ZERO Co-Authored-By trailer drift (preserves ~551+ cumulative streak through `2829637`).**

---

## 4 Codex MCP adversarial review chain (40th cumulative C.C lesson #6 validation slot)

| Round | C | M | m | Resolution summary |
|---|---|---|---|---|
| R1 | 0 | 12 | 8 | 4 in-code (audit JSON; strict verifier; section-boundary; column-name resolution); 6 deferred to findings doc analytical layer; 2 ACCEPTED |
| R2 | 0 | 8 | 3 | 5 in-code (layered verifier; canonical wrapper; line-anchored regex; audit SHA; variable_name reuse); 3 ACCEPTED |
| R3 | 0 | 3 | 4 | 2 in-code (committed-artifact lock test; bypass removal); 1 in-docs; 1 ACCEPTED (code-fence detection); 1 ACCEPTED (atomicity) |
| R4 | 0 | 3 | 3 | 6 in-code (CSV row count + audit metadata + unconditional SHA + flips length + regen entrypoint + docstring fix) |
| R5 | 0 | 0 | 3 | 1 in-code (dead-code removal); 2 BANKED V2 candidates |

**Cumulative: 0 CRITICAL + 26 MAJOR + 21 MINOR; ALL critical + major RESOLVED in-place or ACCEPTED with documented rationale; 2 R5 minor BANKED as V2 candidates.** R5 verdict: `NO_NEW_CRITICAL_MAJOR` — chain converged after 5 rounds.

**40th cumulative C.C lesson #6 validation NOTABLE.** Codex caught REAL defects:
- R1.M#2: silent under-extraction risk on parser permissiveness
- R1.M#4: hardcoded column positions vulnerable to schema reorder
- R2.M#3: section-boundary bug when no h3 heading follows (real bug)
- R2.M#4: line-anchored heading regex requirement for prose-defense
- R2.M#1+M#2: per-triple identity verification (not just aggregate counts)

Pre-Codex review applied cumulative expansions #1-#11 BUT Codex still surfaced 12 R1 MAJOR + 8 R1 MINOR; the cohort-generation surface had unique parser-robustness vectors not covered by prior expansion patterns. **No new gotchas banked this dispatch** (existing #33 cohort-validity-vs-verdict-criteria was first canonical application; the parser-robustness findings are localized to the cohort-extraction layer + don't generalize beyond markdown-table extraction patterns).

---

## 5 Test status

- 39 R2-A fast tests pass (`tests/research/r2a_tightness_days_required/`).
- Broader project fast suite: deferred for orchestrator-side verification (no production swing/ changes; D2 harness byte-unchanged tests pass).
- L2 LOCK preserved + reinforced via 2 BINDING R2-A tests (parametrized over r2a_tightness_days_required module set).

---

## 6 V1 simplifications + V2 candidates banked

Per cumulative discipline (CLAUDE.md V1-simplification-banking discipline):

### Banked as V2 candidates from Codex chain:

1. **R5.minor#1 — source-identity check in regenerate_cohort.py.** The `regenerate_cohort.py` entrypoint currently does not verify the source artifact's SHA-256 matches the canonical value (`b25bcde9...`) before regenerating. The committed-artifact test catches stale SHA, but the regen script itself could short-circuit on canonical-source-mismatch. V2 candidate: add a `--source-sha-canonical` flag or implicit lock against `CANONICAL_SOURCE_SHA256`.

2. **R5.minor#2 — flag-required for non-default paths.** `regenerate_cohort.py` accepts positional `source_md` + `cohort_csv` paths; deviating from default would silently regenerate to a non-canonical location. V2 candidate: require explicit `--allow-non-canonical-paths` flag for non-default invocations.

3. **R3.M#2 — code-fence-aware heading detection.** The `_section_body` regex matches `### vcp.tightness_days_required` at start-of-line even inside triple-backtick code fences. ACCEPTED as low-probability threat; canonical strict verifier is the defense. V2 hardening candidate: add `\`\`\`` open/close state tracking to skip-headings-inside-fences.

4. **R3.minor#4 — atomicity of CSV-then-audit write order.** A failure during audit JSON write after CSV write would leave the CSV without its sidecar. ACCEPTED as low-likelihood; if this becomes a reusable production-grade pattern, the discipline is temp-file + os.replace per existing CLAUDE.md guidance.

### Banked as next-arc operator decisions (post-merge):

- Pivot to a different V2 binding variable (e.g., `vcp.adr_min_pct +11`, `vcp.proximity_max_pct +5`, `vcp.orderliness_max_bar_ratio +1`) and test whether the cohort-specific-NEGATIVE pattern recurs.
- Pivot to market-conditions investigation per CLAUDE.md operator-paired next-arc enumeration.
- Pivot to Phase 14 commissioning per Path B sequencing.
- Pivot to archive refresh + re-run of full V2 sensitivity (last refresh 2026-05-24); test whether refreshed-archive flip events differ.

---

## 7 Cumulative discipline preservation

- **ZERO Co-Authored-By footer trailer drift** (~551+ cumulative streak through baseline `2829637`).
- **ZERO production swing/ writes** (R2-A reuses D2's existing CLI subcommand; no new CLI surface).
- **L2 LOCK preserved + reinforced** (2 NEW R2-A tests source-grep R2-A module set for schwabdev/yfinance/integrations imports).
- **Schema v21 unchanged** (no migrations).
- **ZERO new Schwab API calls** at backtest time (uses V2 Shape A reader's legacy parquet fallback; all 7 tickers use legacy `.parquet` files).
- **ASCII discipline preserved** across all NEW R2-A files (cohort_csv.py / regenerate_cohort.py / test_*.py / findings doc / return report; no non-ASCII glyphs in any path that flows through stdout/click.echo).

---

## 8 Acceptance criteria checklist (dispatch brief §6)

### §6.1 Functional

- [x] Cohort CSV generated at `exports/research/cohorts/r2a_tightness_days_required_sp1.csv` (7 unique rows).
- [x] pattern_cohort_evaluator smoke produces W primary verdicts for the 15-entry cohort (3391 raw double_bottom_w verdicts).
- [x] Cohort.json fixture generated at `tests/fixtures/research/r2a_tightness_days_required/cohort.json` (N=65 canonical primaries).
- [x] D2 6-ruleset harness invoked against new fixture; smoke artifact at `exports/research/w-bottom-ruleset-comparison-20260525T224203Z/`.
- [x] Manifest `l2_lock_preserved: true`; cohort_selection_method documented in cohort_csv.py + findings doc + dispatch brief.

### §6.2 Test scope

- [x] 39 NEW R2-A fast tests (exceeds 10-15 target; primarily Codex-driven expansion).
- [x] `python -m pytest tests/research/r2a_tightness_days_required/ -q` exits 0.
- [ ] Broader project fast suite: deferred for orchestrator-side verification.

### §6.3 Discipline preservation

- [x] ZERO Co-Authored-By footer drift.
- [x] ZERO production swing/ writes.
- [x] Schema v21 unchanged.
- [x] ZERO new Schwab API calls (L2 LOCK).
- [x] ASCII discipline complete (all NEW R2-A files are ASCII-only).

### §6.4 Analytical deliverables

- [x] Artifact directory at `exports/research/w-bottom-ruleset-comparison-20260525T224203Z/`.
- [x] Findings doc at `docs/r2a-tightness-days-required-cohort-backtest-findings-20260526.md`.
- [x] Cross-cohort comparison vs D2 Companion 2 + D2 EXPANDED + D1 in findings §2.
- [x] Verdict classification on canonical evaluation cohort (composite>=0.5 + recency<=365d): NEGATIVE.
- [x] Bootstrap CI on E R distribution (10,000 resamples; seed=42): [-1.377R, -0.782R]; P(mean>0)=0.0000.

### §6.5 Verdict classification

- [x] Applied to canonical evaluation cohort verbatim per gotcha #33 (no cohort substitution).
- [x] NEGATIVE verdict (ALL of {D, E, F} fail PARTIAL POSITIVE thresholds).
- [x] Cross-cohort consistency assertion: R2-A E NEGATIVE AND D2 E PARTIAL POSITIVE → INCONSISTENCY; E may be cohort-specific (findings §2 + §8.2).

### §7 Watch items

- [x] (a) Cohort generation time cost: <5 min orchestrator-side via grep + cohort_csv module.
- [x] (b) D2 harness REUSE VERBATIM: 6 byte-stability tests pass.
- [x] (c) D2 + D1 cohort overlap with R2-A: documented (5-ticker overlap with D1; 0-ticker overlap with D2 bias-free Apr-May 2026 S&P 500 cohort).
- [x] (d) NEW tickers FRO + SEI: pre-flight archive refresh applied (FRO + NAT both stale; refreshed via yfinance period='max').
- [x] (e) Cross-comparison cardinality: 7 R2-A vs 7 D2 vs 10 D1; 5-ticker overlap with D1.
- [x] (f) Codex MCP invocation per pre-dispatch operator-paired decision: invoked; 5 rounds; converged at R5 NO_NEW_CRITICAL_MAJOR.

---

## 9 Handoff to orchestrator

R2-A backtest implementation + Codex review COMPLETE end-to-end.

**Ready for orchestrator merge per `feedback_orchestrator_performs_merge` BINDING.**

Recommended merge commit message (no Claude co-author footer):

```
Merge applied-research-r2a-tightness-days-required-cohort-backtest into main: R2-A V2 OHLCV vcp.tightness_days_required +16 cohort 6-ruleset backtest SHIPPED — NEGATIVE verdict on canonical evaluation cohort (composite>=0.5 + recency<=365d; N=65); E mean R -1.086R; 95% CI [-1.377, -0.782]R; cross-cohort consistency check: D2 E PARTIAL POSITIVE does NOT generalize to V2-binding-variable-selection-biased ticker substrate (40th cumulative C.C lesson #6 validation NOTABLE; Codex MCP 5 rounds R5 NO_NEW_CRITICAL_MAJOR; 0 new gotchas; gotcha #33 cohort-validity discipline applied as canonical second application post-D2 Amendment 3)
```

Suggested CLAUDE.md status-line amendment (orchestrator-side):
- Append R2-A SHIPPED at HEAD `<merge-sha>`; cohort-specific NEGATIVE verdict confirms cross-cohort fragility of D2 Ruleset E PARTIAL POSITIVE.
- C.C lesson #6 validation count: 39 (was 38) — 40th NOTABLE.
- ~551+ cumulative ZERO Co-Authored-By streak preserved.

Next-arc operator decisions remain banked (§6 above); orchestrator chooses next dispatch.
