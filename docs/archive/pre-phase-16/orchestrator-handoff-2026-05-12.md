# Orchestrator handoff — 2026-05-12 mid-session

You are taking over as orchestrator for the Swing Trading project mid-session. The prior orchestrator just shipped Phase 9 Sub-bundle A (`6c8f3a9`) and reached a planned context-budget breakpoint. **Sub-bundles B/C/D/E remain to dispatch + a small set of post-merge housekeeping items are queued for you to absorb early.**

This handoff is **not** a session-restart context recovery (the prior orchestrator was operating well; just budget-managing). The work-in-progress + post-Sub-bundle-A state is fully documented in committed files + this brief.

## ⚠ Critical bootstrap framing

**claude-mem may still be DISABLED** for the operator's evaluation window (started 2026-05-10). You will NOT see SessionStart claude-mem injection blocks. Do NOT attempt `mcp__plugin_claude-mem_mcp-search__*` or `mem-search` skill — both will fail. Auto-memory dir (MEMORY.md + linked files) IS still loaded by the harness. See `~/.claude/projects/c--Users-rwsmy-swing-trading/memory/feedback_claude_mem_hook_blocks_disabled.md` for full re-enablement criteria.

## Step 1 — Read these in order

1. **`docs/orchestrator-handoff-2026-05-11.md`** + **`docs/orchestrator-handoff-2026-05-10.md`** — prior bootstrap briefs; full project framing remains valid. Skim "Project state at handoff" + "Operator preferences" sections.

2. **This brief end-to-end** — captures everything new since the prior handoff.

3. **`docs/phase9-bundle-A-return-report.md`** — Sub-bundle A return report. Read §6 (ACCEPT-WITH-RATIONALE positions), §7 (watch items for B/C/D/E + orchestrator-context capture), §10 (Sub-bundle B/C/D/E hand-off notes), §11 (operator-side action items including 3 CLAUDE.md gotcha promotion candidates).

4. **`docs/superpowers/plans/2026-05-11-phase9-risk-policy-reconciliation-plan.md`** — Phase 9 plan, 2257 lines. Skim §A (resolved-during-planning), §B (file map), §C (decomposition table), §E (Sub-bundle B — lines 1516+). Sub-bundle B is your next dispatch.

5. **`docs/phase9-bundle-A-executing-plans-dispatch-brief.md`** — Sub-bundle A dispatch brief; **template for Sub-bundle B brief drafting**.

## Step 2 — Standard bootstrap verification

```bash
git log --oneline -10
git status
git worktree list
```

Expected: HEAD `2219ab5` on main; in sync with origin; working tree clean. Worktree husks expected at:
- `.worktrees/3e8-bundle-3-maturity-and-stop-tighten-hints/`
- `.worktrees/phase9-bundle-A-risk-policy-foundation/`
- `.worktrees/phase9-writing-plans/`
- `.worktrees/polish-bundle-2026-05-10/`

**4 husks pending operator-elevated `cleanup-locked-scratch-dirs.ps1`** — does NOT block dispatch work.

## Step 3 — Project state at handoff

- **HEAD on `main`:** `2219ab5` (post-Sub-bundle-A-ship housekeeping; pushed).
- **Test count:** 2462 fast (1 skipped; 3 pre-existing failures on `tests/integration/test_phase8_pipeline_walkthrough.py` "archive returned None" — NOT regressions, banked for separate triage).
- **Ruff baseline:** 18 (E501 only).
- **Schema version:** v17 (Phase 9 Sub-bundle A migration landed in production at 2026-05-12T08:18:10Z).
- **Active risk_policy:** policy_id=4 (max_account_risk_per_trade_pct=0.75 inherited from S3 test; capital_floor_constant_dollars=7500 reverted from S2.bis test). Supersession audit chain: 1→2→3→4. Operator may want to supersede again to revert max_risk_per_trade back to 0.50 if 0.75 is not desired ongoing (orchestrator action only if operator surfaces).
- **swing.config.toml:** clean (risk_equity_floor reverted from S2.bis test to 7500.0).
- **user-config.toml:** intact (Finviz token + screen_query); comments restored mid-Codex-R1 by operator from known-good source.
- **Open positions:** 5 (DHC/YOU/VSAT/CVGI/LAR); RLMD test entry from S4 verification was cleaned up via DELETE.

## Step 4 — Queued items for early absorption

### 4.1 CLAUDE.md gotcha promotions (3 candidates banked at Sub-bundle A return report §11)

Promote these to CLAUDE.md `## Gotchas` section. Each is a forward-binding lesson for Sub-bundles B/C/D/E + future phases:

1. **Phase 9 ratification helper single-fire semantics.** `ratify_seed_from_cfg_on_v17_landing` fires ONCE at v16→v17 transition; subsequent `swing db-migrate` runs SKIP to avoid clobbering operator's CLI policy edits. Repair path: per-field `swing config policy import-from-toml --field <name>` covering all 4 spec §3.1.3 SEED MAP fields. Reasoning: bypass-clobber discipline; once-and-only-once landing.

2. **All four cascade emitters MUST do the no-op-skip check** before invoking `supersede_active_policy`. Emitters: CLI `config set`, CLI `config reset`, web `POST /config`, web `POST /config/reset/{field}`. Pattern is per-emitter; future emitters MUST mirror it (compare would-be value to active policy value; skip supersession when identical).

3. **Test pollution: `swing/config_user.py:_user_home()` reads `USERPROFILE`/`HOME` env vars unmonkeypatched.** Any future test fixture that exercises `write_user_overrides` MUST `monkeypatch.setenv("USERPROFILE", str(home))` AND `monkeypatch.setenv("HOME", str(home))` BEFORE invoking — otherwise writes leak to operator's REAL `~/swing-data/user-config.toml`. Mid-Codex-R1 the operator's real user-config.toml accumulated test pollution; manual restoration was required. 5 affected test files now correctly monkeypatch (per implementer return report §7 item #2).

### 4.2 Orchestrator-context "Lessons captured" additions (2 lessons)

Add to `docs/orchestrator-context.md` "Lessons captured" section:

1. **Production-write classifier soft-block under auto-mode.** When orchestrator drives a production action (db-migrate; trade entry; etc.) via Bash or javascript_tool, auto-mode classifier may soft-block on "high-severity" production state changes. Reason: AskUserQuestion responses are NOT visible to the classifier; only chat-text "yes, run X" authorizations are visible. **Workaround:** when operator authorizes via AskUserQuestion AND classifier blocks, surface back to operator + request plain-chat confirmation. Hit this twice in 2026-05-12 session (db-migrate; entry-form submit).

2. **`tomli_w.dump` comment-stripping.** `swing/config_user.py:write_user_overrides()` uses `tomli_w.dump()` which is a one-way serializer — comments dropped. Any Phase 5 cfg-cascade write OR Phase 9 TOML-divergence repair flow strips operator comments from `~/swing-data/user-config.toml`. V2 candidate: switch to `tomlkit` (round-trip preserving) OR document the constraint in operator manual. Pre-existing limitation; surfaced via Sub-bundle A test pollution incident.

### 4.3 Sub-bundle B dispatch brief (the BIG queued task)

Sub-bundle B = reconciliation depth (9 tasks T-B.0..T-B.8; ~14-18 hr per plan §C). Scope per plan §E (lines 1516+):

- Reconciliation repo + service (consumes `reconciliation_runs` + `reconciliation_discrepancies` tables LANDED in Sub-bundle A's migration 0017).
- `swing/journal/tos_import.py` refactor (emitter seam) preserving existing `ReconciliationReport` return shape; existing CLI consumers (`swing journal import-tos`) unaffected during transition.
- 5 new discrepancy types: close_price_mismatch, entry_price_mismatch, stop_mismatch, position_qty_mismatch, cash_movement_mismatch.
- CLI: `swing journal reconcile-tos` (RENAME from `swing journal import-tos`; deprecation alias for V1) + new `swing journal discrepancy {list,resolve,show}` group.
- `material_to_review` classification at INSERT time via `MATERIAL_BY_TYPE` lookup + operator-override.
- Reconciliation failure-path PRESERVES run row + UPDATE state='failed' (NOT rollback-new-row; per spec §3.3.3 + Sub-bundle A's plan §A.2.1).

**Dispatch brief template:** mirror `docs/phase9-bundle-A-executing-plans-dispatch-brief.md` shape. The Sub-bundle A brief was 275 lines; B will be similar scale. **BASELINE_SHA for B = current main HEAD** at brief-commit time (likely `2219ab5` or the brief commit itself).

Sub-bundle B specifics to highlight in brief §0.5 BINDING contracts:
- Reconciliation service must follow Phase 7+8 transactional discipline (reject caller-held tx; own BEGIN IMMEDIATE / COMMIT / ROLLBACK).
- Reconciliation failure-path: PRESERVE run row + UPDATE state='failed' (NOT rollback-new-row); cash_movements + fills inline-inserts retained inside the outer transaction (plan §A.2.1).
- CLI rename: `swing journal import-tos` → `swing journal reconcile-tos`; deprecation alias retained for V1; alias removed in V2.
- `tos_import.py` refactor preserves existing `ReconciliationReport` dataclass return shape (existing CLI consumers unaffected).

## Step 5 — Confirm operator workflow + preferences

Operator preferences (durable, restated for emphasis):

- **Implementer-dispatch is the default** per `~/.claude/projects/.../memory/feedback_orchestrator_vs_implementer_execution.md`. Crossover to orchestrator-inline only when orchestrator's token cost < implementer's spinup-plus-task cost.
- **Once operator-witnessed gate passes, integration merge is orchestrator action.** Do NOT ask "shall I proceed with merge."
- **Worktree-isolated dispatch briefs MUST specify `.worktrees/<branch>/` path explicitly** (binding convention 2026-05-09).
- **Implementer runs adversarial-critic** (per orchestrator-context "Executing-plans dispatch convention" 2026-05-02). Marker file `.copowers-subagent-active` at project root.
- **Brief-recommended technical micro-decisions need empirical pre-verification** before locking.
- **Multi-choice format for design questions** (operator preference; provides clean choice surface).
- **Chrome MCP gate-driving** is the established pattern for operator-witnessed verification. Operator surfaces `@browser` instruction at session start to load `mcp__claude-in-chrome__*` tools.

## Step 6 — Production-write classifier soft-block awareness

**NEW THIS SESSION** (worth absorbing early):

When orchestrator drives production-mutating actions via Bash / javascript_tool / etc., the auto-mode classifier may soft-block. Encountered twice this session:

1. `swing db-migrate` (operator-authorized via AskUserQuestion; classifier blocked). Workaround: operator ran the command themselves.
2. HTMX entry-form submit (operator-authorized via AskUserQuestion; classifier blocked). Workaround: operator replied "yes, submit" in plain chat → I retried successfully.

**Pre-empt:** when about to invoke a production-write action where operator pre-authorized via AskUserQuestion, IF the classifier blocks, surface back to operator with the action description + ask for plain-chat "yes" confirmation. Don't try to work around the classifier in any other way.

## Step 7 — Your first action

1. Run the standard bootstrap verification (Step 2) + read the files in Step 1 order.
2. Absorb the 3 CLAUDE.md gotcha promotions (Step 4.1) + the 2 orchestrator-context lessons (Step 4.2). Commit as a single housekeeping commit early in your session ("docs: bank Sub-bundle A gotcha promotions + orchestrator-context lessons").
3. Draft Sub-bundle B executing-plans dispatch brief at `docs/phase9-bundle-B-executing-plans-dispatch-brief.md` per Step 4.3.
4. Commit + push the brief.
5. Provide paste-ready implementer prompt inline (operator preference).
6. Stand by for Sub-bundle B implementer return.
7. Sub-bundle B ship → housekeeping → repeat for Sub-bundles C → D → E.
8. Then Phase 10 writing-plans dispatch.

## Step 8 — Operator-side action items pending (informational)

Per Sub-bundle A return report §11:

- **Active risk_policy is policy_id=4** with `max_account_risk_per_trade_pct=0.75` (inherited from S3 test). Operator may want to supersede back to 0.5 for production. Surface if/when operator mentions; do NOT supersede unprompted.
- **user-config.toml restored** mid-Codex-R1 per operator (known-good source); current state intact.

## Step 9 — Project state at handoff

- **HEAD:** `2219ab5` on main; in sync with origin.
- **Tests:** 2462 fast (1 skipped; 10 deselected slow; 3 pre-existing failures NOT regressions).
- **Ruff:** 18 (E501 only). Unchanged.
- **Schema:** v17 production.
- **Worktree husks:** 4 (3e8-bundle-3 + phase9-bundle-A + phase9-writing-plans + polish-2026-05-10); cleanup-script-handled.
- **In-flight:** none (Sub-bundle A merged; Sub-bundles B/C/D/E queued for dispatch).
- **Operator availability:** active in session; expect normal turn-by-turn engagement.

## Step 10 — Quick reference summary

| Artifact | Path / commit |
|---|---|
| Phase 9 spec | `docs/superpowers/specs/2026-05-06-phase9-risk-policy-reconciliation-design.md` (`31ee51c`) |
| Phase 9 plan | `docs/superpowers/plans/2026-05-11-phase9-risk-policy-reconciliation-plan.md` (`a0c7223`) |
| Phase 9 writing-plans return | `docs/phase9-writing-plans-return-report.md` |
| Sub-bundle A dispatch brief | `docs/phase9-bundle-A-executing-plans-dispatch-brief.md` (`51ee033`) |
| Sub-bundle A return report | `docs/phase9-bundle-A-return-report.md` (`6c8f3a9` merge) |
| Sub-bundle A merge | `6c8f3a9` |
| Sub-bundle A housekeeping | `2219ab5` (current HEAD) |
| Sub-bundle B section in plan | §E lines 1516+ |
| Sub-bundle B dispatch brief | TBD (your first major deliverable) |

## Operator-facing notes for handoff turn

When operator reads this brief, they should expect:
1. Confirmation that Sub-bundle A shipped successfully + housekeeping committed.
2. Acknowledgment of the gotcha promotions + lesson banking work to do early.
3. Sub-bundle B brief drafted + ready to dispatch.

The prior orchestrator's recommendation on absorption order:
- Gotcha promotions + lesson banking first (small + clean; gets durable knowledge captured before any new dispatch).
- Then Sub-bundle B dispatch brief drafting (~270 lines; ~30 min of work with fresh context).
- Then provide paste-ready prompt + stand by.

Standing by for implementer return on Sub-bundle B once dispatched.
