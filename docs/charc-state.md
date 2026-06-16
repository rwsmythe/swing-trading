# CHARC — Current State (single source of truth)

> **OVERWRITE this file each session/handoff — do NOT append.** This is the one always-current state pointer for the CHARC (Tool Development Director) role. The dated session log in [`docs/tool-director-context.md`](tool-director-context.md) §6 is APPEND-ONLY history; current state lives HERE only. Bootstrap reads this file FIRST. Convention: [`docs/harness-architecture.md`](harness-architecture.md) §6.

**Last overwritten:** 2026-06-16. **Phase 18 ACTIVE** (data-collection integrity). **Schema v30.** main HEAD advanced through the 18-H.1 merge (`1a2a774d`); ahead of origin, **not pushed since the last operator-directed push** (operator cadence). ZERO `Co-Authored-By` intact. NOTE: `main` HEAD moves under concurrent orchestrator generations — use a `git symbolic-ref --short HEAD == main` guard + pathspec commits (§5.8).

---

## ONE workstream remaining — harness scaffold: ONLY the bootstrap-dry-run + accept left

- Fix-pass + the AR-MAJOR-1 fold are **fully CHARC-verified end-to-end** (branch `scaffold-build` @ `d8ad5c9`, harness-template). My re-verify PASS on disk: A1-A5 + the `read_entries` `== path.stem` identity-invariant clause (additive AND; R1 `is_valid_session_id` still first → traversal boundary intact) + **168 unittest green (my own run)** + genericity guard green + manifest 19. Both reviewers clean (review-strong R5 NO_NEW_CRITICAL_MAJOR effort=high; codex-auto-review 0/0/0).
- **REMAINING GATE (the only one):** the **operator bootstrap-dry-run witness on a BARE CLONE** (§5.5 staged guarantee — CHARC reads `charc-state.md` first → charter → comms round-trip on the singular inboxes → hooks load + exit 0 → reaches the application-definition interview, no further setup). CHARC-op, operator-witnessed. Then → **accept** (orch-1 merges `scaffold-build` → master in harness-template).
- Durable records: fix-pass brief + AR ruling [`docs/harness-scaffold-fixpass-brief.md`](harness-scaffold-fixpass-brief.md) (§C2 = the MAJOR-4 broad-guard ratification; §F = the AR-MAJOR-1 fold ruling). After accept: the new repo's OWN CHARC germinates it (separate, later, NOT in swing).

## CHARC follow-ups (not yet actioned)

- **F1 — codex-auto-review WSL-CRLF phantom-finding noise mode** — REFINED: triggers on LARGE/multi-file diffs run via WSL (web-polish "cli.py 5621-line rewrite", 18-H.4 git-status-all-modified — both CHARC-verified false); a SMALL Python-only diff (18-H.1, the harness fold) shows NO phantom. Adjudication rule: cross-check any B line-ending-churn finding vs the Windows-side `git diff --numstat`. Candidate -H: a `.gitattributes` normalization (non-trivial repo-wide renormalization, its own churn). Adoption-scoring signal for the tool I own.
- **F2 — deferred Accept-header media-range looseness** (web-polish R2 Minor): a shared media-range parser touching BOTH 404/validation handlers; D8-like two-handler dup; candidate follow-up.

## Pending CHARC items (operator-sequenced)

- **18-H.6** — orphan broker position = **TRIPWIRE** (schema enum-widen OR `swing/trades`) → CHARC architecture pass at commissioning.
- **18-H.7** — `role_mail`-on-ATTENTION = CHARC comms-sender ruling + nightly-pipeline-step touch.
- **18-H.5** — dead-code audit (brief `f3b95d3e`). · **18-G** — brief sweep (D10).
- **AT PHASE-18 CLOSE:** CLAUDE.md line-3 re-compaction + the §6 session-log compaction (overdue/verbose).

## Closed / shipped this session window

- **18-H.1 SHIPPED + CLOSED** (`1a2a774d`; 8567 green; ruff clean) — `_check_schwab_token` configured-but-tokens-absent → YELLOW; client_id-empty stays GREEN n/a; **operator live-witness 3/3** (green/valid → yellow/logout → green/re-auth — the binding §5.10 net); both reviewers clean. CHARC spot-verified the flip + boundary on main.
- **Web-polish 18-H.2/.3 + R1 SHIPPED + CLOSED** (`e53b0886`; gate 3/3; 8565 green) — CHARC no-block QA verified on disk (8-file delta, no cli.py, no CRLF churn).
- **Director current-state-pointer convention SHIPPED** (`fb4b61a9`) — THIS file is the reference instance. **Harness fix-pass adjudicated + dispatched + the AR-MAJOR-1 fold verified** (the brief `5ecd9511`/`64b498ad`).
- 18-D nightly half (`4d17492b`); 18-H.4/.4.1 (`1a916375`); codex-auto-review A/B → 3 binding harness changes; harness brainstorm→spec→writing-plans (`4d148a79`).

## Debt register snapshot (§4)

CLOSED D6/D3/D11/D13/D14 · PARTIAL D1 · WATCH D5/D9/D12 · OPEN D7(=R1, now DECLARED in pyproject via web-polish — verify/close at phase close)/D8(trigger-gated; F2 = fresh instance)/D10(=18-G)/D15(base-VM base-field hand-duplication ~15 VMs).

## Probe / hygiene

Bootstrap probe: all within thresholds, no ATTENTION. INFO: `exports/` 42 dated (+30 research) = D3. My inbox: 0 unread.

## Behavioral load-bearing (don't relearn the hard way — full text in charter §5)

§5.1 director = PEER, push back at a LOW threshold (no deference-drift after a correction) · **FYI ≠ act — action needs EXPLICIT direction** (else acknowledge+assess+await) · §5.7 verify-the-negative on disk before asserting · §5.8 **pathspec-commit + `symbolic-ref==main` guard** (3 roles share main) · §5.9 orchestrator scope is swimlane-limited (harness architecture routes to CHARC) · §2.7 directors do design dialogue, NEVER run copowers cycles · commit briefs BEFORE the inline prompt · QA on disk, never from the self-report.
