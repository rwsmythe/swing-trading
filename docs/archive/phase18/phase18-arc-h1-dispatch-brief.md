# 18-H.1 — Schwab token health: configured-but-tokens-absent → YELLOW — CHARC dispatch brief

**Author:** CHARC. **Date:** 2026-06-16. **Phase 18, 18-H bug container.** **FIX-DIRECT.** **NO tripwire** (existing module + existing function; no schema, no dependency, no new module/package, no new standing process, no `swing/trades`/`swing/data` carve-out — self-certified).

## 1. The decision (operator-confirmed 2026-06-16)
When Schwab **IS configured** (`client_id` present) but tokens are **ABSENT** (no tokens DB, or a DB with an empty/no row), the tool-health Schwab check returns **YELLOW** (today it returns GREEN "n/a"). `client_id == ""` (never configured) **stays GREEN "n/a"** — unchanged. A deliberate `swing schwab logout` → YELLOW is **intended** (no "intentionally dormant" carve-out; operator-confirmed).

**Rationale (for the implementer's context):** configuring Schwab signals intent to use it, so tokens-absent is an actionable gap, not a benign n/a. It is literally a degraded-but-functional state — the market-data ladder falls back to yfinance and broker reconciliation is unavailable, while the pipeline still collects data — which is the textbook **yellow**. It is recoverable via `swing schwab setup`, so yellow, **not red** (red stays reserved for "broken now": expired / can't-refresh / ≤2h).

## 2. The exact change — `swing/monitoring/tool_health.py::_check_schwab_token`
- **KEEP** the `cfg is None or client_id == ""` short-circuit (≈:301-303) → GREEN "Schwab not configured (n/a)". (Also preserves LOCK #4 — the n/a path stays BEFORE the `cli_schwab` import.)
- **FLIP** `not tokens_path.exists()` (≈:319-321): GREEN → **YELLOW**, summary `"Schwab configured but not authenticated; run swing schwab setup"`.
- **FLIP** `meta is None and error_message is None` (empty / no row, ≈:324-326): GREEN → **YELLOW**, same summary (optional `detail` distinguishing "no tokens DB" vs "empty token row" for diagnostics).
- **UNCHANGED:** unreadable → yellow; issue-date-unknown → yellow; refresh-token empty → red; expired → red; ≤2h → red; ≤1 day → yellow; valid → green.
- **ASCII-only** summaries (the monitor's ASCII mandate). Read-only aggregator posture preserved — no DB write, stdlib-only in this module, lazy `cli_schwab`/schwabdev import unchanged.

## 3. Tests (distinguishing pre/post — `feedback_regression_test_arithmetic`)
- **UPDATE** the existing 18-E `_check_schwab_token` tests that assert GREEN for *configured-but-no-tokens* → assert **YELLOW** + the new summary. (Pre-fix these returned green; post-fix yellow → the assertion distinguishes. Locate via grep on the old "tokens not present (n/a)" summary.)
- **ADD** a boundary regression: `client_id == ""` + no tokens DB → still GREEN "n/a" (guards against over-flipping the never-configured case — passes BOTH pre and post, so it pins the boundary).
- **CONFIRM unaffected:** configured + valid tokens → GREEN; configured + empty refresh_token → RED.
- **AUDIT `compute_tool_health` overall-status tests:** any fixture that configures Schwab WITHOUT tokens now yields **overall = YELLOW** (the rollup is `worst_of`) — update those assertions. This is the intended visible effect (the topbar tool-health stoplight goes yellow while Schwab is configured-but-unauthed).

## 4. Gates
- **review-strong** (gpt-5.5/high, repo-access — binding) to convergence; **codex-auto-review** (repo-access, matched-HIGH — the adopted gating-complementary second eye; production code). Save each round's response; verify Reviewer A ran at effort=high.
- **BINDING operator live-witness (§5.10 — the 18-E lesson: for a monitor *read-path* change, the live-config witness is the true net, not the byte-tests or Codex).** On the operator's live system: the topbar tool-health stoplight shows **GREEN with valid Schwab tokens** (NO false-yellow regression — the failure mode that matters here), and **YELLOW after `swing schwab logout`**, then GREEN again after `swing schwab setup`. This is BINDING because a flip bug could false-yellow a validly-authed system, and only the live witness catches it (the exact 18-E weather_freshness shape).
- Merged-head no-false-green fast suite + `ruff check swing/`.

## 5. Locks / return
- No schema / dep / module / standing-process / carve-out (no tripwire). The §3 n/a-before-import LOCK #4 preserved. Conventional commits, **ZERO `Co-Authored-By`**, no `--no-verify`.
- The IMPLEMENTER reports to the ORCHESTRATOR in chat — never posts to a director inbox; the ORCHESTRATOR posts the return to charc AFTER its QA.

**Cell:** `implementer-sonnet-high` (surgical, settled design; the §5.10 false-yellow risk is netted by the binding operator live-witness, not by raw model power — bump to opus-high only if the overall-rollup test audit proves broader than the two flipped cases).
