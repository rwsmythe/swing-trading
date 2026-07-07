# Phase-19 Close Audit — CHARC

**Auditor:** CHARC (Tool Development Director). **Date:** 2026-07-07 HST. **Audited HEAD:** `0d560822` (the Option-C coda — the phase's LAST substantive commit; supersedes the housekeeping head `b530f3ac`).
**Phase:** 19 — Launch-Context Robustness & Measurement Parity (scoped 2026-07-02, [`phase19-scope-charc.md`](phase19-scope-charc.md) → archived at close). **Duration: five days, scope-to-close.**

## §1 Verdict

**CLEAN TO CLOSE.** All six arcs + D21/R3/R4 + the close-housekeeping bundle + the Option-C coda shipped, witnessed, and verified. Every binding gate re-verified by CHARC directly on disk (not from reports). Zero schema changes (the phase prediction held). Zero tripwire false-negatives. The phase's one standing-process addition (the weeknight scheduled task) is live and has completed its first two autonomous fires.

## §2 Binding gates (each verified by CHARC first-hand at/around the audited HEAD)

| Gate | Result | CHARC verification |
|---|---|---|
| Merged-head fast suite | **9033 passed / 5 skipped / 0 FAILED** | CHARC's own fresh `-n auto` run on `0d560822` (see §2.1) — postdates the phase's last substantive commit (the D21 green-postdates rule, honored) |
| ruff | clean | own run |
| Schema | **v31**, latest migration 0031 (pre-phase) — **ZERO Phase-19 migrations** | `EXPECTED_SCHEMA_VERSION` + migrations dir read |
| `Co-Authored-By` streak | intact (orchestrator deep-scan 3915 at the coda; CHARC 200-commit window corroborates zero non-empty trailers) | own trailer scan |
| Harness probe | zero ATTENTION — **including the new H2 research-size ceilings live** (exports/research 1.9 MB/500; research/harness 2.2 MB/200) | own run |
| Brief corpus | top-level `docs/*.md` 39→**28** (the §4.3 sweep; 14 dead artifacts → `docs/archive/phase19/`) | own count |
| The D21 sweep-safety step (FIRST exercise) | PASSED — pre-sweep moved-path grep zero-hit; post-sweep suite green; extended mid-close to tracked-config changes after the H4 break | grep + suite verified |
| Untracked drift | shadow-expectancy `??` noise **0** (was 28 dirs, accruing nightly); `.codex/` ignored; `AGENTS.md` tracked; `diag_5` retired | `git status --porcelain` + `check-ignore -v` proof |
| Reproducibility contract | **REAL, not aspirational:** 16 cited ledger files git-TRACKED in the T4 study's `artifacts/` (4 artifacts incl. the operator-approved T3 golden gate); the study test asserts actual tracking via `git ls-files` | `git ls-files` count + test read |

### §2.1 The audit suite run
`9033 passed / 5 skipped / 0 failed` — CHARC's own run on `0d560822` (results recorded at commit time of this audit; the two skips are the standing pinned pair).

## §3 Per-arc roster (all CLOSED)

| Arc | Merged | Witness/terminal gate | Notes |
|---|---|---|---|
| 19-A coverage_gaps trailing-delisting | `fadc193d` | live-DB RED 100→GREEN 0 witnessed | the CNTA cry-wolf class dead; RD's consequence-#2 bless carries 2 durable locks |
| 19-B anchor-consistency + lease-or-silent + guard | `3234f19a` (+ belt `44b3bbd9`) | both witness halves PASS (seed stamped; worktree repro no-poison/no-post) | **the #5 saga (June) ENDS**; suite provably cannot spam the T1 channel |
| 19-C weeknight scheduled task | `e3f1a442` | stage (a) all-five PASS + stage (b) the first true 17:30 fire (run 125, a real 5.5-min nightly) | the phase's §3 tripwire arc — C1–C6 held end-to-end; 3 runbook defects found ONLY by the live witness, fixed `e07016cf` |
| 19-D shadow-engine hardening | `f1add34c` | **RD T4 re-read: CONFIRMED-NEGATIVE, FINAL — "the healing is exact" (A+ headline = RD's hand-walk to 4dp)** | triple-confirmed complementary review; VSTS +27R pathology dead; 16 ragged-walk signals recovered; A+ selectivity validation BANKED |
| 19-E Day-3-5 calendar partial advisory | `d68ccfe6` | AMN fired at exactly session-day 3 (the natural witness DISCRIMINATED the sessions-vs-calendar ruling live); VSTS out-of-window silent | the live/measured ruleset parity gap closed; add-alongside preserved +1R untouched |
| 19-F orphan-tolerant resolution | `1ff15898` | the operator resolved disc 73 via the NEW GUI path; badge predicate 0; badge gone | the phase's originating operator complaint healed through the supported path |
| D21/R3/R4 (mid-phase) | `c2ee1d98`/`2d626b27` | main restored to true 0-failed | the Phase-18 sweep's 6-test break; the sweep-safety discipline + RD's arc-lifecycle test standard are the durable residue |
| Close bundle H1–H4 + ritual | `722358a5`..`b530f3ac` | probe zero-ATTENTION; fail-open hook sanity witnessed | H5/D22 correctly deferred (production code ≠ housekeeping) |
| Option-C coda | `0d560822` | contract test 3/3; noise 0 | the crossed-rulings sequence resolved to a design better than either director's first draft |

## §4 Tripwire traffic + false-negative check

One §3 tripwire crossed all phase: **19-C (new standing process)** — architecture pass embedded in the brief (C1–C6), all conditions verified honored through merge + witness. Carve-outs: 19-E (`advisory.py`) + 19-F (`schwab_reconciliation.py`) — both CHARC-passed in-brief, both verified scope-exact on disk at return. **19-F's schema watch-point held:** the plan used the existing enum; no CHECK widening (the STOP-to-CHARC clause never fired, correctly). Sub-tripwire self-certs (19-A/B/D + the bundle): all verified accurate at returns. **Zero false-negatives.** One self-cert CORRECTION mid-phase: RD's 19-E "no tripwire apparent" missed the carve-out — caught at scoping (procedural cost only), logged in the scope doc's corrections-of-record.

## §5 Register motion this phase

- **CLOSED:** D21 (opened + closed in-phase) · D18-FORM (H2) · F1 (WSL-CRLF phantom — recipe `896c67d7`) · F6/R1 (the stop-hook back-port) · the #5 item itself (19-B).
- **OPENED:** D22 (the ungated general `discrepancy resolve` — **deferred to Phase-20**, the headline carry-over).
- **UNCHANGED WATCH:** D1 (runner size) · D5 (suite ~4:12 at 9033 — approaching the ~5-min watch line; note for Phase-20) · D8 · D9 · D12 · D15 (base-VM consolidation, still the largest open consolidation) · D16 (exonerated in the 19-F diagnosis but unfired) · D17 · D11 (orchestrator-context ~109K).
- **New durable disciplines banked:** the D21 sweep-safety step (+ its tracked-config extension) · RD's arc-lifecycle test standard (retirement markers) · the dry-run-snippets rule · signature-scoped session belts · the cite=commit reproducibility convention (RD folds into watch-standard §3) · backtick-free `role_mail` bodies.

## §6 CHARC self-critique (owned errors, all caught by the layered net)

1. **The D21 audit-green gap (structural, mine):** the Phase-18 close audit's "suite green" predated the sweep commit; main sat 6-red for 6 days. Fix: the green-postdates-last-commit rule — exercised for the first time at THIS close (both the housekeeping suite and this audit's own run postdate the last substantive commit).
2. **The C4 "self-heals" note (mine):** asserted lease self-healing while the disproving `IntegrityError` branch sat in my own quoted excerpt. Caught by review-strong. Lesson banked: reading code ≠ walking the full branch — and it immediately paid for itself in the shadow-expectancy pruner trace (§6.4).
3. **The invalid_ohlc "delisting churn" mischaracterization + the 19-F "unresolvable via CLI" overstatement (mine):** both corrected by RD's live probe / the implementer's reproduction respectively; both owned on the record (D22 carries the second).
4. **The symmetric close:** RD's A-narrow ruling missed the pruner interaction exactly the way my C4 note missed the lease index — each director caught the other's untraced-neighbor error within minutes, and the final Option-C design (RD's, rejecting even my exemption patch as needless coupling) was better than either first draft. The peer model + layered net (director review → orchestrator QA → Codex ×2 → merged-head suite → live witness) caught every one of the phase's five director-level errors; **nothing reached a witnessed merge wrong.**

## §7 Carried to Phase-20 (the CHARC scope-proposal seed list)

**D22** (the pending-state gate on general `discrepancy resolve`) · **S4U/explicit-data-root** (true logged-off unattended runs, deferred at 19-C) · **D15** (base-VM consolidation) · **D5** (suite runtime approaching the watch line) · the comms_unread_hook bare-import hardening (the H1 implementer's out-of-scope observation) · the AGENTS.md maintenance policy (CHARC recommendation: thin-pointer conversion, NOT co-maintenance — it is a 61K parallel CLAUDE.md already two phases stale; operator decides) · the dead-gen session-registry tidy (low value, deferred) · RD's floor-ratio 0.15–0.2 band watch item (his lane, realized-evidence-only).

**Phase 19 is CLOSED.**
