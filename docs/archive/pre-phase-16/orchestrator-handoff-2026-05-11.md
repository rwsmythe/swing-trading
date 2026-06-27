# Orchestrator handoff — 2026-05-11 mid-session

You are taking over as orchestrator for the Swing Trading project mid-session. The prior orchestrator handed off after 3e.8 Bundle 1 shipped + reached a planned context-budget breakpoint. **Two more dispatches are queued + specified for you to draft + dispatch:** 3e.8 Bundle 2 (sell-side advisories §4.B + §4.K + §4.D) + 3e.8 Bundle 3 (Option δ hybrid — §4.A.bis maturity-stage MA hint + new M.2 R-multiple stop-tighten hint).

This handoff is **not** a session-restart context recovery (the prior orchestrator was operating well; just budget-managing). The work-in-progress + post-Bundle-1 state is fully documented in committed files + this brief; you should be able to bootstrap quickly.

## ⚠ Critical bootstrap framing

**claude-mem is DISABLED** for the operator's ~1-week experiment window (started 2026-05-10). You will NOT see SessionStart claude-mem injection blocks. Do NOT attempt `mcp__plugin_claude-mem_mcp-search__*` or `mem-search` skill — both will fail. Auto-memory dir (MEMORY.md + linked files) IS still loaded by the harness. See `~/.claude/projects/c--Users-rwsmy-swing-trading/memory/feedback_claude_mem_hook_blocks_disabled.md` for full re-enablement criteria.

## Step 1 — Read these in order

1. **`docs/orchestrator-handoff-2026-05-10.md`** — yesterday's bootstrap brief; full project framing remains valid. Skim "Project state at handoff" + "Operator preferences" sections.

2. **This brief end-to-end** — captures everything new since yesterday's bootstrap.

3. **`docs/3e8-sell-side-advisories-investigation.md`** — 746-line investigation doc (only sections you need: §1 current advisory surface enumeration; §3 gaps; §4 recommendations; §5 Tier-3 #6 advisory matrix; §6 operator decision points). Skim §2 doctrine reconciliation if needed for context. Total ~250-400 lines of relevant content.

4. **`reference/methodology/dst-take-profit-and-trail.md`** — DST sell-side rules transcribed by prior orchestrator from PyMuPDF extraction. **Three CONFIRMED-with-correction + two NOT-PRESENT-IN-SOURCE + two NEW rules surfaced.** Critical for Bundle 2 + Bundle 3 default re-anchoring.

5. **`reference/methodology/minervini-sell-side-rules.md`** — Minervini sell-side rules; operator reviewed TLSMW Ch 13 p. 296. **Only M.2 CONFIRMED-QUANTITATIVE; rest are BRIEF-MENTION-NO-DETAIL or NOT-PRESENT-IN-AVAILABLE-SOURCES.** M.2 contains the R-multiple-of-stop-loss anchor for Bundle 3's NEW stop-tighten advisory.

6. **`docs/phase3e-todo.md`** — search for "## 2026-05-10 3e.8 disposition + commission bundles" section. Full disposition matrix for the 14 §6 decision items + Bundle 1 SHIPPED entry + Bundle 2/3 dispatch-ready specs + 2 new V2 watch items from Bundle 1.

7. **`docs/3e8-bundle-1-advisory-parity-brief.md`** — completed Bundle 1 brief (template for your Bundles 2 + 3 briefs).

## Step 2 — Standard bootstrap verification

```bash
git log --oneline -10
git status
git worktree list
```

Expected: HEAD `<post-handoff-commit>` on main; in sync with origin; working tree clean (or just this handoff brief + housekeeping pending commit). Worktree husks expected at:
- `.worktrees/polish-bundle-2026-05-10/` (ACL-locked Phase 6/7/8 pattern)
- `.worktrees/3e16-cadence-review-trade-summary/` (same pattern)
- `.worktrees/3e10-dark-theme/` (same pattern)
- `.worktrees/3e8-sell-side-advisories-investigation/` (same pattern)
- `.worktrees/3e8-bundle-1-advisory-parity/` (same pattern; just merged)

Operator-elevated `cleanup-locked-scratch-dirs.ps1` handles all in one batch — does NOT block dispatch work.

## Step 3 — Confirm operator workflow + preferences

**Operator preferences (durable, restated for emphasis):**

- **Implementer-dispatch is the default** per `~/.claude/projects/c--Users-rwsmy-swing-trading/memory/feedback_orchestrator_vs_implementer_execution.md`. Crossover to orchestrator-inline only when orchestrator's token cost < implementer's spinup-plus-task cost.
- **Once operator-witnessed gate passes, integration merge is orchestrator action.** Do NOT ask "shall I proceed with merge."
- **Worktree-isolated dispatch briefs MUST specify `.worktrees/<branch>/` path explicitly** (binding convention 2026-05-09).
- **Implementer runs adversarial-critic** (per orchestrator-context "Executing-plans dispatch convention" 2026-05-02). Marker file `c:/Users/rwsmy/swing-trading/.copowers-subagent-active` is created at dispatch start, removed by implementer pre-Codex-invocation.
- **Brief-recommended technical micro-decisions need empirical pre-verification** before locking.
- **Multi-choice format for design questions** (operator preference; provides clean choice surface).

## Step 4 — Bundle 2 brief drafting (your first task)

### 4.1 Bundle 2 scope (operator-locked + post-§4.G doctrine-corrected)

**Three new sell-side advisory rules** to land via single dispatch:

| Recommendation | Rule | Doctrine anchor (post-§4.G) | Default re-anchoring needed? |
|---|---|---|---|
| §4.B | Trim/sell-into-strength advisory | DST D.2 (50% on Day 3-5 calendar window) — peoplewish-attributed | YES — original 3e.8 default (+1R first-time / 25%) is operator-policy hybrid; doctrine-faithful would be Day-3-5 calendar 50% |
| §4.K | planned_target_R hit advisory | M.2 + DST D.2 sell-into-strength principle | NO — straightforward; default fires when r_so_far ≥ trades.planned_target_R |
| §4.D | Parabolic-extension detector | DST D.7 (Realsimpleariel >7x ADR above 50SMA) | YES — original 3e.8 defaults (25%/5d/15%) are arbitrary; doctrine-faithful = >7x ADR above 50SMA |

**Bundle 2 effort:** ~8-10 hr (per phase3e-todo). Advisory-message-only; no V2.1 §VII.F.

### 4.2 §4.B trigger-decision lock (NEW — operator-pending)

Bundle 2 brief drafting needs **one operator design question locked** before dispatch:

> Should §4.B trim advisory use:
> - **(a) R-multiple trigger** (3e.8 original; +1R first-time at 25% trim) — operator-policy hybrid
> - **(b) Calendar trigger** (DST D.2-faithful; Day 3-5 at 50% trim)
> - **(c) Both triggers** (cfg-tunable; operator picks per-trade or sets a default)
> - **(d) Hybrid trigger** (e.g., "+1R OR Day 3 — whichever comes first" at 25% trim)

Prior orchestrator's recommendation in the disposition matrix was implicit (a) but flagged the doctrine divergence in Bundle 2's phase3e-todo entry. Surface this design question to operator before drafting Bundle 2 brief.

### 4.3 §4.D threshold-decision lock (NEW — operator-pending)

Similarly:

> Should §4.D parabolic detector use:
> - **(a) 3e.8 original defaults** (25% in 5 days + 15% above 20MA) — arbitrary
> - **(b) DST D.7 doctrine-anchored** (>7x ADR above 50SMA) — Realsimpleariel-attributed
> - **(c) Both, cfg-tunable** (defaults to D.7; operator can override)

Prior orchestrator-recommendation was implicit (b) per the doctrine-anchor stated in phase3e-todo. Surface to operator.

### 4.4 §4.K — no design lock needed; straightforward

Trigger: `r_so_far ≥ trades.planned_target_R`. Cross-references existing schema (planned_target_R already on trades table per Phase 8 ship). Implementation likely ~2 hr standalone but bundles trivially with §4.B + §4.D.

### 4.5 Bundle 2 brief shape

Mirror `docs/3e8-bundle-1-advisory-parity-brief.md` structure. Three task families (one per recommendation). Worktree branch `3e8-bundle-2-sell-side-advisories`. BASELINE_SHA = post-handoff-commit (your commit of this brief + housekeeping). Adversarial review setup identical (implementer runs).

**Bundle 1 watch-item to pre-empt in Bundle 2 brief:** the new rules will compose into the same 5-path advisory composition surface that Bundle 1 hand-duplicated. Either (a) propose the V2 shared composer extract as part of Bundle 2 (scope-creep) OR (b) explicitly mirror the same hand-duplication pattern across the new rules (consistent with Bundle 1's accept-with-rationale on R1 Minor #1). Recommend (b) for Bundle 2; bank the V2 extract as a separate dispatch when operator wants to address the drift risk.

## Step 5 — Bundle 3 brief drafting (after Bundle 2 ships)

### 5.1 Bundle 3 reframed to Option δ (operator-locked 2026-05-10)

**TWO complementary advisories addressing different operator questions:**

1. **§4.A.bis** — Maturity-stage MA hint (operator-policy per Tier-3 #6)
   - Trigger: read `maturity_stage` from active snapshot
   - Emit: `"Maturity stage {stage} → recommended trail-MA: {20MA | 10MA}"`
   - Doctrine basis: project-policy hybrid of M.2 + DST D.3
   - Effort: ~2-3 hr

2. **NEW: M.2 R-multiple stop-tighten hint** (doctrine per TLSMW Ch 13 p. 296)
   - Trigger: `r_so_far >= cfg.stop_advisory.tighten_at_r_multiple` (default 2.0R, operator-tunable; rough match to TLSMW 7%/20% example = 2.86R)
   - Emit: `"At +X.YR (≥{K}× stop) — Minervini M.2: consider moving stop to breakeven OR tightening trail to lock in majority of gain"`
   - Doctrine basis: directly TLSMW-anchored (verbatim quote in Minervini methodology file)
   - Effort: ~1-2 hr

**Bundle 3 total effort:** ~4-5 hr. Both advisory-message-only.

### 5.2 Bundle 3 brief shape

Mirror Bundle 1 + Bundle 2 brief structure. Worktree branch `3e8-bundle-3-maturity-and-stop-tighten-hints`. Two task families (one per advisory). Wait for Bundle 2 to ship before drafting (so implementation learnings inform Bundle 3 brief).

## Step 6 — DHC operational context

**DHC current state per snapshot 2026-05-08T11:24:23:**
- `open_R_effective`: 0.85
- `open_MFE_R_to_date`: 0.88R
- `maturity_stage`: pre_+1.5R
- Trail-MA decision per §5.3 §6.2 Case A: keep 20MA trail; ignore 10MA suggestion (trade has not yet proven itself)

DHC has been operationally framed as the urgency driver for the entire 3e.8 investigation. Operator has the §5.3 case matrix to apply at next pipeline run. Bundle 1's advisory parity ship + Bundle 3's maturity hint advisory are both designed to reduce operator's mental-mapping load on this exact decision moment.

## Step 7 — V2 watch items banked from Bundle 1

Two architectural concerns surfaced in Bundle 1's Codex R1 Minors that you should be aware of when drafting Bundle 2 + Bundle 3 briefs:

1. **Advisory composition hand-duplicated across 5 paths.** Bundle 2 + Bundle 3 will add new rules to this same surface. Brief-locked discipline (mirror dashboard composition) means the hand-duplication grows. V2 candidate: shared composer extract.

2. **`build_open_positions_expanded` cache I/O during SQLite read-snapshot.** Bundle 2 + 3 don't introduce new lock-window concerns but the canonical pattern divergence persists.

Both items are banked at the bottom of `docs/phase3e-todo.md` as "## 2026-05-11 V2 watch items banked from 3e.8 Bundle 1 ship."

## Step 8 — Other backlog items + dispatched-already context

The non-Bundle-2/3 backlog (per the most recent Bundle-1-ship-state of phase3e-todo):

| ID | Status | Disposition |
|---|---|---|
| §3e.8 §4.A full | Banked-without-gate | Revisit after Bundle 3 §4.A.bis evidence accumulation (n≥10 closed trades) |
| §3e.8 §4.C / §4.C.bis | Banked-without-gate | Triggers: n≥10 closed sub-A+ trades OR specific trade time-stopped prematurely |
| §3e.8 §4.G transcription | COMPLETE within available sources | Think & Trade unavailable; M.4 7-week rule unverifiable |
| §3e.8 §4.H | Deferred-with-second-source-gate | Single-source-Q sector RS rule |
| §3e.8 §4.I | Deferred-with-second-source-gate | Trichotomy resolved to OUTCOME 2 (M.6 qualitative) |
| §3e.8 §4.J | Deferred-with-second-source-gate | Single-source-Q combined-violation rule |
| Process formalization | Below-current-priority backlog item | Orchestrator-vs-implementer execution-mode policy |
| Worktree husks | 5 husks accumulated this session | Operator-elevated cleanup-locked-scratch-dirs.ps1 (single run handles all 5) |

## Step 9 — Your first action

1. Run the standard bootstrap verification (Step 2) + read the files in Step 1 order.
2. Surface the §4.B + §4.D design questions (Step 4.2 + 4.3) to operator via AskUserQuestion (multi-choice format per operator preference).
3. After locks, draft Bundle 2 dispatch brief mirroring `docs/3e8-bundle-1-advisory-parity-brief.md` shape.
4. Commit + push the brief.
5. Provide the paste-ready implementer prompt + pre-dispatch checklist.
6. Stand by for Bundle 2 implementer return.
7. Bundle 2 ship → housekeeping → repeat for Bundle 3.

**Do NOT redo the §4.G transcription work** (DST is fully done; Minervini is operator-reviewed-TLSMW-only). Do NOT re-litigate the 14 §6 dispositions (operator-orchestrator walkthrough completed 2026-05-10). The committed phase3e-todo + methodology files are the authoritative state.

## Project state at handoff

- **HEAD:** post-handoff-commit on main (this brief + housekeeping). Will be in sync with origin after the handoff commit pushes.
- **Tests:** 2206 fast (1 skipped). Test count baseline +85 from pre-polish-bundle-2026-05-10 (2121).
- **Ruff:** 18 (E501 only). Unchanged since 2026-05-10.
- **Schema:** v16 unchanged.
- **Worktrees:** main only (5 husks left from earlier in session; cleanup-script-handled separately).
- **In-flight:** none (Bundle 1 just shipped; Bundle 2 + 3 specs ready for brief drafting).
- **Operator availability:** active in session; expect normal turn-by-turn engagement.

## Operator-facing notes for handoff turn

When operator reads this brief, they should expect:
1. Confirmation that Bundle 1 shipped successfully + housekeeping committed.
2. Two design questions for §4.B trigger + §4.D thresholds (operator-pending locks).
3. Bundle 2 brief drafted + ready to dispatch.

The prior orchestrator's recommendation on the design questions:
- §4.B: implicit (a) R-multiple trigger (Bundle 1's §4.B-adjacent infrastructure already supports it; lower implementation friction)
- §4.D: implicit (b) DST D.7 doctrine-anchored thresholds (cleaner than arbitrary defaults)

Surface these as recommendations alongside the multi-choice options when posing the questions.
