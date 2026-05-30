# Phase 14 Sub-bundle 4 — Orchestrator Handoff (brainstorm onward)

**Audience:** Fresh Claude Code instance taking on the Phase 14 orchestrator role at the Sub-bundle 3 → Sub-bundle 4 boundary. The prior orchestrator handed off after SB3 executing-plans SHIPPED end-to-end + housekeeping, as context ran low (operator-directed 2026-05-30).

**Clean boundary:** SB3 **SHIPPED end-to-end** at `edd098d` (operator-witnessed gate PASS; v23 live in the operator's real DB). main/origin = `890f2d5` (SB3 housekeeping + the pre-existing-test fix). **Your first action: author the SB4 brainstorm dispatch brief** + inline prompt, then drive the brainstorm → writing-plans → executing-plans cycle.

---

## Bootstrap (read in order)

1. **CLAUDE.md** — line-3 "Current state" pointer (now says SB3 SHIPPED, SB4 NEXT) + the compressed Gotchas. The "Expansion #N" process/review disciplines live in [`docs/orchestrator-context.md`](docs/orchestrator-context.md) §"Pre-Codex review + brief-authoring disciplines" — read BOTH.
2. **`docs/phase3e-todo.md`** top entry (2026-05-30 SB3 EXECUTING-PLANS SHIPPED) — full SB3 ship record + the 4 banked follow-ups.
3. **`docs/phase14-commissioning-brief.md`** §"Sub-bundle 4 — review + journal UX (CR.1 + P14.N6)" (the SB4 scope LOCK) + Sec 9.1 LOCKs (Q1-Q7).
4. **Prior sub-bundle dispatch briefs as shape templates:** `docs/phase14-sub-bundle-3-chart-surface-uniformity-brainstorming-dispatch-brief.md` (the brainstorm-brief shape) + the SB2/SB3 writing-plans + executing-plans briefs (the downstream shapes).
5. **Memory** at `C:\Users\rwsmy\.claude\projects\c--Users-rwsmy-swing-trading\memory\` — esp. `feedback_orchestrator_performs_merge` (HARDENED), `feedback_orchestrator_qa_implementer_product`, `feedback_commit_brief_before_inline_prompt`, `feedback_always_provide_inline_dispatch_prompt`, `feedback_pause_means_pause`, `feedback_commit_message_trailer_parse_hazard`, `feedback_copowers_codex_mcp_windows_launcher`, **`feedback_no_false_green_claim` (NEW — read it; the prior orchestrator violated it this session)**, `feedback_visual_gate_both_render_and_browser` (SB3 gate preference).

## Phase 14 state

| Sub-bundle | State |
|---|---|
| 1 data-wiring | SHIPPED end-to-end (`e323339`) |
| 2 temporal log V1+ (v22) | SHIPPED end-to-end (`27f8007`) — v22 live |
| 3 chart-surface uniformity (v23) | **SHIPPED end-to-end (`edd098d`)** — operator-witnessed gate PASS; v23 live in the operator's real DB |
| 4 review + journal UX (CR.1 + P14.N6) | **NEXT — brainstorm dispatch is your first action** |
| 5 metrics overview (P14.N5) | pending (serial) |

**main/origin = `890f2d5`.** **~648+ commits ZERO `Co-Authored-By`.** **Schema v23 LOCKED** (operator's live DB migrated v22→v23 at SB3 ship; `swing` reinstalled, expects v23). **L2 LOCK preserved.**

## SB4 scope (commissioning brief; LOCKed)

- **CR.1** = the post-trade **review** web surface. The `review_log` table + `swing/trades/review.py` + `swing/data/repos/review_log.py` shipped in Phase 6; the **web surface was deferred**. CR.1 MAY add a review-submission POST (the writer exists; wiring the web form is in-scope).
- **P14.N6** = the trade **journal** — a chronological per-trade narrative (entries, exits, stop moves, reviews, advisories) assembled from `trade_events` + `fills` + `review_log`. **Read-only.**
- **Scope LOCK:** review + journal are the ONLY two surfaces; **no new trade-mutation paths**.
- **Likely no schema change** (read-mostly over shipped data) — confirm at brainstorm; if a migration IS needed it would be v24 (STRICT backup-gate `pre_version == 23`; gotcha #11 paired + #9). Do NOT touch the v22/v23 substrate.

## 4 banked follow-ups to carry into the SB4 brainstorm brief

1. **BULZ row-expand wiring (IN-SCOPE for SB4).** The SB3 `render_position_detail_svg` (candlesticks + risk/reward `axhspan` zones + ASCII legend) is correct and LIVE on the trade-detail page (`GET /trades/{trade_id}` → `trades/detail.html.j2`, which embeds `vm.position_chart_svg_bytes`). But the **dashboard open-positions row-expand** (`open_positions_expanded.html.j2`) still shows the **legacy static `/charts/{date}/{ticker}.png`** (the "pivot | stop | 120 bars" chart from `swing/rendering/charts.py:render_chart`). SB4 should wire the row-expand (and/or journal surface) at the SB3 `position_detail` SVG so P14.N4 BULZ zones are visible in the operator's primary workflow. NOTE: chart-access UX brief §2 deliberately put position-detail on a separate page — if SB4 inlines it, record the reversal in that brief.
2. **market_weather 200MA fetch window (NOT SB4-specific; bank as a Phase 14 polish item).** The 50/200 weather chart can only draw the 50MA because the benchmark fetch window is ~200 calendar days (~138 trading bars) at both sites — pipeline `_bars_or_none(ticker, window_days=200)` (`runner.py`) + the refresh handler's `get_or_fetch(ticker=benchmark)` (`routes/dashboard.py`). Widen to ≥200 trading bars (~300 calendar days) at both sites + add a regression test asserting ≥200 bars reach `render_market_weather_svg`. Small; could ride SB4 or be its own fix.
3. **theme2_annotated vcp 5-contraction cosmetic crowding (cosmetic; lowest priority).** At the worst-case 5-contraction stack the right-edge labels lightly cross the price y-axis tick numbers. Legend non-overlap (the S6 binding criterion) still passes. Bank as cosmetic polish.
4. **Schwab daily-bar wiring question (SEPARATE Phase 14 item; operator-concurred 2026-05-30).** The SMA/daily-bar path is **yfinance-only by wiring**: `OhlcvCache`/`PriceCache` are constructed plain in `swing/web/app.py:188-189` with NO `set_ladder_*` call, and `fetch_daily_bars` → `read_or_fetch_archive` refreshes only the yfinance archive shape. The Schwab market-data ladder (`swing/integrations/schwab/marketdata_ladder.py`, gated `env==production AND marketdata_ladder_enabled`) is pipeline-side, not installed on the web caches. Wiring Schwab daily bars onto the web SMA path is a code change touching the L2-locked Schwab call surface → a deliberate separate Phase 14 item, NOT folded into SB4 silently. Operator concurred it's a separate phase.

## Operating disciplines (binding — same as SB3; one NEW)

- **Merge:** Codex-convergence + QA-pass IS the trigger for brainstorm/writing-plans; operator-witnessed gate-pass IS the trigger for executing-plans. Do NOT ask "shall I merge" (`feedback_orchestrator_performs_merge`).
- **NEW — never claim false-green (`feedback_no_false_green_claim`):** after every merge, RUN `python -m pytest -m "not slow" -q` ON THE MERGED HEAD and READ the actual result before claiming green or advancing. Do NOT carry a branch/older-day pass-count forward. (The prior orchestrator claimed "6735 green on main" from the branch run; the real post-merge run was 4 failed — a pre-existing date-sensitive test bug fixed at `0c92d39`.) **Date-sensitive-fixture gotcha candidate for CLAUDE.md:** `pd.bdate_range(end=<date>, periods=N)` returns N-1 rows when `end` lands on a weekend; never pair a hard-coded N-length value array with it — derive the array from `len(idx)`.
- **QA every implementer product against disk** before merge (branch/trailers/merge-base; scope; schema; LOCKs; spot-check Codex catches vs production).
- **Commit trailer hazard:** keep the FINAL `-m` paragraph plain prose; verify `git log -1 --format='%(trailers)'` is `[]` before every push.
- **Codex MCP OFF PURVIEW** (operator investigating the 1s timeout); implementers use the `codex exec` CLI backstop + `resume --last` with inline artifacts (`-c sandbox_mode="read-only"` on resume, NOT `-s`).
- **Inline prompts:** every dispatch brief gets a paste-ready inline implementer prompt in chat; commit the brief BEFORE the prompt.
- **CLI:** `python -m swing.cli` in worktrees. After an executing-plans merge, reinstall `swing` from main (`pip install -e . --no-deps`).
- **Visual gate (if SB4 ships chart surfaces):** the rendered chart is binding; SB3 operator preference was operator-driven browser + orchestrator DB-side probes — re-confirm for SB4. For surfaces with no live data to exercise them, the orchestrator-render-to-PNG + Read fallback works (used for SB3 S6).
- **NO `Co-Authored-By`; NO `--no-verify`.**

## Forward path

SB4 brainstorm → writing-plans → executing-plans (each with its Codex chain + the merge/gate discipline) → SB5 (metrics overview; P14.N5; matplotlib SVG per Q5) → Phase 14 close-out review (Sec 9.1 Q6: all 5 sub-bundles merged + operator browser-witnessed cross-sub-bundle integration). The Schwab-daily-bar-wiring item (banked follow-up #4) is a separate Phase 14 item to sequence with the operator after the 5 sub-bundles.

---

*End of handoff. Clean boundary: SB3 SHIPPED end-to-end at `edd098d`; main = `890f2d5`. First action: author the SB4 (review + journal UX; CR.1 + P14.N6) brainstorm dispatch brief (mirror SB3's brainstorming dispatch brief) + inline prompt, carrying the 4 banked follow-ups, then drive the SB4 cycle. v23 is live; the temporal-log (v22) + chart-surface (v23) substrates are LOCKED.*
