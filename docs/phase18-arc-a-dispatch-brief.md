# Phase 18 Arc 18-A — Temporal-log NaN writer fix + shared finiteness predicate (dispatch brief)

**Authored:** 2026-06-13 by CHARC. **Sources (both committed):** RD commissioning brief [`docs/temporal-log-nan-writer-fix-commissioning-brief.md`](temporal-log-nan-writer-fix-commissioning-brief.md) (demand + locks + verification mandates) · CHARC architecture pass [`docs/phase18-rd-briefs-charc-architecture-pass.md`](phase18-rd-briefs-charc-architecture-pass.md) §Brief-1 (conditions C1–C3 + the LOCKED backfill decision). **Tripwire:** PASSED (writer in `swing/pipeline`; the shared predicate in `swing/data` — no schema this arc).
**Cycle shape:** **writing-plans → executing** (NO brainstorm — see §Cycle below). Codex adversarial review to convergence at each phase; persist every round's RESPONSE to a gitignored file. Worktree `<repo>/.worktrees/<name>`.

## Mandate (writer fix ONLY)
Non-finite OHLC must never enter the temporal log. Add a finiteness guard to `build_ohlc_today_json` (`swing/pipeline/temporal_metadata.py`), mirroring Arc-8 semantics, via a SHARED predicate both write paths consume. **The backfill of the 103 existing NaN rows is WITHDRAWN (operator-LOCKED 2026-06-13) — out of scope; they age out.**

## Resolved open questions (RD brief §4 — do not re-litigate)
- **Writer behavior = SKIP-with-warning** (mirror Arc-8's "never persist bad data; leave the hole; the engine tolerates a hole, not a NaN"), NOT reject-and-raise. The skip emits a `warnings_json` entry (auditable; partial-closes the going-forward observability).
- **The 103 rows / backfill = WITHDRAWN** (locked; three independent reads converged — payoff ~1 priced name, not worth eroding the anti-#26-drift guarantee). Not this arc.
- **Excluded-reason observability = DEDUP'd to Brief 2 (arc 18-D)**, NOT built here (C3) — folding it in would duplicate the monitor.

## Binding conditions (CHARC architecture pass — verified at QA)
- **C1 — shared finiteness predicate, not a third copy.** Extract a pure predicate (e.g. `is_finite_ohlc_bar(...)`) / lift `_trim_trailing_ragged`'s finiteness core into ONE shared helper in **`swing/data/`** that BOTH `ohlcv_archive` and the temporal-log writer consume. **Import direction: `temporal_metadata` (pipeline) imports FROM `swing/data` — NEVER the reverse** (the §4.1-verified-healthy layer rule; `swing/data` must not import `swing/pipeline`).
- **C2a — writer fix only.** No migration, no data mutation, no operator data-gate; normal cycle.
- **C3 — observability dedup'd to 18-D** (above).

## LOCKS (RD brief §3)
1. Do NOT weaken `validate_bars` to accept NaN — the engine's honest-rejection gate stays (belt to the writer's suspenders).
2. PRESERVE the existing completed-session / key-presence / provider guards in `build_ohlc_today_json` (ADD finiteness; remove nothing).
3. Append-only / immutable-log discipline holds (no in-place mutation of existing rows — and there's no backfill this arc anyway).
4. Interior-valid bars preserved — the Phase-15 bad-bar-accept posture for HISTORICAL interior bars is unchanged; this guards non-finite OHLC at the write barrier only.
5. NO schema (the only Brief-1 schema path was the withdrawn backfill).

## Verification mandates (RD brief §5)
- **Failing test from the REAL 06-10 shape:** a completed-session bar (`date ≤ cutoff`), keys present, `provider="yfinance"`, `Close=NaN`, O/H/L/V finite. Current `build_ohlc_today_json` MUST accept it (red); the fixed barrier MUST skip it (green). Compute the assertion under both paths (memory `feedback_regression_test_arithmetic`).
- **Discriminators:** a fully-valid completed bar still records (no over-eager rejection); an interior-valid bar is preserved; the all-NaN F6 case and the single-field-NaN trailing case both covered; the Volume-only-NaN exemption from Arc-8 reconciled (the shared predicate must treat Volume-only-NaN the same way both paths do).

## Cycle: why no brainstorm
RD's brief §6 nominally routed brainstorm→writing-plans→executing, but its open design questions (§4) are now RESOLVED (skip-with-warning; backfill withdrawn; observability→18-D), so there is no design fork left for a brainstorm to settle — only plan-level detail (the predicate's exact API/placement, the Volume-NaN reconciliation, the test discriminators). Same shape as 17-A/17-B (locked design → writing-plans → executing). **If the operator or RD wants the full brainstorm anyway, that's a one-word change.**

## QA + merge gating (THREE-eyes — RD kept up through the measurement core, operator 2026-06-13)
- **Merge gate (all three before merge):** (1) orchestrator QA-against-disk + full fast suite green on the merged head + ruff; (2) CHARC verification of C1–C3 + the locks + tripwire; (3) **RD measurement-chain QA — MERGE-BLOCKING** (RD is up through Phase 18's measurement core 18-A/B/C/D; 18-A touches the instrument RD owns, so RD-eyes-before-merge is the point). Each reviews its own dimension: orchestrator = tactical/disk, CHARC = architecture, RD = measurement integrity (the validate_bars interaction, the Volume-NaN reconciliation, that skip-with-warning preserves the honest-rejection semantics RD relies on).
- **Return report:** the ORCHESTRATOR posts to `charc, rd, operator` (`--type return_report`) AFTER its QA (§5.6 — the implementer reports to the orchestrator, never directly to a director inbox). Itemize C1–C3 + lock compliance verified on disk, the test discriminators, Codex rounds + verdict. CHARC + RD then QA their dimensions from the report + disk before the operator authorizes merge.
- *(Three roles now commit to `main` concurrently — CHARC docs, RD its monitor/charter, orchestrator code. Pathspec-commit discipline applies, charter §5.8.)*
