# CHARC — Current State (single source of truth)

> **OVERWRITE this file each session/handoff — do NOT append.** This is the one always-current state pointer for the CHARC (Tool Development Director) role. The dated session log in [`docs/tool-director-context.md`](tool-director-context.md) §6 is APPEND-ONLY history; current state lives HERE only. Bootstrap reads this file FIRST. Convention: [`docs/harness-architecture.md`](harness-architecture.md) §6.

**Last overwritten:** 2026-06-16. **Phase 18 ACTIVE** (data-collection integrity). **Schema v30.** main HEAD = the doc-ship commit that added this file (was `081fe660`); ahead of origin, **not pushed** (operator cadence). ZERO `Co-Authored-By` intact.

---

## Two live workstreams (two orchestrator generations; operator manages them)

1. **Harness scaffold — BUILD RETURNED + ORCHESTRATOR-QA'd (orch-1); PENDING CHARC decisions before accept.**
   - Repo `C:/Users/rwsmy/harness-template`, branch `scaffold-build` @ `dbac3b2` (34 commits, trailers clean). NOT merged to master, NOT pushed. Findings: `<new-repo>/.copowers-findings.md` + `<new-repo>/.codex-auto-review.txt`.
   - Orchestrator QA: Phase-1 disk PASS (158 unittest green; whole-tree genericity guard GREEN; zero-hard-dep core proven; manifest exact 18 files; cross-repo honored). Phase-2 review-strong CONVERGED (R1 1C+2M incl. a real session_id PATH-TRAVERSAL caught by repo-access; R2 2M; R3 clean — fixes disk-verified). Phase-3 codex-auto-review (repo-access, matched-HIGH, freeform — no diff-base on an unborn master): 0C / 4M / 2m.
   - **PENDING ME (3 things; operator will discuss):** (a) **MAJOR-4 guard-contract RULING** — the §8 genericity guard's `SUBSTRATE_EXCEPTION_RELPATHS` is vestigial (substrate vocab forbidden only in `review-gate-seam.md`); rule tight §8(c) allowlist vs the broad "allowed-except-seam-doc" the implementer built (= implementer flagged-deviation #1; the FORBIDDEN app/domain vocab IS whole-tree-checked — this is substrate-scoping only, not a contamination hole). (b) **fix-pass decision** — orchestrator RECOMMENDS a small targeted pass: MAJOR-2 atomic registry write (registry uses non-atomic `write_text`; inconsistent with the build's own `temp+os.replace` mail delivery) + MAJOR-3 datetime-sort/skip-malformed companion (same file), ~3–4 commits + tests, re-review review-strong → then accept. MAJOR-1 (multi-recipient delivery non-atomic) + 2 minors = cited best-effort/V2.
   - **THEN:** CHARC build-vs-plan/spec verify → operator bootstrap-dry-run witness (§5.5 staged guarantee, bare clone) → accept. After accept: the new repo's OWN CHARC bootstraps it (germination — separate, later, NOT in swing).

2. **Web-polish run — EXECUTING (orch-2).** 18-H.2 (route the 404 through `page_error.html.j2` → renders base + the 18-F stoplights) + 18-H.3 (drill-down status → the `.stoplight-<color>` dot, word kept in title/aria-label) + R1 (declare the already-used `requests` dep). Brief `350180ff`; `.worktrees/18-H-web-polish` from main `41050cdc`; `implementer-opus-high`; review-strong+repo-access+codex-auto-review. FIX-DIRECT, NO tripwire. **ON RETURN → CHARC QA the diff (no block) + the operator BINDING browser gate** (TestClient can't see the render).

---

## Pending CHARC items (operator-sequenced, behind the two returns)

- **18-H.1** — needs a CHARC product-decision (tokens-absent→yellow `_check_schwab_token` contract) BEFORE dispatch.
- **18-H.6** — orphan broker position = **TRIPWIRE** (schema enum-widen OR `swing/trades`) → CHARC architecture pass at commissioning. (`phase18-todo` §18-H.)
- **18-H.7** — `role_mail`-on-ATTENTION = CHARC comms-sender ruling (`VALID_FROM` extension vs `--from rd`) + a nightly-pipeline-step touch.
- **18-H.5** — dead-code audit (brief `f3b95d3e`).
- **18-G** — brief sweep (D10).
- **AT PHASE-18 CLOSE:** CLAUDE.md line-3 re-compaction (over the soft threshold) + the §6 session-log compaction (line-3-style collapse-to-pointer; overdue/verbose).

## Closed recently (this session window)

- 18-D nightly half + 2 calibrations (`4d17492b`) — the 2026-06-13 data-collection audit chain FULLY closed.
- 18-H.4 + 18-H.4.1 Schwab re-auth self-lock (`1a916375`, operator re-auth witnessed).
- The **codex-auto-review A/B closed DECISIVELY POSITIVE** → 3 now-binding harness changes: (1) the binding review runs WITH REPO ACCESS (`00199c51`); (2) codex-auto-review ADOPTED as a gating-complementary second eye on production-code arcs; (3) the `effort=none` fallback gap fixed (`da22b9d8`).
- Harness brainstorm→spec(`94859ba1`)→writing-plans (merged `4d148a79`).
- **This session:** the director current-state-pointer convention (this file + `rd-state.md` scaffold + both bootstrap rewords + `harness-architecture.md` §6).

## Debt register snapshot (§4)

CLOSED D6/D3/D11/D13/D14 · PARTIAL D1 · WATCH D5/D9/D12 · OPEN D7(=R1)/D8(trigger-gated)/D10(=18-G)/D15(base-VM base-field hand-duplication ~15 VMs — future paydown).

## Probe / hygiene

Last probe (bootstrap): all within thresholds, no ATTENTION. INFO: `exports/` 42 dated (+30 research) = D3 (tracked, tiny residual). My inbox: 0 unread.

## Behavioral load-bearing (don't relearn the hard way — full text in charter §5)

§5.1 director = PEER, push back at a LOW threshold (no deference-drift after a correction) · **FYI ≠ act — action needs EXPLICIT direction** (else acknowledge+assess+await) · §5.7 verify-the-negative on disk before asserting · §5.8 **pathspec-commit `git commit -- <file>`** (3 roles share main) · §5.9 orchestrator scope is swimlane-limited (harness architecture routes to CHARC) · §2.7 directors do design dialogue, NEVER run copowers cycles · commit briefs BEFORE the inline prompt · QA on disk, never from the self-report.
