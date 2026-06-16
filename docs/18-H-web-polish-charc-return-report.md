# 18-H web-polish (18-H.2 + 18-H.3 + R1) — orchestrator return report

**To:** CHARC · **From:** orchestrator · **Date:** 2026-06-16
**Arc:** Phase 18 web-polish batch (FIX-DIRECT). **Brief:** `docs/18-H-web-polish-dispatch-brief.md` (`350180ff`).

## 1. Outcome — SHIPPED + CLOSED
Merged to `main` at **`e53b0886`** (rebased twice onto the advancing main — the harness arc landed `fadef861`→`fb4b61a9`→`b118a2c2`, all docs-only, zero overlap; both rebases clean). **Operator browser gate 3/3 PASS.** Merged-head no-false-green: **8565 passed, 5 skipped**, `ruff check swing/` clean. Trailers all empty. Cell: implementer-opus-high.

## 2. The three items
- **18-H.2 (404 surface unify):** `_handle_http_exc` now routes a non-HTMX GET that accepts HTML through `page_error.html.j2` — builds `PageErrorVM` mirroring `_handle_validation_error`, `status_code` preserved, `exc.headers` preserved (a 405's `Allow` — Codex R1 Minor), API/JSON clients fall through unchanged. 404s render base + the 18-F stoplights via the context processor (no per-VM field; the gotcha stays sidestepped). The bare-unhandled-500 + HTMX-fragment paths untouched.
- **18-H.3 (drill-down dots):** `health_tool.html.j2` + `health_research.html.j2` render the colored `.stoplight-<color>` dot (reusing the topbar classes), with `role="img"` (Codex R2 Major — a roleless span's aria-label isn't robustly exposed) + the status word in `title`/`aria-label` (a11y + the word-grep tests survive). No new CSS.
- **R1 (`requests` declared):** `"requests>=2.31"` added to `[project.dependencies]` (floor matches the resolved 2.33.1; already used in finviz_api + schwab auth — declaration-correctness, not a new dep). Guard test added.

## 3. Reviewer A (review-strong, repo-access, effort=HIGH — verified)
Converged R3 (`NO_NEW_CRITICAL_MAJOR`, "No findings"). **`reasoning effort: high` confirmed in every round's raw transcript header** (the `da22b9d8` recipe fallback fix held — the 18-H.4.1 effort=none gap did NOT recur). Repo-access read the surrounding error-handling/base/VM/context-processor code. Findings: R1 (Minor: `exc.headers` stripped → preserved + an Allow-header regression test; Nit: detail fallback) + R2 (Major: a11y `role="img"`; Minor: Accept `q=0` substring — DEFERRED, see §5) → R3 clean. Artifacts: `.worktrees/18-H-web-polish/.copowers-findings.md` + `.codex-review-r1..r3.txt`.

## 4. Reviewer B (codex-auto-review, GATING, repo-access, effort=HIGH) — clean of real findings
Ran `codex exec review --base main -c model_reasoning_effort=high` on the final tree. Verdict: the functional change is coherent; its **only** finding was a **[P2] "repository-wide line-ending rewrite"** claim (cli.py showing 5621 del / 5621 add). **This is a verified-FALSE WSL-git CRLF artifact** — I confirmed on the Windows side that the committed diff touches exactly the 8 expected files, `swing/cli.py` is UNTOUCHED, and there is ZERO whole-file LF→CRLF churn (no `add==del` large patterns). It is the documented cosmetic CRLF gotcha rendering in B's WSL environment. [P2] is non-gating anyway; CITED + dismissed with verification.
**Noise mode worth tracking (for the adoption scoring):** codex-auto-review run via WSL against a Windows CRLF working tree has a recurring **phantom line-ending false-positive** mode (also seen in the 18-H.4 B run's `git status` showing all files modified). Mitigation when scoring B: line-ending-churn findings from the WSL-run B should be cross-checked against the Windows-side `git diff --numstat` before being treated as real. A `.gitattributes` normalization policy would eliminate it at the source (candidate -H item if you want it gone).

## 5. Deferred (flagged, not fixed)
The R2 **Minor** Accept-header substring looseness (`"text/html" in accept_header` would serve HTML to a `text/html;q=0` client). PRE-EXISTING — the new branch mirrors `_handle_validation_error`'s exact behavior (the brief LOCK). A proper fix is a shared media-range parser touching BOTH handlers (separate refactor); failure mode is cosmetic (a vanishingly-rare `q=0` client gets HTML not JSON). Candidate follow-up if you want the two handlers hardened together.

## 6. Process note
Two main-advance rebases during this arc (the concurrent harness arc) — both clean, no overlap. The implementer correctly branched from current main HEAD (not the brief's already-stale base). No cwd-drift this time (all git via `git -C`).
