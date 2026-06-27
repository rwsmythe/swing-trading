# Shadow-Expectancy Engine — Entry/Join Correction — Brainstorming Dispatch Brief

**Audience:** Fresh Claude Code instance, no prior conversation context.
**Mission:** Brainstorm + spec a CORRECTION to the shipped shadow-expectancy engine. The first live run produced **zero priced trades** because the entry/canonical-detection join rests on a false premise. Design the fix (a surgical correction, not a redesign), converge it through Codex, and hand back a correction-design spec.
**Prepared:** 2026-06-09 by the orchestrator/evaluator instance.
**Phase:** copowers:brainstorming. Output → a new spec doc → (later) writing-plans → executing-plans.

---

## 0. Read first

1. `CLAUDE.md` — conventions (conventional commits; NO Claude co-author footer; NO `--no-verify`; TDD; Phase isolation; the Windows/ASCII gotchas). **Especially the gotcha "Synthetic-fixture-vs-production-emitter shape drift"** — this bug IS that gotcha.
2. **The shipped, converged design spec** — `docs/superpowers/specs/2026-06-08-shadow-expectancy-engine-design.md`. Most of it (D1–D8, D10–D12; the bracket, four censoring scenarios, scorecard, two-level funnel, reproducibility) is CORRECT and STAYS. The correction touches only **entry-trigger identification (D9 / §5.1) and canonical-detection selection (§6)** and the funnel reasons that depend on them.
3. **The implementation plan** — `docs/superpowers/plans/2026-06-09-shadow-expectancy-engine.md` (the shipped code mirrors it). The relevant modules: `research/harness/shadow_expectancy/collapse.py` (canonical-detection + consistency gates), `simulator.py` (entry), `io.py` (reader/joiner), `run.py` (orchestration), `funnel.py` (reasons).
4. The shipped code itself under `research/harness/shadow_expectancy/` + `tests/research/shadow_expectancy/`.
5. The evaluator charter session-log entry "2026-06-09 — first live run of P1" in `docs/research-director-context.md` (the diagnostic + the H1-substrate reality).

**Skill posture:** invoke `copowers:brainstorming` (wraps superpowers:brainstorming + a Codex adversarial review run to convergence). This is a CORRECTION of an existing converged spec — keep the scope surgical; do NOT re-open settled decisions (the bracket, censoring, scorecard, funnel two-level structure) unless the correction genuinely forces a change.

---

## 1. The bug (root-caused from the first live run, 2026-06-09)

`swing diagnose shadow-expectancy` ran against the live DB and returned **42 unique signals, 100% → `no_canonical_detection`, zero priced trades, empty scorecard.** (Funnel honesty surfaced it cleanly — not a silent failure.)

**Root cause:** the canonical-detection rule keys entry on `detection.pivot == candidate.pivot`. Against live data those are **different quantities** that never coincide:
- `detection.pivot` = `structural_anchors_json → evidence → pivot_price` is the **pattern-geometric** pivot. It varies per pattern class and is frequently `0.0` (observed: `double_bottom_w`, `cup_with_handle` write `pivot_price=0.0`; HTF/VCP/base patterns write a real level).
- `candidate.pivot` = the **screening** pivot on the `candidates` row.

Concrete live values (run 97 / eval_run 83, all `watch` bucket):
```
WULF  detection pivots {25.86, 0.0}   candidate.pivot 27.47
VECO  detection pivots {61.04, 0.0}   candidate.pivot 65.03
```
They are not the same number and are not meant to be. The shipped tests passed because their **synthetic fixtures forced `detection.pivot == candidate.pivot`** — so the false premise survived 6 writing-plans + 3 executing-plans Codex rounds (the reviews checked logic-vs-spec, not data shapes). Only the live run could falsify it.

**Substrate realities the run also exposed (document these in the corrected spec's scope/limitations):**
- All 42 signals are `watch` — **zero A+**. So even once fixed, the engine (against the current log) prices **H2/H3/H4**, not H1. H1 accrues only as A+ signals fire (rare). The "prices H1 at signal-pace" framing was an overstatement — correct it.
- The log is tiny/young: **4 runs, 2026-06-05→09, 219 forward observations** — ~5-session walks, so nearly everything is open-at-horizon. Needs months.

---

## 2. The proposed fix direction (a strong starting hypothesis — pressure-test it, don't rubber-stamp it)

**Re-adopt the design that writing-plans round 3 had and round 4 reverted: recompute the entry from `candidate.pivot` over the frozen forward bars.** The live data vindicates R3 over R4.

- **Entry trigger** = the first `pattern_forward_observations` row (for the signal's `(run,ticker)`) where `high >= candidate.pivot`. The forward observations are written by the observe step **strictly after `detection_date`** — so recomputing the trigger over them introduces **no look-ahead** (the detection-day bar is never in the forward chain). This was the R4 worry; the post-detection property dissolves it.
- **Bars** = the shared frozen forward-observation OHLC for the `(run,ticker)`. All detections for a `(run,ticker)` observe the same ticker/calendar with the same frozen bars, so the OHLC series is identical regardless of pattern class (the existing `inconsistent_detection_series` gate already enforces this). **Canonical-detection selection no longer needs `detection.pivot` at all** — pick any consistent detection deterministically (e.g. lowest `detection_id`) purely as the bar source; the *candidate* drives the entry.
- **Everything downstream is unchanged:** `entry_fill = max(candidate.pivot, entry_bar.open)`; `initial_stop = entry_bar.low`; the Day-3–5 partial, breakeven, maturity-staged MA trail, exits, the `[realistic, favorable_reprice]` bracket, the four censoring scenarios, the scorecard, the two-level funnel. The correction is surgical.

**This is a hypothesis for you to validate against the real data + harden through Codex — not a mandate.** If a better design emerges, take it.

---

## 3. Design questions the brainstorm MUST resolve

1. **Exact entry condition.** Is it purely `high >= candidate.pivot` on the first post-detection forward session? Or is a validity gate needed (the original temporal-log trigger was `high >= pivot AND close >= structural_low`)? Note: the executing-plans R2 fix REMOVED `candidate.initial_stop` usage (it's stale/unused), and the mechanical stop is `entry_bar.low` — so there is no candidate stop to gate on. Decide the trigger precisely and justify any gate.
2. **Canonical-detection / collapse redefinition.** With pivot-match gone, how is the bar source chosen, and what consistency must still hold (identical OHLC + identical first triggered session — or is `triggered_open` now irrelevant since we recompute)? Re-derive the `inconsistent_detection_series` / `inconsistent_trigger_state` / `no_canonical_detection` reasons: which survive, which are removed, which are renamed.
3. **Null/zero `candidate.pivot`.** Some candidates may carry a null or 0.0 pivot. Define the funnel handling (a new `no_candidate_pivot` exclusion? unattributed vs per-hypothesis?).
4. **No-look-ahead proof.** State explicitly why recomputing the trigger over the forward observations cannot enter on already-known information (the forward chain excludes the detection-day bar).
5. **Fixtures from REAL emitter shapes (non-negotiable).** The new/updated tests MUST reflect production reality: `detection.pivot != candidate.pivot`, per-pattern `pivot_price` including `0.0`, entry recomputed from `candidate.pivot`. Capturing a sanitized real `(run,ticker)` group from the live DB as a golden fixture is encouraged. A fixture that forces the two pivots equal is the bug — forbid it.
6. **Scope / limitations updates.** The corrected spec's risks/limitations must state the H1-substrate reality (watch-dominated log; H1 gated on rare A+ fires; engine accelerates the watch hypotheses primarily) and the young/thin-log caveat.
7. **The invocation gap (decide: fold in or defer).** The bare `swing diagnose shadow-expectancy` fails `ModuleNotFoundError: research` from the installed entry point (`research/` isn't an installed package + the repo root isn't on `sys.path`; it only works with `PYTHONPATH=<repo root>`). This affects ALL research diagnostics (`minervini-recall`, `primary-base-recall` too) — a pre-existing shared gap. Decide whether this correction also makes the research diagnostics turnkey (e.g. the CLI prepends the repo root to `sys.path` before the deferred import) or defers it to its own arc. If folded in, it stays within the single-CLI L2 footprint.

---

## 4. Hard constraints (the correction stays inside the shipped architecture)

- **Stay surgical.** Touch only entry/collapse/funnel-reason logic + the affected fixtures + the spec sections that change. Do NOT redesign the bracket, censoring, scorecard, or funnel two-level structure (D1–D8, D10–D12 stand).
- **L2 LOCK:** the only `swing/` change remains the (already-shipped) CLI registration; if the invocation-gap fix is folded in, it must live in that same `swing/cli.py` command (no new `swing/` files). Everything else under `research/harness/shadow_expectancy/` + tests + the spec.
- **NO schema change** (v25 holds; the harness is a read-only `mode=ro` consumer of the temporal log).
- **NO new production dependency / no forbidden imports** in the harness (`yfinance`/`schwabdev`/`swing.integrations.schwab`/`swing.data.ohlcv_archive`); the L2-lock test stays green.
- **Fixtures derived from real emitter shapes** (§3.5) — this is the whole point.
- Output a **correction-design spec** at `docs/superpowers/specs/2026-06-09-shadow-expectancy-entry-join-correction-design.md` that cross-references the original and states precisely which original decisions it supersedes (D9/§5.1/§6 + funnel reasons) and which it preserves.

---

## 5. Codex transport (this machine)

The MCP `codex` tools are dead in the VS Code extension. Drive Codex via the WSL CLI:
```
wsl -e bash -c 'export PATH="$HOME/.local/node22/bin:$PATH"; codex exec -s read-only --skip-git-repo-check -C "<repo root>" - < "<repo root>/.copowers-review-prompt.txt"'
```
PATH-prefix export REQUIRED; liveness `codex --version` → `codex-cli 0.135.0`; round 2+ via `codex exec resume --last -c sandbox_mode="read-only" --skip-git-repo-check`. The 5-round cap is suspended — run to convergence. **Persist each Codex RESPONSE** (verdicts + the final `NO_NEW_CRITICAL_MAJOR`) to a gitignored on-disk file. Instruct Codex to VERIFY the load-bearing data-shape claims against the real source/DB where it can (it has read-only repo access) — that is exactly what the original reviews lacked.

---

## 6. Done criteria + handoff

- A correction-design spec written, self-reviewed, and **Codex-converged** (`NO_NEW_CRITICAL_MAJOR`), with responses persisted.
- The spec resolves every §3 design question, mandates real-emitter fixtures (§3.5), and updates scope/limitations (§3.6).
- **Do NOT implement.** Brainstorming output is the spec; it returns for orchestrator QA, then routes to writing-plans → executing-plans as separate phases.
- Commit the spec (conventional; no co-author footer; verify `git log -1 --format='%(trailers)'` is `[]`). Return a short summary: the chosen entry/collapse design, the §3 resolutions, the Codex convergence verdict, and anything you pushed back on.
