# CHARC — Current State (single source of truth)

> **OVERWRITE this file each session/handoff — do NOT append.** The one always-current state pointer for the CHARC (Tool Development Director) role. The dated §6 log in [`docs/tool-director-context.md`](tool-director-context.md) is APPEND-ONLY history; current state lives HERE. Bootstrap reads this FIRST. Convention: [`docs/harness-architecture.md`](harness-architecture.md) §6.

**Last overwritten:** 2026-07-15 (**the GENERATIONAL-HANDOFF overwrite — the prior CHARC gen [bootstrapped 2026-07-02, ran Phases 19+20] signs off; you are the fresh generation.** PHASE 20 CLOSED, audit CLEAN at `e3b6570f`. **NEXT CHARC deliverable: the Phase-21 scope proposal (§2.3) — NOT drafted; await the operator.**)

---

## #1 — PHASE 20 CLOSED 2026-07-15 (audit CLEAN). The board is EMPTY. Phase-21 scoping is the next decision, at the operator's cadence.

**Fresh CHARC: read this lead, then the TWO close audits ([`phase20-close-audit-charc.md`](phase20-close-audit-charc.md) + [`phase19-close-audit-charc.md`](phase19-close-audit-charc.md) — verdicts, rosters, register motion, the self-critiques), then the charter §5 + §6 for the durable rules and how-we-got-here. Do NOT re-derive phase history — the audits + `docs/archive/phase19|20/` + git carry it.**

**Phase 20 in one paragraph:** the $10.94 cash-review badge the operator refused to acknowledge (2026-07-10) decomposed — via a full operator-transcribed broker-history reconciliation — into 3 corrupted fill rows (the tier-1 auto-corrector wrote the WRONG LEG's price on same-qty pairs; its own audit table confessed), a phantom test trade, and $0.20 of true penny drift. Phase 20 fixed the corrector (ambiguity→tier-2, side/date/2%-band guards, re-correction alarm, fills↔trades invariant), corrected the data through audited overrides, voided the phantom no-schema, gated the ungated CLI resolve (D22), gave the coherence badges destinations that route to the DATA FIX (D23/D24), and hardened three riders (stop-hook fail-open; AGENTS.md → a 23-line pointer with codex-follows-it verified; the registry singleton reconciled). Ledger↔broker now reconciles TO THE CENT dual-path; AMN's H1 outcome healed −$9.60→+$1.17 EXACT; the guards proven in anger (run 78 + five scheduled runs over the exact causal geometry, zero re-corruption). Suite **9115/5/0** (audit own-run, 5:14). Schema **v31 — TWO consecutive zero-migration phases.** Streak ~3,983.

**Standing facts:** the weeknight task `SwingWeeknightPipeline` runs itself (Mon–Fri 17:30 HST, Interactive-only V1; the runbook carries the wedged-lease/PUSH-INVISIBLE playbook). Both measurement chains are CLEAN and instrument-guarded (research: healed-to-4dp at Phase 19; trading-ledger: to-the-cent at Phase 20). RD's posture: STOP-ENGINEERING + MARKET TIME — H1 needs trading days; his monthly read #2 (first trading week of August) opens on corrected values. The engine artifact path is ephemeral-by-design (cite=commit, watch-standard v2.1, binding). Main is LOCAL-FIRST (~60+ commits ahead of origin — the operator pushes at his cadence; verify trailer-cleanliness + fast-forward before any push he requests).

**Phase-21 seed list (audit §7):** **D5 — the suite CROSSED the 5-minute watch line (5:14 @ 9115) at the Phase-20 close audit; the runtime paydown is the likely headline** · the 0032 taxonomy type (`fills_trades_price_divergence`, the #11 one-commit multi-mirror discipline) · two V2 candidates (execution↔fill IDENTITY linking; the strict-ALL stats choke point — RD's bound-b: a NEW stats surface still needs manual `voided_exclusion_sql` injection until it exists) · S4U/explicit-data-root (true logged-off unattended) · D15 base-VM consolidation · 2 residual brief-named top-level docs (`comms-stage1-…`, `phase19-close-housekeeping-…`) · D16/D17 decide-as-reached · RD-lane watches (the floor-ratio 0.15–0.2 band; the shadow-twin day-3-vs-day-4 divergence, n-of-a-few). Weigh against RD demand at scoping; the operator arbitrates (§2.2).

**Topology at handoff:** swing CHARC (you, fresh) + RD (gen live as of 07-15) + NO live orchestrator gen (d67f7279 closed out with the Phase-20 ritual; a fresh gen bootstraps from `scripts/orchestrator_bootstrap.md` → `orchestrator-context.md` → its close handoff `docs/orchestrator-handoff-2026-07-15-phase20-close.md` when the operator launches one). Dispatches go to the per-gen inbox with the EXPLICIT sid (`role_mail --to orchestrator:<sid>`); authority survives generational handoffs via director re-conveyance (proven twice). coa-chess is its OWN repo — do NOT drive/contaminate.

## Register quick-state (full table: charter §4)

- **CLOSED in Phases 19–20:** D3 D6 D10 D13 D14 D18 D19 D20 D21 **D22 D23 D24 D25** + F1/F6.
- **OPEN/WATCH:** D1 (runner size) · **D5 (FIRED — runtime)** · D8 · D9 · D12 · D15 · D16 · D17 · D11 (orchestrator-context ~109K, re-WATCH).
- **Follow-ups:** F2 Accept-header parser · F3 WSL-Codex CWD · F4 hook-file-absence · F5 `newest_live` staleness (mitigation: explicit `:<sid>` ALWAYS) · the 0032 taxonomy type · the two V2 candidates.

## Behavioral load-bearing (full text charter §5; harness model [`harness-architecture.md`](harness-architecture.md))

- **§5.1 director = PEER — disagree plainly + UNPREFACED at a LOW threshold; never manufacture objections; a SCOPE/FRAMING correction does NOT lower the bar.** Call out the operator's errors and yours. The prior gen owned FIVE (two dismiss-recommendations on the $10.94; two wrong residual attributions; the A5 cite-without-verify) — all net-caught; own yours the same way.
- **THE HEADLINE LESSON (both directors' lists): a monitor that fires gets a DECOMPOSITION before it gets an explanation.** Size-of-residual ≠ nature-of-residual; prior-plausibility ("it's the deposit drift") is how both directors nearly dismissed real corruption the instrument caught in 24h.
- **Verify on disk before asserting — TRACE THE FULL BRANCH + THE NEIGHBORING SYSTEM + THE KEY STRUCTURE** (the C4, pruner, and #33-chain lessons: reading code ≠ walking it; a mechanism claim must trace what interacts with it; a chain-repair ruling must know what the chain is keyed on).
- **A citation is only as good as the verified DEF** — never cite a symbol's location off a comment reference (the A5 miss); the §5.7/§5.11 grep-the-negative + verify-pre-existence + content-currency disciplines all bind.
- **FYI ≠ act** — action needs EXPLICIT direction; else acknowledge + assess + await.
- **Comms:** operator pre-authorizes the ACTION; the director couriers dispatches to the per-gen inbox (explicit `:<sid>`; commit the brief FIRST); `decision_request` operator-only; bodies BACKTICK-FREE (bash substitution mangles); `role_mail` from the MAIN repo dir; the mailbox is TRANSPORT not a tracker — must-persist content goes in a committed doc.
- **§2.7 directors do design dialogue + author/commit briefs + dispatch; NEVER run copowers cycles.**
- **§5.8 pathspec-commit `git commit -- <file>`** (+ `git add` first for NEW files) + `symbolic-ref==main` guard; final `-m` paragraph plain prose (trailer hazard); ZERO `Co-Authored-By` EVER (the ~3,983 streak).
- **QA on disk, never from the self-report; the operator live-witness is the binding net.** CHARC drives witnesses STEP-BY-STEP with recorded baselines + verified teardowns (the 19-B/19-C/20-A/20-BC pattern — witnesses found 3 runbook defects, discriminated a design ruling live, and validated every D25 gate).
- **The D21 sweep-safety discipline (BOTH charters): any moved-path OR tracked-config change gets a tests-grep BEFORE + a suite run AFTER; a close's green claim postdates the close's LAST commit; brief-coupled doc-assertions retire-at-close per the RD standard (retirement markers on new ones).**
- **The SCHEMA-STOP pattern works — keep using it:** name the schema temptation in the brief, forbid designing past it, route back on genuine need (it fired twice in Phase 20; both resolved no-schema).
- **Do NOT contaminate the generic scaffold with swing config**; coa-chess has its own directors.
- **Sub-agent 529 recovery:** inspect the worktree first; dispatch a NARROW recovery agent for only the missing gate.
