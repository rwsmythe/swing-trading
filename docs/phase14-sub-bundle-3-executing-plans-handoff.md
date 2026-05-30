# Phase 14 Sub-bundle 3 -- Orchestrator Handoff (executing-plans onward)

**Audience:** Fresh Claude Code instance taking on the Phase 14 orchestrator role mid-Sub-bundle-3. The prior orchestrator handed off at 33% context after merging the SB3 writing-plans product (operator-chosen "merge + housekeep now, then hand off" 2026-05-30).

**Clean boundary:** SB3 **writing-plans SHIPPED** at `4fa20dd`. Your **first action: author the SB3 executing-plans dispatch brief** + inline prompt, then drive the executing-plans cycle.

---

## Bootstrap (read in order)

1. **CLAUDE.md** -- the line-3 "Current state" pointer + the compressed Gotchas (code-failure-prevention). NOTE: the "Expansion #N" process/review disciplines were relocated 2026-05-28 (restructure `665cab0`) to `docs/orchestrator-context.md` §"Pre-Codex review + brief-authoring disciplines" -- read BOTH.
2. **`docs/orchestrator-context.md`** -- durable orchestrator-role bootstrap (role/pattern + retention discipline). Its "Currently in-flight work" section is STALE (V2 OHLCV from late May); **canonical live state = `git log --oneline -20` + `docs/phase3e-todo.md` top entry** (per CLAUDE.md line 3).
3. **`docs/phase3e-todo.md`** top entries (2026-05-30 SB3 writing-plans + the #4/#5/#2 SB2/SB3 entries) -- full per-pass context.
4. **`docs/phase14-commissioning-brief.md`** Sec 2.1 + Sec 9.1 LOCKs (Q1-Q7).
5. **Memory** at `C:\Users\rwsmy\.claude\projects\c--Users-rwsmy-swing-trading\memory\` -- esp. `feedback_orchestrator_performs_merge` (HARDENED: gate-pass/QA-pass/Codex-convergence IS the merge trigger across all 3 copowers phases; do NOT ask "shall I merge"), `feedback_orchestrator_qa_implementer_product`, `feedback_commit_brief_before_inline_prompt`, `feedback_always_provide_inline_dispatch_prompt`, `feedback_pause_means_pause`, `feedback_commit_message_trailer_parse_hazard` (NEW), `feedback_copowers_codex_mcp_windows_launcher` (NEW).

## Phase 14 state

| Sub-bundle | State |
|---|---|
| 1 data-wiring | SHIPPED end-to-end (`e323339`) |
| 2 temporal log V1+ (v22) | **SHIPPED end-to-end (`27f8007`)** -- operator-witnessed gate PASS; v22 LIVE in the operator's real DB |
| 3 chart-surface uniformity | brainstorm `f16735f` + **writing-plans `4fa20dd` SHIPPED**; executing-plans NEXT |
| 4 review+journal UX / 5 metrics overview | pending (serial) |

**main/origin = `4fa20dd`** (+ the housekeeping commit that lands with this handoff). **~624+ commits ZERO `Co-Authored-By`**. **Schema v22 LOCKED** (v23 DESIGNED in SB3; lands at SB3 executing-plans). **L2 LOCK preserved** (source-grep test at `tests/integration/test_l2_lock_source_grep.py` baseline `bf7e071`).

## Your first action: author the SB3 executing-plans dispatch brief

- Mirror **`docs/phase14-sub-bundle-2-temporal-log-executing-plans-dispatch-brief.md`** (the SB2 executing-plans brief is the shape template).
- Consume: the plan **`docs/superpowers/plans/2026-05-30-phase14-sub-bundle-3-chart-surface-uniformity-plan.md`** §G (tasks T-3.1..T-3.6) + §I (the per-renderer binding visual-gate runbook) + the writing-plans return report **`docs/phase14-sub-bundle-3-chart-surface-uniformity-writing-plans-return-report.md`** (forward-binding lessons).
- The **11 operator-LOCKed OQ dispositions** are in the writing-plans dispatch brief **`docs/phase14-sub-bundle-3-chart-surface-uniformity-writing-plans-dispatch-brief.md`** §1.3 -- carry them verbatim (P14.N8 real `current_stage` at all weather sites; mplfinance candlesticks on the 4 detail surfaces, thumbnail line; SINGLE Codex chain; P14.N1 substrate-only; 50/200 MAs; v23 in-migration rename; S6 upper-right; Okabe-Ito MA palette; BULZ target-only-if-present; zone hues gate-confirmed; full renderer-fn rename).
- **Codex = SINGLE chain** (OQ-chain LOCK).
- v23 is INTRODUCED by executing-plans (exactly one new `0023_*.sql`; backup-gate STRICT `pre_version == 22`; gotcha #11 paired; gotcha #9). No v24.

## Two production corrections + one confirm-item to carry into the executing-plans brief

1. `current_stage` is at `swing/patterns/foundation.py:745` (`current_stage(conn, ticker, asof_date: date)`; returns only `stage_2`/`undefined` in V1) -- the spec's `review_form.py:454` caller does not exist.
2. The dashboard reads `market_weather` from cache only (no live JIT caller) -> the `chart_jit` `stage_2` default is dead/defensive (now `undefined`). P14.N8 = **2 live sites + 1 defensive default**.
3. **BULZ entry-anchor V1 simplification (OPERATOR-CONFIRM at the visual gate):** the plan anchors the BULZ zones on the locked `trade.entry_price` (deriving target from `planned_target_R`), deviating from spec §7's avg-fill anchor. The implementer surfaced this; the operator should confirm it at the executing-plans operator-witnessed visual gate.

## Executing-plans operator-witnessed gate (per-renderer visual)

Per plan §I, the BINDING gate is the RENDERED chart (matplotlib; byte/string tests insufficient): S1 pytest+ruff; S2 v23 applied (`schema_version=23`; `chart_renders` rows migrated `hyprec_detail`->`ticker_detail`; backup written); S3-S7 per-surface visuals (ticker_detail + position_detail/BULZ + market_weather real-trend + theme2 duration-text + refresh-vs-pipeline kwarg uniformity). **Proven technique (SB2 S6):** if the browser MCP is unavailable, the orchestrator can render a surface to PNG via the branch code + Read the PNG visually (the Read tool views PNGs); or operator-driven browser + orchestrator DB-side probes. **The operator directed the orchestrator to RUN the gates** at SB2 -- confirm their preference for SB3.

## Operating disciplines (binding)

- **Merge:** gate-pass/QA-pass/Codex-convergence IS the trigger; perform merge + push + housekeeping + next-phase dispatch brief + inline prompt WITHOUT asking "shall I merge" (hardened `feedback_orchestrator_performs_merge`). For executing-plans, merge AFTER the operator-witnessed gate passes.
- **QA every implementer product against disk** before merge (branch/trailers/merge-base; scope; schema; LOCKs; spot-check Codex catches against production code).
- **Commit message trailer hazard (NEW):** keep the FINAL `-m` paragraph plain prose -- a line starting `Word:` (e.g. `FB-N1:`) parses as a git trailer and pollutes the `%(trailers)` ZERO-Co-Authored-By audit. Verify `git log -1 --format='%(trailers)'` is `[]` before every push. (Recovered once this session via `--amend` + `--force-with-lease`.)
- **Codex MCP (FB-N1):** OFF YOUR PURVIEW -- the operator is investigating the 1s-timeout separately. Implementers use the `codex exec` CLI + `resume --last` backstop (inline-pasted artifacts; read-only sandbox can't read files on this host). Do NOT attempt to fix the MCP.
- **Inline prompts:** every dispatch brief gets a paste-ready inline implementer prompt in chat (fenced block); commit the brief BEFORE providing the prompt.
- **Worktree CLI:** `python -m swing.cli` (not bare `swing`). After an executing-plans merge, reinstall `swing` from main (`pip install -e . --no-deps`) since the editable install gets pointed at the worktree during the gate.
- **NO `Co-Authored-By` footer; NO `--no-verify`.** ~624+ ZERO-drift streak.

## Forward path

SB3 executing-plans (dispatch -> ship -> per-renderer visual gate -> merge) -> Sub-bundle 4 (review+journal UX; CR.1 + P14.N6) -> Sub-bundle 5 (metrics overview; P14.N5; matplotlib SVG per Q5) -> Phase 14 close-out review (Sec 9.1 Q6: all 5 sub-bundles merged + operator browser-witnessed cross-sub-bundle integration).

---

*End of handoff. Clean boundary: SB3 writing-plans SHIPPED at `4fa20dd`. First action: author the SB3 executing-plans dispatch brief (mirror SB2's) + inline prompt, then drive the executing-plans cycle. The temporal-log substrate (SB2) is LIVE and accumulating; chart-surface uniformity (SB3) is the current work; the rendered chart is the binding visual gate.*
