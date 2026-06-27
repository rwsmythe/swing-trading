# Orchestrator handoff — 2026-05-17 PM (post-Sub-bundle-1-merge + post-housekeeping; Sub-bundle 1.5 dispatch queued; Phase 12.5 + Phase 13 scope LOCKED)

You are taking over as orchestrator for the Swing Trading project at the **post-Sub-bundle-1-merge + post-housekeeping** breakpoint. Sub-bundle 1 (V2 Schwab mapper execution-grain widening + classifier consumer + comparator + housekeeping FOLDED) merged 2026-05-17 at `120c992` (PASS-WITH-FINDING). Sub-bundle 1.5 follow-up dispatch is queued (root-cause + fix the validator-drop defect surfaced at S3 production gate). Phase 12.5 (3 items) + Phase 13 (4 themes; 10 sub-bundles) scope is operator-LOCKED but dispatch is gated on Sub-bundle 2 + Sub-bundle 1.5 close.

**HOUSEKEEPING COMPLETED 2026-05-17 PM by outgoing orchestrator** (this handoff was AMENDED post-housekeeping after operator caught the ownership mistake — orchestrator-context.md is the working-memory passthrough owned by outgoing orchestrator, per §"Session-end checklist" line 587 + §"How to update this file" line 598). Updated:
- `CLAUDE.md` status-line PARAGRAPH — appended Sub-bundle 1 SHIPPED entry with gate outcome + validator-drop finding.
- `docs/phase3e-todo.md` — Sub-bundle 1 SHIPPED entry at top (above Phase 12.5 RESCOPED entry).
- `docs/orchestrator-context.md` — §"Currently in-flight work" updated with post-Sub-bundle-1 state + Phase 12.5 rescope + Phase 13 scope locks + 3 NEW memory entries + Sub-bundle 1.5 dispatch readiness; §"Lessons captured" appended 4 NEW lessons (pause-means-pause + worktree-cli-invocation + time-estimates-overstated + sub-bundle-1-architectural-fix-holds-negative-positive-fails-fire + per-run-vs-per-fill re-emission family + Bash-tool-cwd-drift); §"Memory entries" updated with 3 NEW memory entries.

The prior orchestrator handed off because:

1. **Sub-bundle 1 merge is a clean shift boundary.** Main HEAD `120c992`; production banner=0; system in safe-degraded mode (V1-equivalent + Path B sentinel emit; no false-positives; positive lift gated on Sub-bundle 1.5 fix).
2. **Substantial Sub-bundle 1.5 dispatch brief drafting remains** (~250-350 lines mirroring Sub-bundle 1 brief structure) — benefits from fresh context window.
3. **Cap-drift on prior session** was real — drove a 9-surface operator-witnessed gate + 4 production-write dispositions + Phase 13 scope conversation + 4 doc commits + memory banking + housekeeping updates.

## ⚠ Critical bootstrap framing

**claude-mem may still be DISABLED** for the operator's evaluation window (started 2026-05-10). Auto-memory dir (`~/.claude/projects/c--Users-rwsmy-swing-trading/memory/MEMORY.md` + linked files) IS still loaded.

**3 NEW memory entries banked during prior session** (load-bearing for this orchestrator):
- `feedback_pause_means_pause.md` — when operator says pause, STOP all forward motion immediately, even items appearing independently confirmed.
- `feedback_worktree_cli_invocation.md` — at worktree-side gates, `swing` console-script routes to editable-install (main repo), NOT worktree code. Use `python -m swing.cli <subcommand>` from worktree cwd.
- `feedback_time_estimates_overstated.md` — orchestrator's wall-clock estimates are 3-5x too long; divide naive estimate by 3-5x for actual operator-paced wall-clock.

**Operator dispatches implementers themselves** (per durable preference). Orchestrator drafts brief + provides inline dispatch prompt as fenced code block.

**Always provide an inline dispatch prompt** with every brief.

**Commit brief BEFORE inline dispatch prompt.**

**One command at a time on production writes; inline-batched OK on reads/tests.**

**NO Claude co-author footer.** Phase 12 C.B precedent + post-Phase-12 brainstorm/writing-plans/Sub-bundle-1 chains ALL held the line via explicit citation in dispatch prompts. Pattern is durable.

**Once operator-witnessed gate passes, integration merge is orchestrator action.**

## Step 1 — Read these in order

1. **This brief end-to-end** — captures Sub-bundle 1 outcome + Sub-bundle 1.5 dispatch readiness + Phase 12.5 + Phase 13 scope locks.

2. **`CLAUDE.md` status line** — currently does NOT have Sub-bundle 1 SHIPPED entry; **YOUR FIRST DELIVERABLE is updating it** to include the Sub-bundle 1 SHIPPED entry (per the merge commit `120c992` content) with the validator-drop finding routing to Sub-bundle 1.5. Existing Pass-2-tier-1-FORBIDDEN gotcha already has the V2-RESOLVED-for-Pass-1 amendment text (was in the worktree CLAUDE.md and merged through). The status line PARAGRAPH itself needs the new SHIPPED entry.

3. **`docs/phase3e-todo.md`** top entries in reverse-chronological order:
   - Sub-bundle 1 merge entry — **needs to be banked at top after status line update**.
   - Phase 12 Sub-sub-bundle C.D SHIPPED (2026-05-17) — predecessor.
   - Phase 12.5 RESCOPED entry (3 items; operator-locked 2026-05-17).
   - Phase 13 scope-brainstorm IN PROGRESS entry — superseded by §0.5 LOCK at `docs/phase13-scope-brainstorm.md`.

4. **`docs/orchestrator-context.md`** sections "Currently in-flight work" + "Lessons captured" — **needs current-state pointer refresh** (Sub-bundle 1 SHIPPED + Sub-bundle 1.5 dispatch queued). 3 NEW session-banked lessons (per memory entries above) should also be folded into orchestrator-context per retention discipline (or summarized at top if you choose to defer the full archive-split — see §"Cap-drift maintenance pass" below).

5. **`docs/phase13-scope-brainstorm.md`** §0.5 — operator-locked Phase 13 scope (4 themes + 10 sub-bundles + 11 design decisions). NOT your immediate scope; ground for context.

6. **`docs/phase13-brainstorm-dispatch-brief.md`** — ready-to-dispatch Phase 13 brainstorm brief. NOT to be dispatched until Sub-bundle 2 + Phase 12.5 close.

7. **`docs/post-phase12-schwab-mapper-bundle-1-execution-grain-widening-executing-plans-dispatch-brief.md`** at `e2a11bf` — Sub-bundle 1's dispatch brief (format precedent for Sub-bundle 1.5 brief).

## Step 2 — Standard bootstrap verification

```bash
git log --oneline -10                       # expect 120c992 at HEAD
git status                                  # expect clean (scripts/convert_books_pdf_to_md.py untracked is operator's WIP)
git worktree list                           # expect main + schwab-mapper-bundle-1 husk pending cleanup
python -m pytest -m "not slow" -q -n auto | tail -5  # expect ~4475 fast + 3 pre-existing phase8 walkthrough failures + 5 skipped (~74s)
ruff check swing/ --statistics | tail -3    # expect 18 E501
python -c "from swing.integrations.schwab.models import SchwabExecutionLeg, SchwabOrderResponse; print('mapper OK')"
python -c "from swing.trades.schwab_reconciliation import _compute_execution_price, _resolve_match_quantity, _is_execution_bearing_candidate; print('helpers OK')"
python -m swing.cli journal discrepancy show-correction --help    # T-1.12 NEW CLI subcommand; verify the generic ID-free addendum renders
```

Expected state on main HEAD `120c992`:
- **Sub-bundle 1 SHIPPED** (4 architectural surfaces + housekeeping FOLDED; 5 Codex rounds; ZERO ACCEPT-WITH-RATIONALE; +115 fast tests; schema v19 unchanged).
- **Production state CLEAN** — ZERO unresolved-material discrepancies; banner count=0; 4 discrepancies dispositioned at gate (correction_ids 11+12+13+14 — all DHC+VSAT unmatched_open_fill / acknowledge per C.D-precedent family).
- **System in safe-degraded mode** — V2 mapper widening's positive lift NEVER FIRED on production data (all 18 production orders had executionLegs[0] uniformly dropped at SchwabExecutionLeg validator); architectural fix HOLDS in negative sense only (no false-positive entry/close_price_mismatch emissions).
- **schwab-mapper-bundle-1 worktree husk** pending cleanup-script -DeregisterFirst pass.

## Step 3 — Current state + Sub-bundle 1.5 dispatch readiness

### §3.1 Sub-bundle 1 validator-drop defect (Sub-bundle 1.5 scope)

**Defect**: Every production order at S3 gate (`python -m swing.cli schwab fetch --orders`; emitted reconciliation_run #13) had `orderActivityCollection[0].executionLegs[0]` rejected by `SchwabExecutionLeg.__post_init__` validator. Mapper logged 18 drop-warnings:
```
map_orders_to_fill_candidates: order <id> activity[0].executionLegs[0] failed validator (ValueError); dropping leg
```

**Symptoms**:
- All 18 orders fail UNIFORMLY (not just edge cases) → systematic shape mismatch
- run #13 summary: `discrepancies_emitted: 2`; `tier1_applied_count: 0`; `tier2_pending_count: 2`
- ZERO `entry_price_mismatch` / `close_price_mismatch` false-positives (architectural fix held in negative sense)
- Cassette tests + hand-rolled E2E tests all PASS (3 cassette LIMIT BUY/SELL/STOP FIRED + 3 hand-rolled Shape C tier-1/Path B sentinel/MARKET BUY)

**Hypothesis** (root cause unknown without raw Schwab response):
- (a) Schwab returning `price` / `quantity` keys nested differently than mapper expects (e.g., `priceAtFill` or `legQuantity`); mapper defaults to 0 → validator fails on `> 0` check
- (b) Schwab returning `time` as missing/null/non-string for some leg shapes
- (c) Some other field with unexpected type
- Family = synthetic-fixture-vs-production-emitter shape drift (C.D-arc lesson #2 + #4 inheritance)

**Critical**: `schwab_api_calls` audit table does NOT capture `response_body_json` (verified via SELECT). Sub-bundle 1.5 will need to add temporary diagnostic logging OR a one-shot direct API call OR a schema extension to capture raw shape.

### §3.2 Sub-bundle 1.5 dispatch brief drafting (YOUR FIRST MAJOR DELIVERABLE post-housekeeping)

Target output: `docs/post-phase12-schwab-mapper-bundle-1.5-validator-drop-fix-executing-plans-dispatch-brief.md` (mirror Sub-bundle 1 brief structure at `e2a11bf`; ~250-350 lines).

Key elements to cover:
1. **Diagnostic phase**: implementer must capture raw Schwab response shape for one failing order (options: temporary debug logging at mapper drop-point + re-run schwab fetch; OR one-shot direct API call via schwabdev bypassing mapper; OR schema extension to capture response_body_json — implementer picks).
2. **Fix phase**: amend validator OR amend mapper pre-coercion OR amend field-extraction to match actual Schwab production shape. Discriminating regression test landing in cassette form.
3. **Re-verification**: re-run S3 against production; verify `tier1_applied_count > 0` IF there are eligible discrepancies, OR at minimum NO validator-drop warnings logged.
4. **Branch**: `schwab-mapper-bundle-1.5` (matches cleanup-script regex `schwab(?:-\w+)?-bundle-`).
5. **Worktree**: `.worktrees/schwab-mapper-bundle-1.5/`.
6. **Codex chain**: expect 2-4 rounds (focused defect fix).
7. **Gate**: small (3-5 surfaces; S1 fast tests + S2 cassette + S3 production re-run + S4 banner + S5 ruff).

### §3.3 Operator-locked scope downstream of Sub-bundle 1.5

Per `docs/phase13-scope-brainstorm.md` §0.5 (LOCKED 2026-05-17):

**Post-Phase-12 arc** (close in order):
- Sub-bundle 1.5: validator-drop fix (YOUR FIRST DISPATCH after housekeeping)
- Sub-bundle 2: T-B.7 `/schwab/status` web counterpart (per `docs/post-phase12-schwab-mapper-execution-grain-widening-writing-plans-dispatch-brief.md` §7 T-2.0..T-2.6)

**Phase 12.5** (3-item bundle; ships after Sub-bundle 2):
1. OQ-F multi-leg tier-1 auto-redirect
2. Web Tier-2 discrepancy-resolution surface
3. CLAUDE.md + orchestrator-context.md maintenance pass

**Phase 13** (4 themes / 10 sub-bundles; ships after Phase 12.5):
- Theme 1: Chart rendering deepening (watchlist + hyp-rec + active list + market weather mini-chart)
- Theme 2: Pattern recognition (5 buy-side patterns; rule-based + template matching + closed-loop surface; sell-side BANKED Phase 14; ML re-ranker BANKED indefinitely)
- Theme 3: Auto-fill deepening (entries + exits + reviews; absorbed Phase 12.5 #2)
- Theme 4: Usability triage closer

## Step 4 — Operator preferences (durable; carry over)

- Implementer-dispatch is the default; orchestrator-inline only at token-cost crossover.
- Once gate passes, integration merge is orchestrator action (do NOT ask "shall I merge").
- Worktree-isolated dispatch briefs MUST specify `.worktrees/<branch>/` path explicitly.
- Implementer runs adversarial-critic via `copowers:executing-plans` wrapper.
- AskUserQuestion preferred for design decisions BUT operator noted (2026-05-17) the tool can't combine pre-canned + custom input cleanly — use prose follow-up for "Option B with caveat" cases.
- Spec is canonical over brief on cosmetic typos.
- Production-write classifier soft-block fires PER INVOCATION; expect blocks per operator decision per writes; plain-chat "yes" is recovery.
- Always provide inline dispatch prompt with every brief.
- Commit brief BEFORE inline prompt.
- Operator-paired gate driving — ONE COMMAND AT A TIME on production writes; inline-batched OK on reads/tests.
- Explicit `Co-Authored-By` footer suppression in dispatch prompts (durable; passive CLAUDE.md inheritance insufficient).
- Pre-Codex orchestrator-side review for executing-plans dispatches (saved 1-2 Codex rounds on C.C + C.D + Sub-bundle 1).
- Operator-architectural-pushback mid-gate triggers STOP-and-recover (NEW C.D lesson #1; validated again on Sub-bundle 1 validator-drop finding).
- **Pause means pause** (NEW memory entry from prior session — when operator says pause, STOP forward motion completely).
- **Worktree CLI invocation**: `python -m swing.cli` from worktree cwd, NOT `swing` (NEW memory entry; routes to editable install if `swing` used).
- **Time estimates 3-5x too long** (NEW memory entry; calibration for future scope conversations).

## Step 5 — Cap-drift maintenance pass (deferred Phase 12.5 #3; orchestrator-context note)

`orchestrator-context.md` active "Lessons captured" section was reported at ~48 entries vs ~30 cap by prior orchestrator. CLAUDE.md status line is also accumulating. **Phase 12.5 #3 maintenance pass will handle this**; until then, you can add to top of "Lessons captured" or summarize old entries — your call. **DO NOT do a full archive-split as a standalone task** — wait for Phase 12.5 #3 dispatch.

## Step 6 — Pending operator-action items (NOT orchestrator-blocking)

- **schwab-mapper-bundle-1 worktree husk cleanup** — operator's `cleanup-locked-scratch-dirs.ps1 -DeregisterFirst` pass.
- **S6 + S7 async review** (deferred from Sub-bundle 1 gate):
  - S6: operator reads CLAUDE.md `Pass-2-tier-1-FORBIDDEN` gotcha amendment (already merged at `120c992`; check on main).
  - S7: operator runs `python -m swing.cli journal discrepancy show-correction --help`; reads generic ID-free addendum.
- **Schwab refresh-token clock** — issued 2026-05-15T17:05:00+00:00; expires ~2026-05-22T17:05. ~5 days remaining at handoff. T-A.2 self-healing recovery via `/schwab/setup` web form OR `swing schwab setup` CLI.
- **Run #12 + #13 audit cleanup** — both reconciliation runs emitted same DHC + VSAT unmatched_open_fill pattern (per-run-vs-per-fill family). Discrepancies all dispositioned. Banner count=0. No action needed.

## Do NOT

- Re-litigate Sub-bundle 1 ship outcome (merged + production banner clean).
- Re-litigate Phase 12.5 scope (3 items; locked).
- Re-litigate Phase 13 scope (4 themes / 10 sub-bundles; locked at `docs/phase13-scope-brainstorm.md` §0.5).
- Dispatch Sub-bundle 1.5 before drafting + committing the brief + providing inline prompt.
- Do post-merge housekeeping (CLAUDE.md status line + orchestrator-context update) BEFORE drafting Sub-bundle 1.5 brief — operator's preferred orderly flow.
- Skip the explicit Co-Authored-By footer suppression citation in any new dispatch prompt.
- Run any new production-write actions without explicit operator pre-authorization.
- Touch Sub-bundle 1's shipped code without Sub-bundle 1.5 dispatch — defect is a separate dispatch.

## Step 7 — Suggested orchestrator flow (your first session)

**Housekeeping ALREADY COMPLETED by outgoing orchestrator** (per handoff top — operator caught ownership mistake mid-handoff; outgoing orchestrator did the work). Your first deliverable is **Sub-bundle 1.5 dispatch brief drafting** directly.

1. Read this brief end-to-end.
2. Run Step 2 bootstrap verification (confirm main HEAD includes the housekeeping commit + handoff brief amendment).
3. Draft Sub-bundle 1.5 dispatch brief at `docs/post-phase12-schwab-mapper-bundle-1.5-validator-drop-fix-executing-plans-dispatch-brief.md` per §3.2 scope.
4. Commit + push brief.
5. Provide inline implementer-dispatch prompt for Sub-bundle 1.5 as fenced code block (per durable preference).
6. Operator commissions Sub-bundle 1.5 implementer.

---

*End of handoff brief. Post-Sub-bundle-1-merge orchestrator transition. Main HEAD `120c992`; production state clean; Sub-bundle 1.5 dispatch UNBLOCKED — your first major deliverable. Operator-paced.*
