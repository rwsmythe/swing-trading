# CHARC — Current State (single source of truth)

> **OVERWRITE this file each session/handoff — do NOT append.** This is the one always-current state pointer for the CHARC (Tool Development Director) role. The dated session log in [`docs/tool-director-context.md`](tool-director-context.md) §6 is APPEND-ONLY history; current state lives HERE only. Bootstrap reads this file FIRST. Convention: [`docs/harness-architecture.md`](harness-architecture.md) §6.

**Last overwritten:** 2026-06-16. **Phase 18 ACTIVE** (data-collection integrity). **Schema v30.** main HEAD `bc8acee6`; ahead of origin, **not pushed** (operator cadence). ZERO `Co-Authored-By` intact. NOTE: `main` HEAD moves under concurrent orchestrator generations — use a `git symbolic-ref --short HEAD == main` guard + pathspec commits (§5.8; a detached-HEAD race dangled a commit earlier this session).

---

## ONE live workstream

1. **Harness scaffold — FIX-PASS DISPATCHED (orch-1); awaiting return.**
   - Build returned + QA'd (branch `scaffold-build` @ `dbac3b2`); review-strong CONVERGED; the separate codex-auto-review surfaced 0C/4M/2m. **CHARC adjudicated** + bundled the operator-directed state-pointer convention into a pre-accept fix-pass. **Brief:** [`docs/harness-scaffold-fixpass-brief.md`](harness-scaffold-fixpass-brief.md) (`5ecd9511`). Dispatched to an `implementer-opus-high` cell.
   - **Scope:** A1 MAJOR-2 atomic registry write (required) · A2 MAJOR-4 delete vestigial `SUBSTRATE_EXCEPTION_RELPATHS` (**broad guard model RATIFIED**; brief §C2 = durable record) · A3 MAJOR-3 robustness companion (low-pri) · A4 MINOR-2 verify/harden the hook import-before-exit-0-guard · **A5 the `<role>-state.md` convention bundled into the scaffold**. CITED V2: MAJOR-1 + MINOR-1.
   - **ON RETURN → MY LEG:** build-vs-plan/spec verify (every fix on disk; the C5 convention present + charc-bootstrap reads-state-first; genericity guard green whole-tree; §2.1 manifest 18→19; R1 CRITICAL session_id validation intact) → **operator bootstrap-dry-run witness** (bare clone) → accept (merge `scaffold-build` → master in harness-template). Re-gate before return: review-strong (repo-access, binding) + codex-auto-review.

## CHARC follow-ups surfaced (not yet actioned)

- **F1 — codex-auto-review WSL-CRLF phantom-finding noise mode.** Running B via WSL against a Windows CRLF tree recurrently emits a FALSE "repository-wide line-ending rewrite" finding (seen 18-H.4 + 18-H web-polish; the latter's "cli.py 5621-line rewrite" — CHARC-verified false on disk). **Adjudication rule (immediate):** cross-check any B line-ending-churn finding against the Windows-side `git diff --numstat` before treating it as real. **Candidate -H (optional):** a `.gitattributes` normalization policy kills it at the source — but that is itself a non-trivial repo-wide renormalization (its own one-time churn + risk), NOT a quick fix. Adoption-scoring signal for the tool I own.
- **F2 — deferred Accept-header media-range looseness** (web-polish R2 Minor): `"text/html" in accept_header` would serve HTML to a `text/html;q=0` client; PRE-EXISTING, the new 404 branch mirrors `_handle_validation_error` (brief LOCK). A proper fix is a shared media-range parser touching BOTH handlers — a D8-like two-handler dup; candidate follow-up.

## Pending CHARC items (operator-sequenced, behind the fix-pass return)

- **18-H.1** — CHARC product-decision (tokens-absent→yellow `_check_schwab_token` contract) BEFORE dispatch.
- **18-H.6** — orphan broker position = **TRIPWIRE** (schema enum-widen OR `swing/trades`) → CHARC architecture pass at commissioning.
- **18-H.7** — `role_mail`-on-ATTENTION = CHARC comms-sender ruling + nightly-pipeline-step touch.
- **18-H.5** — dead-code audit (brief `f3b95d3e`). · **18-G** — brief sweep (D10).
- **AT PHASE-18 CLOSE:** CLAUDE.md line-3 re-compaction + the §6 session-log compaction (overdue/verbose).

## Closed / shipped this session window

- **Web-polish 18-H.2 + 18-H.3 + R1 SHIPPED + CLOSED** (`e53b0886`; close `bc8acee6`; operator browser gate 3/3; 8565 green; ruff clean). CHARC no-block QA verified on disk: 8-file delta, NO cli.py, no CRLF churn, trailers clean; review-strong effort=high confirmed; codex-auto-review B clean of real findings (only the F1 false-positive).
- **Director current-state-pointer convention SHIPPED** (`fb4b61a9`) — this file + `rd-state.md` scaffold + both bootstrap rewords + `harness-architecture.md` §6. THIS file is the reference instance.
- **Harness-scaffold codex-auto-review ADJUDICATED** + fix-pass brief committed + dispatched (`5ecd9511`).
- 18-D nightly half + 2 calibrations (`4d17492b`); 18-H.4/.4.1 Schwab self-lock (`1a916375`); the codex-auto-review A/B → 3 binding harness changes (`00199c51`, adopted, `da22b9d8`); harness brainstorm→spec→writing-plans (`4d148a79`).

## Debt register snapshot (§4)

CLOSED D6/D3/D11/D13/D14 · PARTIAL D1 · WATCH D5/D9/D12 · OPEN D7(=R1, now declared — verify at fix-pass/close)/D8(trigger-gated; F2 is a fresh instance)/D10(=18-G)/D15(base-VM base-field hand-duplication ~15 VMs).

## Probe / hygiene

Bootstrap probe: all within thresholds, no ATTENTION. INFO: `exports/` 42 dated (+30 research) = D3 (tracked, tiny residual). My inbox: 0 unread.

## Behavioral load-bearing (don't relearn the hard way — full text in charter §5)

§5.1 director = PEER, push back at a LOW threshold (no deference-drift after a correction) · **FYI ≠ act — action needs EXPLICIT direction** (else acknowledge+assess+await) · §5.7 verify-the-negative on disk before asserting · §5.8 **pathspec-commit + `symbolic-ref==main` guard** (3 roles share main) · §5.9 orchestrator scope is swimlane-limited (harness architecture routes to CHARC) · §2.7 directors do design dialogue, NEVER run copowers cycles · commit briefs BEFORE the inline prompt · QA on disk, never from the self-report.
