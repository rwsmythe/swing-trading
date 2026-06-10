# Shadow-Expectancy Engine — Entry / Canonical-Detection Join Correction — Design Spec

**Date:** 2026-06-09
**Status:** Design — correction of a shipped, converged spec; pending Codex convergence + writing-plans
**Author role:** Research Director / CIO evaluator (see [`docs/research-director-context.md`](../../research-director-context.md))
**Phase:** copowers:brainstorming output
**Corrects:** [`docs/superpowers/specs/2026-06-08-shadow-expectancy-engine-design.md`](2026-06-08-shadow-expectancy-engine-design.md) (the "original spec"). Implemented by [`docs/superpowers/plans/2026-06-09-shadow-expectancy-engine.md`](../plans/2026-06-09-shadow-expectancy-engine.md); shipped code under `research/harness/shadow_expectancy/`.

---

## 0. What this document is

A **surgical correction** of the shipped shadow-expectancy engine. The engine's first live run (2026-06-09) priced **zero trades**: 42 unique signals, 100% routed to `no_canonical_detection`. Root cause is a false premise in entry-trigger identification and canonical-detection selection. This spec fixes **only** entry-trigger identification (original §5.1 / D9-adjacent), canonical-detection selection (original §6), and the funnel reasons that depend on them (original §7). **Everything else in the original spec stands** — the `[realistic, favorable_reprice]` bracket (D2), the Day-3–5 partial (D3/D4), the breakeven/MA-trail simulator internals (§5.2–§5.8), the four censoring scenarios (D10), the scorecard (§7.2), the two-level funnel *structure* (§7.1), reproducibility (§8). Section 9 of this document is an explicit supersede/preserve ledger against the original.

All claims of fact below were verified against the live DB (`%USERPROFILE%/swing-data/swing.db`, read-only) and the production observe step (`swing/pipeline/runner.py:_advance_status`, lines 2526–2577) on 2026-06-09. The verification queries and their outputs are reproduced in §8 so Codex and writing-plans can re-run them.

---

## 1. The bug

### 1.1 Symptom
`swing diagnose shadow-expectancy` against the live DB → **42 unique signals → 100% `no_canonical_detection` → 0 priced trades → empty scorecard.** Funnel honesty surfaced it cleanly (no fabricated result).

### 1.2 Root cause
The original spec (§6) selects the **canonical detection** as the one whose `detection.pivot == candidate.pivot` (tick-normalized), and excludes the signal under `no_canonical_detection` when no detection pivot matches. In production these are **different quantities that never coincide**:

- `detection.pivot` = `structural_anchors_json → evidence → pivot_price` — the **pattern-geometric** pivot, written per pattern class by the detectors. It is class- and shape-dependent and **frequently `0.0` in practice**: the **live-emitted** `cup_with_handle` / `double_bottom_w` rows in run 89 carried `pivot_price = 0.0` (the zero-evidence path), while `vcp` / `flat_base` / `high_tight_flag` carried a real level. (The detectors *can* compute real cup/dbw pivots on a fully-successful detection — `swing/patterns/cup_with_handle.py:762`, `double_bottom_w.py:592` — so "cup/dbw are always 0.0" is **not** the claim. The load-bearing fact is narrower and unconditional: `detection.pivot` is the geometric pivot and is **never equal** to `candidate.pivot` regardless of class.)
- `candidate.pivot` = the **screening** pivot on the `candidates` row — a different computation entirely.

Verified live values (run 89, all `watch`):

| ticker | detection pivots (per pattern class) | candidate.pivot |
|---|---|---|
| BULZ | vcp 49.89, flat_base 49.89, htf 49.89, **cup 0.0, dbw 0.0** | **56.09** |
| CIFR | vcp 25.55, flat_base 25.55, htf 25.55, **cup 0.0, dbw 0.0** | **28.62** |
| WULF | (mixed real / 0.0) | **27.47** |
| VECO | (mixed real / 0.0) | **65.03** |

They are not the same number and were never meant to be. The shipped tests passed because their fixtures **forced `detection.pivot == candidate.pivot`** (e.g. `tests/research/shadow_expectancy/test_collapse.py:_det(5, 10.0)` matched against `candidate_pivot=10.0`). This is the CLAUDE.md **"Synthetic-fixture-vs-production-emitter shape drift"** gotcha. The premise survived 6 writing-plans + 3 executing-plans Codex rounds because every review checked logic-against-spec, not data-shape-against-DB. Only the live run could falsify it.

### 1.3 A second latent fault the live data exposes
Even if the pivot-match requirement were merely relaxed, the original §6 **`inconsistent_trigger_state`** gate would still falsely exclude. That gate requires all detections in a `(run, ticker)` group to share an identical first `triggered_open` session. But `triggered_open` is stamped by the observe step on `bar.high >= detection.pivot` — so a `cup`/`dbw` detection with `pivot=0.0` triggers on the **first** forward bar (high ≥ 0 always), while a `vcp` detection with `pivot=49.89` stays `pending`. The first-trigger session therefore **legitimately differs across pattern classes within the same group**. Verified: **8 of 42 live groups** have differing first-trigger sessions. The fix must remove this gate, not just the pivot match — both rest on the geometric pivot the correction abandons.

---

## 2. The fix (entry recomputation from the screening pivot)

**Re-key entry to `candidate.pivot`, recomputed over the group's shared frozen forward bars. Demote canonical-detection selection to a pure bar-source choice; the geometric `detection.pivot` is no longer consulted for entry at all.**

### 2.1 Entry trigger (supersedes original §5.1 entry-timing)
Entry session = the **first bar in the canonical forward series (date-ascending) whose `high >= candidate.pivot`**, where `candidate.pivot` is the screening pivot on the joined `candidates` row.

- The comparison is a plain threshold (`bar.high >= candidate.pivot`); no tick-normalization is required (tick-normalization in the original existed only for the now-deleted equality match).
- If **no** forward bar reaches `candidate.pivot`, the signal is **`never_triggered`** (an attributed terminal — counted in the per-hypothesis signal denominator, contributes 0R to per-signal expectancy; D11 preserved). On the current thin log this is the **dominant** outcome (see §6).
- **Zero-forward-depth guard (Codex R1-#3):** if the trigger fires on the **last available bar** of the canonical series (so `forward_bars` would be empty), the trade is **excluded under `insufficient_forward_depth`** (per-hypothesis; the reason already reserved in `ATTRIBUTED_EXCLUDED_REASONS`, hitherto unused) — it is **not** simulated. A triggered trade with zero post-entry bars has no management data; routing it to `insufficient_forward_depth` is honest and avoids the shipped simulator's empty-`forward_bars` artifact (it would set `last_close = entry_fill` → a spurious 0R MTM at the fill — `simulator.py:191`). This keeps `simulate(...)` **never called with empty `forward_bars`**, so the simulator contract and internals stay genuinely untouched (the orchestrator guards before the call).
- `entry_fill = max(candidate.pivot, entry_bar.open)` — unchanged in form (D2). The shipped simulator already fills from `candidate.pivot`; the correction makes the **entry bar** coherent with it (today the simulator fills at `max(candidate.pivot, …)` but is handed the *geometric-pivot* `triggered_open` bar — an internal incoherence the recompute removes).
- `initial_stop = entry_bar.low`; `risk_per_share = entry_fill − entry_bar.low`; the `degenerate_risk` gate (`entry_fill <= entry_bar.low`) — all **unchanged** (D6 / §5.2).
- Everything downstream of entry is **unchanged**: §5.0 per-bar precedence, Day-3 partial (§5.3), breakeven (§5.4), maturity-staged MA trail (§5.5), gap-aware exit fills (§5.6), horizon/censoring (§5.7), multi-leg R on the fixed denominator (§5.8), the entry-bar same-bar-adverse ambiguity sensitivity (D9 — it still flags the recomputed entry bars where `entry_bar.low < entry_fill`).

### 2.2 No entry-validity gate beyond `high >= candidate.pivot` (resolves §3.1 design question)
The original observe-step trigger was `high >= pivot AND close >= structural_low` (invalidation wins over breakout). The correction applies **no** close-confirmation gate, for three reasons:
1. The `structural_low` is a **geometric, per-pattern-class** quantity (and is itself frequently absent / `0.0`) — re-applying it would reintroduce exactly the geometry this correction abandons.
2. There is **no candidate-frame structural low** to gate on. `candidate.initial_stop` is explicitly **stale/unused** (executing-plans R2-M1 removed it; the mechanical stop is `entry_bar.low`), so it must not gate eligibility.
3. The same-bar-adverse sensitivity (D9) already reports the headline under the assumption that ambiguous entry bars (`low < entry_fill`) stopped out same-session.

**Honest statement of the cost (Codex R1-#2):** dropping close confirmation means **V1 admits intraday-touch entries** — a bar that merely *tips* `candidate.pivot` intraday then closes weak still enters. This is **potentially optimistic**, and the "the mechanics stop it out anyway" argument is **not** generally true: the simulator deliberately does **not** test the stop on the entry bar (D9 — the stop is live only from the next session, `simulator.py:117`), so a weak-closing entry bar with **no** subsequent bar is never penalized at all, and one with subsequent bars is penalized only later. The correction therefore does **two** things rather than hand-wave:
  - (a) records the no-close-confirmation choice as a **named V1 limitation** (§7.5), candidate-frame confirmation flagged as possible V2 hardening; and
  - (b) adds a **reported diagnostic flag `entry_bar_weak_close`** (`entry_bar.close < candidate.pivot`) to the per-trade ledger and a count in the scorecard — an **annotation only, no behavior change** — mirroring the existing `entry_bar_ambiguous` flag, so the operator can see exactly how many priced entries were intraday-touch-only and discount the headline accordingly.

This keeps the correction surgical (no new entry gate, no pattern geometry reintroduced) while refusing to understate the optimism it admits.

### 2.3 Canonical detection = bar source only (supersedes original §6 canonical selection)
All detections for a `(pipeline_run_id, ticker)` group observe the **same ticker on the same calendar**, and the observe step freezes each session's bar from the archive **independently of pattern class** — so the OHLC for a given `observation_date` is **identical across the group's detections** (verified: 0 groups out of 42 have any divergent OHLC on a shared date). Detections therefore differ only in *how far* their chains extend (a `pending` detection expires at `max_pending`; a `triggered_open` detection is observed through the post-trigger window).

**Canonical bar source = the group's detection with the LONGEST frozen observation chain (most bars), tie-broken by lowest `detection_id`.** Its full date-ascending bar series is the forward series the entry recompute (§2.1) scans.

- **Why longest, not lowest-id (resolves §3.2; diverges from brief §2's "lowest detection_id"):** terminated chains are **strict date-prefixes** of the longest (verified: **0 prefix violations** across 42 groups; **1 group** has detections of differing chain length). Lowest-id could therefore select a **truncated** chain and miss a later breakout above `candidate.pivot`. Longest-chain == the date-union of the group and never truncates. The choice is data-justified, not stylistic.
- The `inconsistent_detection_series` gate **survives and is STRENGTHENED to enforce the strict-prefix invariant the longest-chain rule relies on (Codex R1-#1).** The prefix property is **empirically observed, not guaranteed by source** (the observe writer appends per open detection independently — `runner.py:2728`; nothing in code forbids a gappy/interior-missing chain). So an **overlap-only** OHLC check is insufficient: it would silently accept e.g. `A=[d1,d3]` vs `B=[d1,d2,d3]` (interior date missing) and let "longest" be a non-union series, changing trigger availability. **The gate therefore asserts, after sorting each detection's chain by `observation_date`:** every non-canonical chain's date list **equals** `canonical_dates[:len(chain)]` (a true date-prefix — no missing interior sessions, no divergent dates) **AND** the OHLC on every shared date matches the canonical. **Any** violation → exclude under `inconsistent_detection_series` (an `unattributed`, substrate-integrity reason). Empirically this never fires today; it makes the longest == union guarantee a **checked invariant** rather than an assumption.
- The `inconsistent_trigger_state` gate is **removed** (its reason retired) — see §1.3.
- The `no_canonical_detection` reason is **removed** — there is no pivot to match, so the fault it named cannot occur.
- `collapsed_duplicate_detection` accounting is **unchanged**: a group of *k* detections contributes `k − 1` collapsed duplicates and 1 unique signal, on both the success and the exclusion paths (preserves the detection-level reconciliation invariant).

---

## 3. Funnel-reason changes (supersedes the relevant parts of original §7.1)

### 3.1 Removed reasons
- **`no_canonical_detection`** — deleted from `FUNNEL_REASONS` and `UNATTRIBUTED_REASONS`. No pivot-match step remains.
- **`inconsistent_trigger_state`** — deleted from `FUNNEL_REASONS` and `UNATTRIBUTED_REASONS`. The observe-step trigger session is no longer consulted (entry is recomputed); the gate produced false exclusions for multi-pattern-class groups (§1.3).

### 3.2 New reason — `no_candidate_pivot` (resolves §3.3 design question)
~3.5% of candidates carry a null/`0.0` pivot (verified: **255 / 7241** `candidates` rows have `pivot IS NULL OR pivot = 0`). Such a candidate has **no screening breakout level**, so no entry can be recomputed.

- **Routing: per-hypothesis `excluded` (attributed), not `unattributed`.** A null-pivot candidate still **joins** (the row exists) and still **attributes** (bucket + frozen criteria are independent of `pivot`). It is excluded only at the **validate** stage (which runs after attribution), exactly like `invalid_ohlc` / `degenerate_risk`. Keeping it per-hypothesis preserves the original spec's principle that **post-attribution data-quality rates stay visible per bucket** and are never hidden in a global bucket.
- It is added to `ATTRIBUTED_EXCLUDED_REASONS` and is **disjoint** from `UNATTRIBUTED_REASONS` (so `build_funnel`'s existing per-terminal reason validation continues to reject misrouting).
- **Split from `invalid_ohlc`:** the validate step returns `no_candidate_pivot` specifically when `candidate.pivot` is `None`/non-finite/`<= 0`, and reserves `invalid_ohlc` for malformed *frozen bars*. A null screening pivot is an **expected, common** data state, not a corrupt bar; conflating them would muddy the honesty reporting. (Mechanically, the shipped `validate_candidate_levels` already rejects pivot `None`/`<=0` — the change is to return the more specific reason string.)

### 3.3 Preserved reasons
`no_candidate_join` (candidate **row** absent — now decided purely by `candidate is None` in the orchestrator, no longer entangled with `candidate_pivot`), `matched_no_hypothesis`, `multi_match` (defensive), `inconsistent_detection_series`, `invalid_ohlc`, `degenerate_risk`, `insufficient_forward_depth`, `missing_observations`, `lifecycle`, `never_triggered` — all unchanged in meaning and routing. The reconciliation invariant `Σ(unattributed reasons) + Σ(per-hypothesis terminals) == unique_signals` is **unchanged** and still asserted at the producer (`run_harness`).

### 3.4 Resulting `UNATTRIBUTED_REASONS` (after correction)
`{no_candidate_join, matched_no_hypothesis, multi_match, inconsistent_detection_series}` (was six; `no_canonical_detection` and `inconsistent_trigger_state` removed).

### 3.5 Resulting `ATTRIBUTED_EXCLUDED_REASONS` (after correction)
`{no_candidate_pivot, invalid_ohlc, degenerate_risk, insufficient_forward_depth, missing_observations, lifecycle}` (`no_candidate_pivot` added).

---

## 4. No-look-ahead proof (resolves §3.4 design question; CORRECTS the brief's framing)

The brief states "forward observations are written strictly after `detection_date`, so the detection-day bar is never in the forward chain." **This is factually wrong against the live data** and must not be the proof. Verified: the **first** forward observation for a detection is **on `detection_date` itself** (the action session), with `sessions_since_detection = 1`. Example (detection 1, BULZ vcp): `detection_date = 2026-06-05`, `data_asof_date = 2026-06-04`, first observation `observation_date = 2026-06-05`.

The proof rests on **one enforced invariant** the harness can rely on directly, plus an upstream by-construction property:

1. **Enforced (the harness's actual guarantee):** every forward observation satisfies `data_asof_date < observation_date`. This is **enforced in source** — `list_observable_detections` only advances a detection on a session strictly after its `data_asof_date` (`swing/data/repos/pattern_detection_events.py:119`; Codex-verified). So every bar the entry recompute scans is **strictly after the detection's information cutoff**, even though the **first** scanned bar is on `detection_date` itself (the action session, one session after `data_asof_date`).
2. **Upstream, by construction (not re-derived by the harness):** `candidate.pivot` is a screening output of the production evaluator over a fetched OHLCV frame whose **maximum bar date is `data_asof_date`** (the runner derives `data_asof` as the max fetched session — `swing/pipeline/runner.py:1159` — and the evaluator screens over that frame, `swing/evaluation/evaluator.py:58`). So the pivot is bounded by `data_asof_date` **by construction of the screening**, and is fixed before any forward bar exists. The harness **does not recompute** the pivot; it consumes the frozen value. Therefore the harness's no-look-ahead correctness does **not** depend on re-proving the pivot's provenance — it depends only on invariant (1).
3. **Conclusion (appropriately scoped):** recomputing "first bar with `high >= candidate.pivot`" compares a **pre-committed threshold** (fixed ≤ `data_asof_date` upstream) against bars **strictly after `data_asof_date`** (enforced). No bar in the scan set informed the threshold. Hence no look-ahead. The guarantee is **stronger** than "after `detection_date`" (it holds even though the detection-day bar is in the chain) and rests on a **source-enforced** boundary, not a cadence assumption. The one piece this spec does **not** prove from persisted data is that a given historical candidate's evaluator frame was *exactly* bounded by `data_asof_date`; that is a property of the production screening at write time, stated here as a precondition, not a harness obligation.

Writing-plans MUST encode a fixture invariant asserting `data_asof_date < observation_date` for every forward bar (the enforced boundary), and Codex MUST confirm the boundary against `pattern_detection_events.py` / the live observation rows.

---

## 5. Code-change surface (surgical)

All paths under `research/harness/shadow_expectancy/` unless noted. No new `swing/` files.

- **`collapse.py`** — replace `collapse_detections(detections, candidate_pivot)`:
  - Signature drops `candidate_pivot` (no longer needed for selection).
  - Canonical = longest chain, tie low `detection_id` (§2.3). To compute "longest," the detection views must carry their chain length (or full bar series); the orchestrator already reads each chain.
  - Implement the **strict date-prefix** `inconsistent_detection_series` gate exactly as §2.3 (R2-#1): sort each detection's chain by `observation_date`; canonical = longest chain, tie low `detection_id`; every non-canonical chain's date list MUST equal `canonical_dates[:len(chain)]` AND its OHLC on every shared date MUST match the canonical's; **any** violation → `inconsistent_detection_series`. (NOT an overlap-only check — that is the insufficient condition R1 rejected.) **Delete** the `no_canonical_detection` and `inconsistent_trigger_state` branches and the `first_trigger_session` field's role here.
  - Return the canonical's full bar series (or enough for the orchestrator to fetch it).
- **`run.py`** — entry recompute replaces `_entry_and_forward`'s `triggered_open`/`entry_fired` search:
  - Build the canonical bar series (longest chain), date-ascending.
  - `entry_idx = first i where bars[i].high >= candidate.pivot`; `entry_bar = bars[entry_idx]`; `forward_bars = bars[entry_idx+1:]`. `None` → `never_triggered`.
  - **`entry_idx == len(bars) - 1` (empty `forward_bars`) → `insufficient_forward_depth`** (per-hypothesis excluded); do **not** call `simulate` (R1-#3).
  - Emit the **`entry_bar_weak_close`** annotation (`entry_bar.close < candidate.pivot`) into the ledger row and the scorecard count (R1-#2); no behavior change.
  - `candidate is None` → `no_candidate_join` (decided here, not in collapse).
  - Pipeline order unchanged: collapse(bar source) → join → attribute → **validate (now returns `no_candidate_pivot` for pivot faults)** → entry-recompute → simulate. Order entry-recompute after validate so a null pivot is caught as `no_candidate_pivot` **before** the recompute dereferences it.
- **`validate.py`** — `validate_candidate_levels` returns `"no_candidate_pivot"` (not `"invalid_ohlc"`) for `pivot` `None`/non-finite/`<= 0`; bar checks still return `"invalid_ohlc"`. `validate_signal` threads the specific reason.
- **`constants.py`** — `FUNNEL_REASONS`, `UNATTRIBUTED_REASONS`, `ATTRIBUTED_EXCLUDED_REASONS` updated per §3.4 / §3.5; remove `no_canonical_detection`, `inconsistent_trigger_state`; add `no_candidate_pivot`. `PRICE_TICK_DECIMALS` may remain (harmless) or be removed with the equality match.
- **`funnel.py`** — no structural change; it consumes the updated reason vocabularies. Its per-terminal reason validation continues to enforce routing.
- **`bracket.py`, `simulator.py`, `exceptions.py`, `attribution.py`** — **unchanged** (the simulator's `simulate(pivot, entry_bar, forward_bars, params)` contract is preserved; it still receives `candidate.pivot` and a recomputed `entry_bar`, and is never called with empty `forward_bars`).
- **`scorecard.py`, `output.py`** — **additive only:** carry the new `entry_bar_weak_close` count / ledger column (R1-#2). The censoring/expectancy/Wilson math and the CSV/manifest writers are otherwise untouched.

### 5.1 Invocation-gap fix (folded in — operator-elected; resolves §3.7)
`swing diagnose shadow-expectancy` (and the other research diagnostics) fail `ModuleNotFoundError: research` from the installed entry point because the repo root is not on `sys.path` (only `PYTHONPATH=<repo root>` works). Add a shared helper in **`swing/cli.py`** (the single L2-lock file; no new `swing/` files):

```python
def _ensure_research_importable() -> None:
    """Prepend the source-tree root to sys.path so deferred `research.harness.*`
    imports resolve from the `swing` entry point (research/ is not an installed
    package). Idempotent; verifies the located root actually contains
    research/harness before inserting (R2-#2), so it is a safe no-op when the
    source tree is absent rather than silently shadowing site-packages."""
    import sys
    from pathlib import Path
    here = Path(__file__).resolve()
    # This project is installed editable (`pip install -e`), so swing/cli.py lives
    # in the source tree and parents[1] is the repo root containing research/.
    # Walk parents defensively and accept the first that actually holds research/harness.
    for root in here.parents:
        if (root / "research" / "harness").is_dir():
            if str(root) not in sys.path:
                sys.path.insert(0, str(root))
            return
    # No source tree on disk (true non-editable install): nothing to add. The research
    # diagnostics genuinely cannot run without the source checkout; the deferred import
    # will raise its normal ModuleNotFoundError, which is the honest outcome.
```

**The rule is MECHANICAL, not an enumerated list (Codex R1-#5):** call `_ensure_research_importable()` immediately before **every** deferred `from research.harness… import …` under the `diagnose` group. The operator chose to make the research diagnostics **turnkey**, so the acceptance check is a **grep**: `grep -n "from research.harness" swing/cli.py` enumerates every site, and each must be preceded by the helper call. As of this writing those sites are `aplus-sensitivity` (`aplus_sensitivity`, cli.py:4822), **`aplus-sensitivity-v2`** (`aplus_v2_ohlcv_evaluator`, cli.py:4883 — explicitly included; it was omitted from an earlier draft list), `minervini-recall` (`minervini_exemplar_recall`, 4931), `primary-base-recall` (`minervini_primary_base_recall`, 4964), `pattern-cohort` (`pattern_cohort_evaluator`, 5028/5032), `shadow-expectancy` (5084), and the two backtests (`double_bottom_w_backtest` 5160, `w_bottom_ruleset_comparison` 5238). Enumerating risks omission (as the earlier draft proved); the binding rule is "every `research.harness` import site under `diagnose` is guarded." This is the only `swing/` change and stays within the existing CLI's L2 footprint. A test asserts the helper makes `research.harness.shadow_expectancy.run` importable with the located root absent from `sys.path` (and is idempotent) **and that it only inserts a path that actually contains `research/harness`** (R2-#2 — so it cannot shadow site-packages with a wrong root); a second test greps `swing/cli.py` to assert no un-guarded `from research.harness` site remains under `diagnose`.

---

## 6. Substrate realities — scope / limitations updates (resolves §3.6)

These MUST be stated honestly in the corrected spec's risk section and surfaced in the run `summary.md`. They are **not** bugs; they are properties of the current log that bound what the fixed engine can show **today**.

1. **The log is `watch`-dominated — zero A+.** All 42 live signals are `bucket='watch'`. The engine therefore prices **H2 / H3 / H4**, not H1. **H1 accrues only as A+ signals fire** (rare: ~5 on a good night, often 0). The original framing "prices H1 at signal-pace" (original §1) was an **overstatement** — corrected: the engine prices the *watch* hypotheses fast; H1 still depends on A+ emission rate, faster than hand-trading but not signal-pace.
2. **The log is young/thin.** 4 pipeline runs, `2026-06-05 → 2026-06-08`, 219 forward observations (~2–3 sessions/walk). Nearly everything is `never_triggered` or open-at-horizon.
3. **Even after this fix, the current log prices ≈ zero — and that is correct.** Verified: for every live `(run, ticker)`, `candidate.pivot` sits **above** all available forward highs (e.g. WULF pivot 27.47 vs forward highs 25.21 / 26.20; VECO 65.03 vs 62.78; BULZ 56.09 vs 48.16 / 44.57). No ticker has broken out above its screening pivot in a 2–3 session window, so the recompute yields `never_triggered`, not a priced trade. **The fix unblocks the *mechanism*** (signals now reach the simulator and price when a breakout occurs); **priced samples accrue only as the log matures and breakouts happen.** This is a substrate-maturity limitation, not an engine fault.

### 6.1 Corrected success criteria (supersedes original §12 where it implied immediate H1 pricing)
- The funnel routes **correctly**: live signals land in `never_triggered` / open-at-horizon / per-hypothesis exclusions with honest counts — **not** 100% `no_canonical_detection`.
- A **real-shaped golden fixture** in which a forward high *does* exceed `candidate.pivot` prices a trade **end-to-end** (entry → legs → R bracket → scenarios), proving the mechanism.
- The engine **measurably accelerates** evidence **as the log matures** — the original "H1 triggered ≫ 1 live closed" target is retained as a *forward* expectation contingent on A+ emission + breakouts, **not** an assertion about the current log.

---

## 7. Testing strategy (supersedes the affected parts of original §9)

### 7.1 Fixtures from REAL emitter shapes — non-negotiable (resolves §3.5)
- **Forbid forcing `detection.pivot == candidate.pivot`.** Every fixture MUST set `detection.pivot != candidate.pivot`, with per-pattern `pivot_price` values **including `0.0`** for `cup_with_handle` / `double_bottom_w` and a real level for `vcp` / `flat_base` / `high_tight_flag`, mirroring the live shape.
- **Capture a sanitized real `(run, ticker)` group as a golden fixture** — e.g. BULZ run 89: 5 detections with geometric pivots `{49.89, 49.89, 0.0, 49.89, 0.0}`, `candidate.pivot = 56.09`, two identical frozen bars per detection, all `watch`. This fixture's expected outcome is **`never_triggered`** (no forward high reaches 56.09) — a regression guard that the live shape now routes honestly instead of `no_canonical_detection`.
- **Add a second real-shaped fixture where a forward high EXCEEDS `candidate.pivot`** (no live group does this yet) so a trade actually prices through the full simulator. Hand-verify the R bracket.
- **Mixed-first-trigger-session fixture** (regression guard for §1.3): a group where `cup`/`dbw` (pivot 0.0) trigger on bar 1 while `vcp` (pivot 49.89) never does, asserting the signal is **NOT** excluded as `inconsistent_trigger_state` (that reason no longer exists) and that the longest chain is selected as the bar source.
- Every fixture asserts `data_asof_date < observation_date` for all forward bars (the §4 no-look-ahead invariant).

### 7.2 `collapse.py` tests (rewrite)
- **Delete:** the pivot-match canonical test, the `no_canonical_detection` test, the `inconsistent_trigger_state` test.
- **Add:** longest-chain selection (tie-break low id); a differing-chain-length group selects the longest (prefix property); a differing-first-trigger-session group is **accepted** (not excluded); `inconsistent_detection_series` still fires on divergent OHLC for a shared date; **and (R1-#1) a group with a gappy/interior-missing chain (`A=[d1,d3]` vs `B=[d1,d2,d3]`) is excluded under `inconsistent_detection_series`** (the strengthened strict-prefix invariant), not silently accepted with a truncated bar source.

### 7.3 Entry-recompute tests
- First bar with `high >= candidate.pivot` is the entry; bars before it are skipped; no forward high reaching pivot → `never_triggered`; the detection-date bar (bar 1) is an eligible entry; `entry_fill = max(candidate.pivot, entry_bar.open)`.
- **(R1-#3) Zero-forward-depth:** a trigger on the **last** available bar → `insufficient_forward_depth` (per-hypothesis excluded), and `simulate(...)` is **not** called (assert the simulator is never invoked with empty `forward_bars`).
- **(R1-#2) `entry_bar_weak_close` flag:** an entry bar whose `close < candidate.pivot` is flagged in the ledger and counted in the scorecard, with **no** change to the entry/exit behavior (the trade still prices identically; the flag is annotation only).

### 7.4 Funnel / validate tests
- `no_candidate_pivot` (pivot `None`/`0.0`/`<=0`) routes to per-hypothesis `excluded`, distinct from `invalid_ohlc`; `insufficient_forward_depth` routes per-hypothesis (R1-#3); reconciliation invariant holds with the new reasons; removed reasons (`no_canonical_detection`, `inconsistent_trigger_state`) no longer appear in any vocabulary.
- **(R1-#5) Invocation grep test:** no un-guarded `from research.harness` import site remains under the `diagnose` group in `swing/cli.py`.

### 7.5 Preserved coverage + V1 limitation note
- All original §9 simulator/bracket/scorecard/censoring/reproducibility tests **stay green** (the simulator internals are untouched).
- A docstring/test note records the **no-close-confirmation** entry limitation (§2.2) as an explicit V1 choice.
- Invocation-gap test (§5.1): `research.harness.shadow_expectancy.run` imports with repo root absent from `sys.path`; helper is idempotent.
- L2-lock import-safety + banned-import source grep (`yfinance`, `schwabdev`, `swing.integrations.schwab`, `swing.data.ohlcv_archive`) **stays green**.
- Fast suite green on the merged head.

---

## 8. Verification appendix (re-runnable; for Codex + writing-plans)

Run against `~/swing-data/swing.db` read-only. Outputs captured 2026-06-09:

- **detection.pivot ≠ candidate.pivot, per pattern class** — BULZ/CIFR detections show geometric pivots `{49.89/25.55 (vcp/flat_base/htf), 0.0 (cup/dbw)}`; the joined `candidate.pivot` is `56.09 / 28.62`. → confirms §1.2.
- **Bars identical across a group's detections** — for every shared `observation_date`, all detections carry the same OHLC (`dates with >1 distinct OHLC across dets: {}`). → confirms §2.3 (bar source is class-agnostic).
- **Chain prefix property** — across 42 groups: differing chain lengths in **1** group, differing first-trigger sessions in **8** groups, **0** prefix violations. → confirms §2.3 (longest-chain == union, never truncates) and §1.3 (trigger-state gate must go).
- **First obs is on `detection_date`** — detection 1: `detection_date=2026-06-05`, `data_asof_date=2026-06-04`, first `observation_date=2026-06-05` (`sessions_since_detection=1`). → corrects the brief; confirms §4 (proof rests on `data_asof_date`).
- **`candidate.pivot` above forward highs on the live log** — WULF 27.47 vs {25.21, 26.20}; VECO 65.03 vs {62.78}; BULZ 56.09 vs {48.16, 44.57}; CIFR 28.62 vs {24.58, 24.51}; none would trigger. → confirms §6.3 (≈zero priced today, correctly).
- **Null/zero candidate pivots** — `255 / 7241`. → confirms §3.2 (`no_candidate_pivot` is a real, ~3.5% state).
- **Log span** — obs `2026-06-05 → 2026-06-08`, 219 rows, 4 distinct pipeline runs. → confirms §6.2.

The probe scripts used are `\tmp\probe.py` / `probe2.py` / `probe3.py` (gitignored; reproduce from the queries above).

---

## 9. Supersede / preserve ledger (against the original spec)

| Original element | Disposition |
|---|---|
| D1 (temporal-log substrate, read-only) | **Preserved** |
| D2 (single entry fill `max(pivot, open)`; `[realistic, favorable_reprice]` bracket) | **Preserved** — `pivot` is `candidate.pivot` throughout |
| D3 / D4 (core + Day-3 partial) | **Preserved** |
| D5 (126-session horizon) | **Preserved** |
| D6 (initial stop = entry-bar low; `degenerate_risk`) | **Preserved** |
| D7 / D12 (MA-trail from frozen bars; 10/20 proxy) | **Preserved** |
| D8 (no new schema) | **Preserved** |
| D9 (entry-bar same-bar-adverse ambiguity sensitivity) | **Preserved** — applies to the recomputed entry bar |
| D10 (four censoring scenarios) | **Preserved** |
| D11 (triggered-trade vs per-signal; trigger rate) | **Preserved** |
| §5.1 entry-timing = canonical detection's `triggered_open` event | **SUPERSEDED** — entry recomputed as first `high >= candidate.pivot` (§2.1) |
| §5.2–§5.8 simulator internals | **Preserved** |
| §6 canonical detection = `detection.pivot == candidate.pivot` | **SUPERSEDED** — canonical = longest-chain bar source; geometric pivot not consulted (§2.3) |
| §6 `inconsistent_trigger_state` gate | **SUPERSEDED / removed** (§1.3) |
| §6 `inconsistent_detection_series` gate | **Preserved + strengthened** — now enforces the strict date-prefix invariant, not overlap-only (§2.3; R1-#1) |
| §7.1 `insufficient_forward_depth` reason (reserved, unused) | **Now used** — zero-forward-depth entries route here (§2.1; R1-#3) |
| Entry-bar annotations (D9 `entry_bar_ambiguous`) | **Extended** — add `entry_bar_weak_close` diagnostic flag (annotation only; §2.2; R1-#2) |
| §7.1 funnel two-level structure + reconciliation invariant | **Preserved** |
| §7.1 reasons `no_canonical_detection`, `inconsistent_trigger_state` | **SUPERSEDED / removed** (§3.1) |
| §7.1 reason set | **Amended** — add `no_candidate_pivot` (per-hypothesis); see §3.2/§3.4/§3.5 |
| §7.2 scorecard | **Preserved** |
| §8 reproducibility | **Preserved** |
| §11 risks/limitations | **Amended** — add the H1-substrate, thin-log, and no-close-confirmation limitations (§6, §2.2) |
| §12 success criteria | **Amended** — funnel-routes-correctly + golden-fixture-prices + forward-accrual; not immediate H1 pricing (§6.1) |
| Invocation gap (not in original) | **Added** — `sys.path` repo-root helper in `swing/cli.py` (§5.1) |

---

## 10. Hard constraints honored

- **Surgical:** only the correction surface enumerated in §5/§5.1 (entry-recompute + collapse + validate + funnel-reason logic in `run.py`/`collapse.py`/`validate.py`/`constants.py`/`funnel.py`; additive `entry_bar_weak_close` annotation in `scorecard.py`/`output.py`; the single `swing/cli.py` importability helper), plus the affected fixtures/tests and this spec. The bracket math, censoring scenarios, scorecard expectancy/Wilson math, simulator internals (`simulator.py`/`bracket.py`), and the funnel two-level structure are untouched.
- **L2 lock:** the only `swing/` change is the existing `swing/cli.py` (the `_ensure_research_importable` helper + its call sites). No new `swing/` files.
- **No schema change** (v25 holds; harness stays a `mode=ro` consumer).
- **No new production dependency / no forbidden imports** (`yfinance` / `schwabdev` / `swing.integrations.schwab` / `swing.data.ohlcv_archive`); the L2-lock test stays green.
- **Fixtures derived from real emitter shapes** (§7.1) — the whole point.
