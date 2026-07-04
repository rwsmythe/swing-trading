# Orchestrator handoff — 2026-07-04 — Phase 19, the 19-D/E/F parallel batch

**From:** the Phase-19 orchestrator generation `1a0ae071` (shipped 19-A, D21/R3/R4, 19-B, 19-C).
**To:** the next orchestrator generation. **Reason:** clean arc-boundary handoff before the 3-arc parallel batch (context-capacity discipline; QA rigor over momentum). Operator-approved 2026-07-04.
**Bootstrap first:** `scripts/orchestrator_bootstrap.md` → `docs/orchestrator-context.md` → this file. **Main HEAD at handoff: `e07016cf`. Schema v31. All this session's commits are trailer-clean (streak intact).**

---

## What shipped this session (Phase 19; do NOT re-derive — this is orientation)

- **19-A — coverage_gaps CALIBRATION-C trailing-delisting fix — MERGED `fadc193d`.** clause-2b (skip-warning-explained) evaluated INDEPENDENT of clause-1; live-DB gate witnessed RED(100 gaps)→GREEN(0); RD plan-stage + merge-blocking QA PASS. Killed the CNTA false-RED.
- **D21 (a main-health regression I caught during 19-A)** — Phase-18 §4.3 archival sweep broke 6 research-brief-path tests. **R3** repathed them (`c2ee1d98`), **R4** retired the 6 brief-coupled assertion blocks per RD's arc-lifecycle ruling (`2d626b27`). D21 CLOSED.
- **19-B — launch-context anchor-consistency + lease-or-silent + broken-context guard (the #5 root fix) — MERGED `3234f19a`.** The #5 drumbeat-false-RED saga ENDED (operator witness both halves PASS). Follow-up: the session comms-isolation belt was flaky under `-n auto` (whole-tree freeze vs live comms churn → 16 spurious per-worker errors); **narrow-fixed `44b3bbd9`** (key on the `_LATEST_JSON_POINTER` push signature, added-inbox-only) + banked a CLAUDE.md gotcha.
- **19-C — weeknight-pipeline Windows Scheduled Task — code MERGED `e3f1a442`; runbook witness-fixes `e07016cf`.** `swing pipeline run --skip-if-running`→exit 75 + an exit-78 code-tree guard + a C3 non-interactive-auth wiring test; a PowerShell wrapper (process-tree-kill timeout, always-one-line result) + idempotent register/unregister (Interactive-only, S4U hard-refused) + a runbook. CHARC confirmed C1–C6. **Witness stage (a): all five components PASS** (register+C1, real scheduler fire run 121, collision demo + a bonus stale-lease-recovery witness, C3 no-hang run 124, restore). **A false "lease self-heals" premise (CHARC's C4 note, folded into plan §10) was review-caught + corrected** (a SIGKILL'd run's `running` row re-blocks via the unique index until `force-clear`; backstopped by tool_health pipeline-freshness RED — NOT self-healing; the design stands; CHARC owns the error). 3 witness runbook defects fixed (`e07016cf`, F1/F2/F3).

### 19-C stage (b) — PENDING (the only open 19-C item)
**The first real weeknight fire, Monday 2026-07-06 17:30 HST, CLOSES the arc.** Nothing needed until then. When the operator confirms the Monday fire ran clean, POST the arc-close to `charc,rd`. (CHARC tracks it in its state.)

---

## YOUR ASSIGNMENT — the 3-arc parallel batch (commissioned + operator-pre-authorized 2026-07-04; briefs committed; NOT yet dispatched)

> **The dispatch inbox messages were already read/acked by the prior generation, so YOUR inbox will NOT re-show them. THIS handoff + the committed briefs carry the dispatch.** Each carries the operator's prior approval (the amended dispatch-authority model): treat as operator-hand-carried commissions. All THREE are file-disjoint from each other + from 19-C (whose only open item is the Monday fire) → run in PARALLEL, separate worktrees, sequence merges as they converge. Each: writing-plans dispatch → your QA → the named plan-stage review → executing → your QA → merged-head no-false-green → the named witness → merge. **Announce each cell before spawn (the recipe handshake).**

### 19-D — shadow-engine hardening bundle
- **Brief (durable tracker):** `docs/shadow-engine-hardening-19d-commissioning-brief.md`. **Read in full.**
- **3-part bundle:** (a) risk-unit FLOOR / discriminator — the `degenerate_risk` guard at `simulator.py:103` is a ZERO-floor (entry_fill ≤ initial_stop), so VSTS's ~0.25%-of-price rps passed and a normal +7.9% move priced +27.3R; `entry_bar_ambiguous` is true-by-construction on daily bars (165/165) → cannot gate. BINDING distinction: **VSTS caught, TVTX (+7.84R @ 1.4% risk, tight-but-REAL) survives unchanged.** (b) epsilon-tolerant READER — clamp sub-threshold ragged-shape bars at the read boundary BEFORE `validate_bars` (`validate.py:32-48`), reader-side ONLY, log/archive verbatim, emit a clamped-bar counter. (c) capture-timing trace (analysis-only; incl. the CROSS-VENDOR Schwab pricehistory rejections from run 123 — the ragged-bar family is cross-vendor, not yfinance-only).
- **Gates:** RD AUTHORITY IS BINDING — RD plan-stage review RULES the semantic choices (floor form+value, epsilon threshold, exclude-vs-winsorize, outlier posture; the plan PROPOSES from the LIVE distribution with evidence); RD merge-blocking QA; **RD's pre-committed T4 confirmatory re-read = the terminal gate.**
- **Scope/locks:** SUB-TRIPWIRE — research/harness ONLY, **NO `swing/` file, NO schema.** Pure-recompute EXACTLY preserved (read-only conn, zero DB writes); no archive mutation; 0026 frozen criteria untouched. **Fixture discipline BINDING (brief §4):** REAL emitter shapes (actual VSTS/TVTX geometry, real DINO/CALY ragged bars from the live archive) — never values built to satisfy the premise; pre/post arithmetic for every discriminator.
- **Cells:** writing-plans `implementer-opus-xhigh` (measurement-policy design density), executing `implementer-opus-high`.

### 19-E — Day-3-5 partial-trim advisory
- **Brief:** `docs/day35-partial-advisory-19e-commissioning-brief.md`. **Read in full.**
- **Scope:** a calendar-triggered partial advisory (day 3–5, entry day = day 1) in the recommendations surface; engine-aligned defaults (day-3-5 / 50% / close>entry). **DST 4.B fork RESOLVED by the operator: ADD-ALONGSIDE** (the existing +1R trigger keeps its exact semantics; nothing deleted). `advisory.py:145`'s docstring says "DST D.2 calendar trigger banked for V2" — **this arc IS that V2; cite it in the plan.**
- **Tripwire:** the `swing/trades/advisory.py` phase-isolation carve-out is DISCHARGED IN-BRIEF (conditions E1–E4: purely additive; day-counting sessions-vs-calendar = RD RULES at plan review; `has_been_trimmed` reuse + window-closes-after-day-5; rides the existing advisory render path).
- **Gates:** RD plan-stage review (trigger/parity semantics); **BINDING operator GUI witness incl. the UNSEEDED-default state** (the seeded-gate-masks-default lesson).
- **Cells:** writing-plans `implementer-opus-high`, executing `implementer-opus-high`.

### 19-F — cash-review orphan-resolve
- **Brief:** `docs/cash-review-orphan-resolve-19f-commissioning-brief.md`. **Read in full.**
- **Diagnosis COMPLETE + banked in the brief:** the unresolvable dashboard cash-review badge = discrepancy 73 → a raw-deleted cash movement (id 5); **NOT D16**; the badge predicate is correct + untouched. The fix is the MECHANISM for all future raw-delete orphans (orphan-tolerant discrepancy resolution).
- **PLAN STEP 1 IS MANDATORY:** reproduce the exact live failure against discrepancy 73 READ-ONLY before writing the fix section.
- **Tripwire:** carve-out DISCHARGED in-brief (F1–F4: append-only SELECT-then-UPDATE; **NO schema — if the plan concludes a CHECK-enum widening is genuinely needed, that IS a schema tripwire → STOP and route back to CHARC**). Scope = the recon service (`swing/trades/schwab_reconciliation.py`) + reconcile web/CLI + tests.
- **Gates:** RD plan-stage LIGHT (audit-trail semantics; no ledger/measurement change); **BINDING operator witness = the LIVE HEAL** — the operator resolves 73 in the real GUI and the badge disappears.
- **Cells:** writing-plans `implementer-opus-high`, executing `implementer-opus-high`.

---

## Process learnings this session (carry forward)

- **The dispatch machinery worked well:** each arc = writing-plans sub-agent → orchestrator QA-on-disk (convergence from the REAL `.copowers-findings.md`, never the self-report) → the plan-stage director review (route to the OWNING director; the plan makes the decision, the director rules) → executing sub-agent (review-strong + codex-auto-review) → QA → rebase-onto-main + `--ff-only` + **merged-head no-false-green suite** → the binding operator/live witness → merge. Hold to it.
- **Fold director rulings into the plan (a short amendment commit) before the executing dispatch** — did this for 19-B (RD 8.1(b)) and 19-C (§10 resolutions). Keeps the plan the durable tracker.
- **`role_mail` MUST run from the MAIN repo dir** — a QA `cd` into a worktree persists the Bash cwd and misdelivers director mail to the worktree's gitignored `comms/` tree (I hit this early; re-anchor `cd /c/Users/rwsmy/swing-trading` before every post). Memory `feedback_role_mail_run_from_main_repo`.
- **The merged-head suite is genuinely load-bearing** — it caught the 19-B belt flake (16 spurious xdist errors) AND is where a cross-arc/main-health regression surfaces. Always READ the actual result (no-false-green).
- **A false premise can originate in a director note and propagate into a binding plan** (the 19-C C4 "self-heals") — the review + the QA layers caught it. Directors own + correct their own errors gracefully; don't paper over.
- **Operator-procedure code snippets get a DRY-RUN before shipping** (the 19-C F1/F2/F3 runbook bugs — both snippets had never been executed). New discipline.
- **Push is NOT done per-arc** — `origin/main` was ~293 behind at 19-A; this repo is local-first. Don't push unless the operator asks.

## Standing facts

- **Amended dispatch-authority model is LIVE:** a director's action-bearing inbox message (a commissioning brief/dispatch) carries the operator's PRIOR approval — act as an operator-hand-carried prompt. `decision_request` stays operator-only.
- **Directors:** CHARC (`docs/charc-state.md` = its single-source state) + RD. RD owns measurement/alarm semantics (19-D/E gates); CHARC owns tripwire/architecture (19-C's confirm; 19-F's schema-widening STOP). coa-chess is its OWN repo — do NOT touch.
- **Suite:** 8942 fast green at the 19-C merged head (`e3f1a442`; docs-only since). Cells library `.claude/agents/implementer-*.md`. Dispatch SPOF `docs/implementer-dispatch-recipe.md`. Phase-19 board `docs/phase19-scope-charc.md`.
