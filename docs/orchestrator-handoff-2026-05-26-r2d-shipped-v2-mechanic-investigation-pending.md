# Orchestrator handoff -- 2026-05-26 PM #3 (R2-D SHIPPED; V2-selection-mechanic investigation operator-selected as next arc; Turn H ready to design + dispatch)

You are taking over as orchestrator (**Turn H**) for the Swing Trading project at the **V2-selection-mechanic investigation pre-dispatch** breakpoint.

**Context:** Turn G drove R2-A + R2-D V2-binding-variable cohort backtests + extensive housekeeping. R2-A NEGATIVE on N=65 (vcp.tightness_days_required +16 cohort); R2-D INSUFFICIENT SAMPLE on N=4 STNG-only (vcp.adr_min_pct +11 cohort; substrate ~4x thinner than peers). Cumulative cross-cohort finding: V2-binding-variable cohort selection produces substrates that are EITHER (a) outright NEGATIVE for E (R2-A) OR (b) too thin to evaluate (R2-D). Operator selected **V2-selection-mechanic investigation** over additional R2-* binding-variable backtests because the substrate-thinness surprise raises a more interesting structural question than per-variable sweep continuation.

**main HEAD AT HANDOFF**: `aa5e693` (R2-D housekeeping; gotcha #34 banked). Turn H starts here.

**WORKING DIRECTORY**: `c:\Users\rwsmy\swing-trading`

---

## §0 Critical bootstrap framing (all BINDING memories)

- `feedback_pause_means_pause`
- `feedback_worktree_cli_invocation` -- `python -m swing.cli` (NOT bare `swing`)
- `feedback_orchestrator_qa_implementer_product` -- QA against reality on disk BEFORE merge
- `feedback_orchestrator_performs_merge` -- merge + push + housekeeping = orchestrator action
- `feedback_orchestrator_vs_implementer_execution` -- default to implementer-dispatch
- `feedback_always_provide_inline_dispatch_prompt` -- every brief gets inline prompt
- `feedback_commit_brief_before_inline_prompt` -- commit BEFORE inline prompt
- `feedback_handoff_briefs_only_when_context_actually_exhausting` -- only author when <30% remaining
- `feedback_verify_regression_test_arithmetic` -- when specifying tests, compute pre/post-fix paths

**NO Claude co-author footer**. ~559+ cumulative ZERO trailer drift through `aa5e693`.

---

## §1 Cumulative state at handoff

- **~6111 fast tests estimated** broader project (baseline ~6054 + 39 R2-A + 59 R2-D - some overlap; cross-bundle pin verifier required)
- **Schema v21 LOCKED** through entire arc
- **ZERO new Schwab API calls** (L2 LOCK preserved + REINFORCED via discriminating tests in V2 OHLCV / D2 / R2-A / R2-D harnesses)
- **34 cumulative CLAUDE.md gotchas (1-34)** BINDING for 42nd cumulative C.C lesson #6 validation
- **42nd C.C lesson #6 validation slot RESERVED** for V2-mechanic investigation's Codex chain (recommended YES per arc pattern)
- **~559+ cumulative ZERO Co-Authored-By trailer drift**
- **Method-records active**: V2 OHLCV criterion-evaluator v0.3.0 SHADOW + pattern-cohort-detection v0.1.1

### Recent commits on main (last 12; Turn G full arc)

| SHA | Purpose |
|---|---|
| `aa5e693` | R2-D housekeeping: gotcha #34 banked (brief-prescription cross-table verification; Expansion #18 candidate) + phase3e-todo Turn G #2 top entry |
| `7330628` | R2-D merge: V2 OHLCV vcp.adr_min_pct +11 cohort 6-ruleset backtest SHIPPED INSUFFICIENT SAMPLE on N=4 STNG-only |
| `ae8cfad` | R2-D slice 6: findings + return report + ASCII sweep |
| `ae039cc` | R2-D slice 5: D2 6-ruleset backtest smoke artifact |
| `19a8179` | R2-D Codex R2 minor fix bundle |
| `2be5df2` | R2-D Codex R1 fix bundle (6 MAJOR + 1 MINOR; includes Amendment 1 sp=1->sp=2.0 reconciliation) |
| `d0892fc` | R2-D slice 2: cohort.json fixture + harness-reuse + L2 LOCK + committed-artifact tests |
| `a1fbd60` | R2-D slice 1: cohort CSV generator + 22 fast tests for vcp.adr_min_pct +11 |
| `6c34e2d` | R2-D dispatch brief |
| `6f64f91` | R2-A housekeeping: D2 findings Amendment 6 + phase3e-todo Turn G top entry |
| `634cc9f` | R2-A merge: V2 OHLCV vcp.tightness_days_required +16 cohort 6-ruleset backtest SHIPPED NEGATIVE on N=65 |
| `f01c789` | Turn G handoff brief (transition from Turn F EXTENDED) |

---

## §2 What just shipped (Turn G full arc; sessions 1+2)

### §2.1 Turn G session 1: R2-A (commits `f01c789` -> `6f64f91`)

R2-A V2 OHLCV `vcp.tightness_days_required +16` cohort 6-ruleset backtest SHIPPED at `634cc9f`. Cohort: 15 watch->aplus flips at sweep_point=1 across 7 unique tickers (FRO/KOD/NAT/OII/RLMD/SEI/TROX). Canonical evaluation cohort N=65; Ruleset E mean R -1.086R; 95% CI [-1.377, -0.782]R; P(mean>0)=0.0000; **NEGATIVE verdict**. Cross-cohort interpretation: D2 EXPANDED PARTIAL POSITIVE for E does NOT generalize to V2-binding-variable-selection-biased cohort; E is **cohort-specific to bias-free S&P 500**.

Codex MCP 5 rounds R5 NO_NEW_CRITICAL_MAJOR (0C + 26M + 21m cumulative; ALL major resolved or accepted; 2 R5 minors banked V2 candidates). **40th cumulative C.C lesson #6 validation NOTABLE.** 0 new gotchas this dispatch.

Housekeeping at `6f64f91`: D2 findings Amendment 6 (cross-cohort consistency check; bounds D2 E PARTIAL POSITIVE generalization scope) + phase3e-todo Turn G first top entry.

### §2.2 Turn G session 2: R2-D (commits `6c34e2d` -> `aa5e693`)

R2-D V2 OHLCV `vcp.adr_min_pct +11` cohort 6-ruleset backtest SHIPPED at `7330628`. **Cohort architecture decision LOCK**: sibling module strategy at `research/harness/r2d_adr_min_pct/` (DO NOT refactor R2-A's cohort_csv into a shared base; V2 candidate banked at brief §1.2). Cohort: 11 watch->aplus flips at sweep_point=**2.0** (NOT sp=1 as brief originally prescribed; Amendment 1 reconciled via Codex R1.M#1; sp=2.0 is the actual binding signal per V2 sensitivity SUMMARY TABLE). Cohort substrate AMX/GLNG/STNG/XENE (4 unique tickers).

Canonical evaluation cohort N=4 ALL FROM STNG (single-ticker substrate). Substrate density ~3% vs R2-A ~13% / D2 EXPANDED ~12% (~4x thinner). **INSUFFICIENT SAMPLE verdict (DIRECTIONAL POSITIVE color)** per gotcha #33 BINDING (third canonical application). F's technical PARTIAL POSITIVE on N=4 STNG-only (3 of 3 closed @ +0.122R mean; 100% wr) EXPLICITLY REJECTED as cohort substitution per Amendment 1 A1.2 LOCK. E's single closed trade @ +0.800R (STNG-2025-05-22; measured-move target at 5 sessions) is DIRECTIONAL POSITIVE color only.

Codex MCP 2 rounds R2 NO_NEW_CRITICAL_MAJOR (0C + 6M + 6m cumulative; ALL major resolved; 2 minors banked). **41st cumulative C.C lesson #6 validation NOTABLE.** **NEW gotcha #34 banked**: brief-prescription cross-table verification (orchestrator-side brief-authoring discipline failure at R2-D R1.M#1; Expansion #18 candidate; BINDING for 42nd validation onwards).

Housekeeping at `aa5e693`: NEW gotcha #34 + phase3e-todo Turn G #2 top entry.

**Cross-cohort discrimination test status: DEFERRED.** R2-A NEGATIVE on N=65 vs R2-D INSUFFICIENT SAMPLE on N=4 CANNOT discriminate between "R2-A NEGATIVE unique to tightness_days_required" vs "systemic across V2 binding variables."

### §2.3 Cumulative 5-way cross-cohort table (load-bearing)

| Cohort | Selection mechanism | N pat | E closed-and-profitable | E mean R | E 95% CI | E verdict |
|---|---|---|---|---|---|---|
| D1 post-refresh | Hand-curated +67 watch->aplus from V2 tightness_range_factor=1.005; recency<=60d | 12 | n/a (E not tested) | n/a | n/a | NEGATIVE-strict (close_below_50d) |
| D2 Companion 2 | Bias-free S&P 500; composite>=0.5 + recency<=120d | 26 | 3 (100% wr) | +1.208R | [+0.464R, +2.026R] | PARTIAL POSITIVE (degenerate) |
| D2 EXPANDED | Bias-free S&P 500; composite>=0.5 + recency<=365d | 71 | 5 | +1.220R | [+0.753R, +1.704R] | PARTIAL POSITIVE (6 of 7 statistical-defensibility PASS) |
| R2-A canonical | V2 tightness_days_required +16; recency<=365d | 65 | 9 (22.5% wr) | -1.086R | [-1.377R, -0.782R] | NEGATIVE |
| R2-D canonical | V2 adr_min_pct +11; recency<=365d | 4 | 1 (100% wr; N=1) | +0.800R | n/a | INSUFFICIENT SAMPLE (DIRECTIONAL POSITIVE color) |

---

## §3 What YOU (Turn H) MUST do

### §3.1 Design the V2-selection-mechanic investigation dispatch brief

This is the operator-selected next arc. The investigation is **analytical / exploratory**, NOT a backtest. Key research questions to design the brief around (recommend operator-paired triage BEFORE drafting the brief):

1. **Why are V2-binding-variable-selected substrates W-pattern-thin?** R2-A's substrate produced 65 W primaries (~13% density); R2-D's substrate produced 4 W primaries (~3% density). What is different about the 4 R2-D tickers (AMX/GLNG/STNG/XENE) vs the 7 R2-A tickers (FRO/KOD/NAT/OII/RLMD/SEI/TROX) that produces 4x lower W incidence?

2. **What chart-regime is each V2 binding variable selecting for?** Hypothesis: tightness criteria select tickers in flat/declining trends with few V-bottoms; adr_min_pct loosening selects tickers with intrinsically low volatility where W-bottom amplitude is small + harder to detect; proximity_max_pct selects tickers far from highs (recovery candidates); orderliness selects steady trends.

3. **Is V2 cohort selection FUNDAMENTALLY incompatible with E ruleset?** R2-A NEGATIVE + R2-D INSUFFICIENT SAMPLE cumulatively suggest either (a) V2 selects FOR chart conditions where E fails OR (b) V2 selects FOR thin substrates where E's mechanism cannot be reliably tested. Either is a critical compatibility finding for any future production deployment of E on V2-derived cohorts.

4. **Is the substrate-thinness a sweep_point=2.0 artifact?** R2-D used sp=2.0 per Amendment 1; would sp=1 yield different substrate? Per Codex R1.M#1 disclosure, sp=1 emits 15 flips identical to R2-A. R2-D could re-run at sp=1 as a sub-investigation but probably not informative (mirrors R2-A).

5. **Cross-cohort baseline comparison**: For each V2 binding variable (tightness_range_factor / tightness_days_required / adr_min_pct / proximity_max_pct / orderliness_max_bar_ratio), what fraction of the S&P 500 universe would produce W primary verdicts at canonical filter (composite>=0.5 + recency<=365d)? This is the BASELINE incidence. Then for each V2-selected substrate, what fraction of the SELECTED tickers produce W primary verdicts? The DELTA is the selection-mechanic-specific W-incidence signal.

### §3.2 Brief authoring discipline (per cumulative + new gotcha #34)

Per **NEW gotcha #34 (brief-prescription cross-table verification)** BINDING for the 42nd validation onwards: when authoring the V2-mechanic investigation brief, if the brief references V2 sensitivity artifact tuples (variable, sweep_point, count), CROSS-CHECK the SUMMARY TABLE at the artifact top, NOT just drill-down section headers. The brief's COUNT contract is binding; SUMMARY TABLE overrides drill-down section header.

Brief structure recommendation (adapt from R2-A / R2-D briefs but pivot from backtest to investigation):
- §0 Read first
- §1 Investigation methodology (NEW): empirical questions + measurement specs + comparison cohorts
- §2 Cohort enumeration (5 V2 binding variables; canonical filter; baseline S&P 500)
- §3 Output / analytical surface (findings doc; tables; possibly charts)
- §4 Discriminating tests (lighter scope; investigation is exploratory)
- §5 Acceptance criteria
- §6 Watch items + cumulative discipline (34 gotchas BINDING; gotcha #34 first canonical application post-banking)
- §7 Codex MCP decision (recommend YES; 42nd C.C lesson validation slot)
- §8 Commit cadence + return report
- §9 Branch + worktree setup
- §10 Do NOT
- §11 Pre-dispatch operator-paired decisions

### §3.3 Operator pairing recommended BEFORE brief drafting

The investigation's scope is exploratory + has multiple valid research-question framings. **Strongly recommend Turn H opens with an operator AskUserQuestion** triaging:
- Which research questions (§3.1 #1-5) to scope into V1 vs defer to V2
- Whether to use 5 V2 binding variables OR a subset (orderliness_max_bar_ratio +1 may be too small to be informative)
- Whether to include a cross-comparison with bias-free baseline cohort (S&P 500 W incidence)
- Whether the investigation produces NEW research artifacts (e.g., V2-selection-mechanic study writeup at `research/studies/2026-05-26-v2-selection-mechanic-analysis.md`) OR appends to existing study artifacts

### §3.4 Cumulative discipline BINDING

- **ZERO Co-Authored-By footer trailer drift**: ~559+ commits through `aa5e693`. DO NOT regress.
- **34 cumulative CLAUDE.md gotchas BINDING for 42nd validation onwards**
- **42nd C.C lesson #6 validation slot RESERVED** for V2-mechanic investigation's Codex chain
- **Schema v21 LOCKED**
- **ZERO new Schwab API calls** (L2 LOCK)
- **Production swing/ READ-ONLY** beyond OQ-13-mirror CLI carve-outs (no new CLI expected for V2-mechanic investigation; it's an analytical script + findings doc, OR potentially a new CLI subcommand if operator decides V2-mechanic needs persistent surface)
- **V1 persisted state UNCHANGED**

---

## §4 Operator-pending items (NOT orchestrator-blocking)

- **V2-selection-mechanic investigation brief authoring + dispatch** -- Turn H primary task
- **Phase 14 commissioning consideration** -- banked candidate; gated on cross-cohort robustness establishment (NOT established for any single ruleset post-R2-A + R2-D)
- **D + E hybrid ruleset variant** -- banked V2 candidate from D2 return report
- **R2-E (vcp.proximity_max_pct +5) backtest** -- ALTERNATIVE next-arc if operator pivots; banked
- **R2-F (vcp.orderliness_max_bar_ratio +1) backtest** -- ALTERNATIVE next-arc; banked; substrate may be even thinner than R2-D
- **Option C real-time prospective tracking** -- banked V2 candidate; could run in parallel with V2-mechanic investigation
- **Worktree husks** -- multiple `.worktrees/applied-research-*` from prior dispatches; operator runs cleanup when convenient
- **Schwab refresh-token clock** -- renew when <=24h remaining

---

## §5 Cumulative streaks to preserve

- **ZERO `Co-Authored-By` footer trailer drift**: ~559+ commits through `aa5e693`. DO NOT regress.
- **C.C lesson #6 cumulative validations**: 40 NOTABLE (R2-A) + 41 NOTABLE (R2-D); 42nd SLOT RESERVED for V2-mechanic
- **Schema v21 LOCKED** through entire arc
- **ZERO new Schwab API calls** (L2 LOCK)
- **Production swing/ READ-ONLY** beyond OQ-13-mirror CLI carve-outs (D1 80 lines + D2 77 lines; R2-A + R2-D ZERO production writes)
- **V1 persisted state UNCHANGED**
- **34 cumulative CLAUDE.md gotchas** BINDING for 42nd validation onwards

---

## §6 Suggested first session flow (Turn H)

1. Read this brief end-to-end
2. Read CLAUDE.md current state + tail (gotchas #1-#34; #34 newest)
3. Read R2-D findings doc at `docs/r2d-adr-min-pct-cohort-backtest-findings-20260526.md` (especially §2.1 substrate-depth comparison + §8.1 cross-cohort discrimination DEFERRED interpretation)
4. Read R2-D return report at `docs/r2d-adr-min-pct-cohort-backtest-return-report.md`
5. Read R2-A findings + return report for arc context
6. Operator pairing via AskUserQuestion (§3.3) -- triage research questions + scope
7. Draft V2-mechanic investigation dispatch brief (§3.2)
8. Commit brief BEFORE inline prompt per `feedback_commit_brief_before_inline_prompt` BINDING
9. Provide inline dispatch prompt for operator paste
10. Pause for implementer dispatch + ship notification

Estimated wall-clock for Turn H first session: ~3-5h depending on operator-pairing depth + brief scope. The brief itself is larger than R2-A/R2-D briefs because it pivots from backtest to investigation; multiple novel methodological choices to specify.

---

## §7 Do NOT

- Re-litigate the LOCKED gotcha #33 + #34 disciplines (cohort-validity + brief-prescription cross-table)
- Skip operator pairing on research-question scoping (§3.3)
- Add Co-Authored-By footer to ANY commit
- Modify production swing/ beyond existing OQ-13 carve-outs (no new CLI expected for V2-mechanic; if operator decides ONE is needed, that's an OQ-13-mirror)
- Modify V1 persisted state
- Trigger Schwab API calls
- Skip cumulative gotcha discipline (34 gotchas BINDING)
- Use the V2-mechanic investigation to "find a winning ruleset" by alternative-cohort substitution (gotcha #33 third canonical application LOCKED; investigation is analytical not verdict-producing)
- Pre-emptively dispatch R2-E or R2-F before V2-mechanic investigation has shipped (operator explicitly selected V2-mechanic over R2-E)
- Author another handoff brief unless context drops below 30% remaining AND you're at a natural breakpoint

---

*End of Turn H orchestrator handoff brief. R2-D SHIPPED / V2-selection-mechanic investigation operator-selected as next arc. Turn H opens with operator pairing on research-question scoping, then drafts the V2-mechanic investigation dispatch brief + inline prompt. The investigation is exploratory / analytical (NOT a backtest); examines WHY V2-binding-variable cohort selection produces W-pattern-thin substrates (R2-D ~3% density vs peer ~13%) AND whether V2 selection is fundamentally compatible with E ruleset deployment. ~559+ cumulative ZERO Co-Authored-By trailer drift preserved through `aa5e693`. 34 CLAUDE.md gotchas BINDING for 42nd cumulative C.C lesson #6 validation.*
