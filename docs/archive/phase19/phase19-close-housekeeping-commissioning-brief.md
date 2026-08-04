# Commissioning Brief — Phase-19 close housekeeping bundle + close ritual

**From:** CHARC. **To:** the Phase-19 orchestrator (gen 2). **Committed:** 2026-07-06 evening HST (operator "proceed"). **Context:** all six Phase-19 arcs + D21/R3/R4 are FULLY CLOSED; the T4 terminal measurement gate is DISCHARGED. This bundle sweeps the riders + drift, runs the close ritual, and hands to the CHARC close audit.
**§3 verdict:** SUB-TRIPWIRE (scripts/ + docs/ + .gitignore + the standing close ritual; NO `swing/` production code, NO schema [v31], NO new module/process/dependency). The one production-code candidate (D22) is explicitly DEFERRED — see H5.

## §1 The housekeeping bundle

- **H1 — Rider R1: `scripts/comms_stop_hook.py` hardening back-port.** Source = the harness-template scaffold's Arc-C hardened Stop hook; swing's live copy predates it and can fail-CLOSED in edge cases (a loop risk). Port the three behaviors: strict-decode FAIL-OPEN; missing `stop_hook_active` → allow-stop; block ONLY on exact `is not False`. Measurement-neutral, harness-lane. Test what is testable (the decode/decision function, if factored); the hook's live behavior gets a manual sanity check (one deliberate turn-end with unread mail still triggers; a malformed-input case allows the stop).
- **H2 — Rider R2: `scripts/harness_probe.py` research-size ceilings** per the archived brief (`docs/archive/phase18/harness-probe-size-check-commissioning-brief.md`): report `exports/research/` + `research/harness/` sizes each run; ATTENTION at 500 MB / 200 MB (v1 ceilings — quiet at the current ~MB-scale baseline; a forward regrowth guard). ASCII output, read-only, report-never-delete — the §4.2 probe contract.
- **H3 — Rider-2: the 19-C runbook capture-timing softening.** In `docs/runbooks/weeknight-pipeline-scheduled-task.md` §Schedule rationale, replace the ragged-inflow claim with RD's verbatim sentence: *"a capture-timing correlation was tested and not supported (19-D Task 8); the 17:30 default stands on operational grounds."* (RD owns the original hypothesis and supplied the wording.)
- **H4 — Drift disposition (banked 2026-07-04):** add `.gitignore` entries for `exports/research/shadow-expectancy-*/` (28+ untracked dirs, accruing nightly now) and `.codex/`; **`AGENTS.md`** — read it and adjudicate: project-general Codex-review instructions → TRACK (commit it); personal/local tooling config → gitignore; state the call + rationale in the return; **`diag_5_launch_context.py`** — retire (untracked, the #5 diagnostic; #5 closed at 19-B; simple delete).
- **H5 — D22 EXPLICITLY DEFERRED to Phase-20 scoping.** The ungated general `discrepancy resolve` fix is real `swing/` production code (a pending-state gate + tests) and does NOT belong in a housekeeping bundle; the register entry stays OPEN and rides the Phase-20 proposal. Do not scope-creep it in.

## §2 The close ritual (standing convention + the NEW D21 sweep-safety step, BINDING)

1. **§4.3 archival sweep:** Phase-19 dead dispatch artifacts (commissioning briefs, plans, per-arc transcripts, handoffs) → `docs/archive/phase19/`. **D21 SWEEP-SAFETY (BINDING, first exercise since it was written):** BEFORE committing the sweep, grep `tests/` + `swing/` + `scripts/` for every moved filename (repath or defer any referenced file; check retirement markers on any test reference per the RD standard); AFTER the sweep commit, re-run the FULL fast suite; the close's "suite green" claim must postdate the close ritual's LAST commit.
2. **CLAUDE.md maintenance:** line-3 re-compaction (the Phase-19 summary leads; Phase-18 collapses to a one-line pointer) + baseline refresh (suite ~9035 post-bundle, schema v31, the streak count re-verified by trailer scan) + **fold the D4 §Architecture refresh** (the register notes §Architecture omits 8 shipped packages — fold at this compaction per the standing D4 disposition).
3. `orchestrator-context.md` in-flight refresh; the comms/session registry tidy if any dead gens linger.
4. `harness_probe.py` run (post-H2, so the new ceilings execute) — expect zero ATTENTION.

## §3 Gates + handoff

- Suite runs: after H4's `.gitignore`/tracked-config changes (the inline-edits-need-suite-run memory) AND after the archival sweep (D21) — these may be the same run if sequenced sensibly; the FINAL suite run postdates the LAST close commit.
- Trailers [] throughout; pathspec commits (three roles share main).
- Execution mode: orchestrator's call — H3/H4 + the ritual are inline-appropriate; H1+H2 together fit one small implementer dispatch (`implementer-sonnet-high` or `opus-high`, your selection) with Codex review-fast (harness scripts, not measurement code).
- **Return report to `charc,rd` after your QA** — then **the CHARC close audit runs on the post-housekeeping HEAD** (binding-gates verification: suite/ruff/schema/streak/probe + per-arc roster + tripwire-false-negative check + self-critique), and the operator receives the close verdict.
