# Commissioning Brief — 19-E: Day-3-5 calendar partial-trim advisory (add-alongside)

**From:** CHARC. **To:** the Phase-19 orchestrator. **Arc:** 19-E ([`phase19-scope-charc.md`](phase19-scope-charc.md)). **Committed:** 2026-07-04 HST. **Demand:** operator-originated 2026-07-03 (VSTS trade 17 — the Day-3-5 partial step never surfaced; +1R = +17% on the wide-stop geometry, unreachable in the window). RD interest: cohort parity (the live standard cohort must be able to execute what the engine measures under H1).
**OPERATOR DECISION (2026-07-04, in-chat): ADD-ALONGSIDE** — the calendar partial advisory joins the existing +1R trim-into-strength; nothing deleted.
**§3 verdict: CARVE-OUT tripwire (`swing/trades/advisory.py`) → this brief embeds the CHARC architecture pass. GO with conditions E1–E4 (§2). NO schema (v31), NO new module, NO dependency.**

## §0 References (CHARC-verified on disk 2026-07-04)

- `swing/trades/advisory.py:135-162` — `suggest_trim_into_strength`: fires on `r >= ctx.config.trim_first_r_trigger` (default 1.0) AND `not ctx.has_been_trimmed`; the docstring says it outright: "**DST D.2 calendar trigger banked for V2**" — this arc IS that V2. `:384` the aggregator append site. `:122-133` `suggest_time_stop` — the existing day-counting precedent (`(as_of_date − entry_date).days`, CALENDAR days).
- Engine constants (the parity source): `research/harness/shadow_expectancy/constants.py` `PARTIAL_SESSION_N=3` / `PARTIAL_PCT=0.5`; simulator step 2b takes the partial when the day-3 close > entry. **The engine counts SESSIONS.**
- Config: `swing/config.py:102` `trim_first_r_trigger` (+ its `__post_init__` validation pattern to mirror for new fields).
- RD's demand mail (2026-07-03, capability-demand thread) + DST transcription `reference/methodology/dst-take-profit-and-trail.md` D.2 / 3e.8 §4.B.

## §1 The problem

The measured strategy (engine: mechanical day-3 50% partial when close>entry) and the GUI-prompted strategy (+1R-only trigger) diverge at exactly this step; on wide-stop geometries the +1R advisory is effectively dead — a standard-cohort operator following the queue CANNOT execute the ruleset H1 is measured under. The operator personally missed the VSTS partial.

## §2 CHARC architecture pass — conditions (binding)

- **E1 — PURELY ADDITIVE:** a NEW advisory function (e.g. `suggest_partial_day_window`) + its aggregator wiring + NEW config fields with validation. NO behavior change to any existing advisory (`trim_into_strength` keeps its exact semantics — the operator chose add-alongside); the carve-out touches `advisory.py` (+ config) ONLY — no other `swing/trades` file.
- **E2 — defaults aligned with the ENGINE:** window day 3–5 (entry day = day 1), 50%, close>entry-price condition. **Day-counting semantics (sessions vs calendar days) is a PLAN design point RD RULES** — the engine counts sessions (the parity argument); `suggest_time_stop` counts calendar days (the in-file precedent); the plan proposes with the parity rationale, RD rules at plan review.
- **E3 — suppression + coexistence:** reuse `ctx.has_been_trimmed` (any prior trim suppresses — same as +1R); the window CLOSES after day 5 (no stale nag). Simultaneous-fire with +1R (a day-3 trade that is also ≥+1R) = both render as distinct labeled rules OR an explicit precedence — plan proposes, RD reviews, the operator sees it at the witness.
- **E4 — the surface rides the EXISTING advisory render path** (a new `rule` string through the existing `AdvisorySuggestion` plumbing); if ANY template/VM change proves necessary, it stays within the existing advisory surface — no new page, no base-VM field (the every-base-VM-or-500 gotcha).

## §3 Discriminating tests (pre/post arithmetic computed — `feedback_regression_test_arithmetic`)

Day-2 + close>entry → NO fire (window not open) · day-3 + close>entry → FIRES (pre-fix: nothing fires below +1R) · day-3 + close≤entry → NO fire · day-6 → NO fire (window closed) · day-4 + already-trimmed → suppressed · day-3 AND r≥1.0 → the E3-ruled coexistence behavior, asserted exactly · wide-stop geometry (the VSTS shape: +1R unreachable, day-3 reached) → the calendar advisory fires where the old surface stayed silent — the arc's reason-to-exist test.

## §4 Gates

1. **RD plan-stage review** (trigger semantics: day-counting, close>entry definition, coexistence — cohort parity is RD's stake; he asked to review).
2. review-strong + codex-auto-review; suite + ruff + merged-head no-false-green.
3. **BINDING operator GUI witness** (advisory surfaces are HTMX/browser — the TestClient-blind gotcha family): witness BOTH a state where the advisory fires AND the unseeded default (the `feedback_seeded_gate_masks_default_state` memory); a live in-window trade if one exists, else seeded + default both.
4. The ORCHESTRATOR posts the return report to `charc,rd` AFTER its QA.

## §5 Sizing + dispatch recommendation

Small. CHARC recommendation: **writing-plans `implementer-opus-high`** (bounded design points), **executing `implementer-opus-high`** (production `swing/trades` surface + GUI witness prep). Orchestrator selects + announces.
