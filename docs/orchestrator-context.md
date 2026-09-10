# Orchestrator Context — Persistent Handoff File

**Audience:** Future orchestrator-role Claude sessions for the Swing Trading project. Also useful as a reference when the current orchestrator's context window is compacted.
**Purpose:** Provide enough context to bootstrap an orchestrator role without re-reading conversation history. Not a complete project spec — pointers to authoritative sources are throughout.
**Last updated:** 2026-09-10 (22-A4 merged + live-migrated to schema v38; worktrees torn down; the section-of-record rewritten and this file trimmed at its size trigger). **This line is a POINTER, not a ledger** — it regressed to a 5,298-char wall of superseded per-session history dated 2026-05-24 and was compacted here, the same pathology and the same fix as the CLAUDE.md line-3 restructure. Current state lives in §"Currently in-flight work" below; the displaced history is verbatim in [`docs/orchestrator-context-archive.md`](orchestrator-context-archive.md) §"Appended 2026-09-10".

---

## How to use this file

If you are a fresh orchestrator session: read this file end-to-end before engaging with the developer. Then check `git log --oneline -20` to see what's landed recently, then check `git status` to see what's untracked or modified.

If you are the same orchestrator post-compaction: skim the **Currently in-flight work** and **Recent decisions** sections to recover state, then continue.

This file is project-specific and lives in the repo. Update it (small commits) whenever you make a meaningful framing decision, capture a new operating process, or accumulate a lesson worth carrying forward. Avoid bloat — pointers to authoritative documents beat duplicated content. Older content migrates to `docs/orchestrator-context-archive.md` per §"Maintenance: retention discipline" below.

---

## Role and operating pattern

You are the **orchestrator instance** for the Swing Trading project. Your collaborator is the developer (Reid Smythe). The actual implementation work is done by **separate Claude Code implementer instances** that the developer dispatches with paste-ready prompts you provide.

**The pattern is:**

1. Developer raises a need (bug, strategic question, feature, study).
2. You and the developer discuss tradeoffs and decide on scope.
3. You draft a comprehensive **dispatch brief** as a Markdown file in `docs/`.
4. You produce a paste-ready **initial prompt** that points the implementer at the brief.
5. Developer dispatches a fresh Claude Code instance with that prompt.
6. Implementer executes the brief (TDD, adversarial review, etc.) and returns a structured **return report**.
7. Developer relays the return report to you.
8. You triage the return: validate decisions, flag follow-ups, capture lessons, propose next moves.
9. Loop.

**Key principle: the developer drives, you serve.** They set goals, methodology choices, gating decisions, scope boundaries. You provide recommendations, surface tradeoffs, draft artifacts, capture decisions in durable form. You do NOT decide on the developer's behalf when they haven't yet decided. When in doubt, present options with your recommendation and ask.

This principal-agent framing is captured in detail at `reference/Future Work/QuantEcon/2026-04-24-quant-econ-companion-ai-inference-benchmark.md` §"AI's role in this project — operator drives, agent serves."

---

## Governing strategy (binding)

Three documents govern. Read these before engaging on strategic questions.

1. **`reference/Future Work/2026-04-23-bifurcated-strategic-implementation-proposal-v2.1.md`** — the V2.1 governing strategy. Bifurcated architecture (Operational + Research-and-Verification), minimum-viable governance, bootstrap-first data, tranche sequencing.
2. **`reference/Future Work/2026-04-23-rebuttal-response-for-implementors.md`** — binding clarifications on V2.1. Anti-patterns list (strategy inflation, registry maximalism, infrastructure displacement, parity absolutism, bootstrap drift, priority flattening, document worship) is binding.
3. **`CLAUDE.md`** at repo root — current-state context, project conventions, gotchas. Auto-loaded by Claude Code on session start.

Forward-looking strategic content (deferred until V2.1 tranches mature):

- `reference/Future Work/QuantEcon/2026-04-24-quant-econ-future-research-program.md` — quant-econ integration program (Themes 1–4).
- `reference/Future Work/QuantEcon/2026-04-24-quant-econ-companion-trigger-purpose-three-branch.md` — Path A vs Path B framing + three-branch architecture refinement.
- `reference/Future Work/QuantEcon/2026-04-24-quant-econ-companion-ai-inference-benchmark.md` — AI-era crowding metric + operator-drives framing.
- `reference/Future Work/QuantEcon/external-references.md` — pointer file for external resources.

---

## Three-branch architecture (key refinement to V2.1)

V2.1 specifies two branches: Operational + Research-and-Verification. A 2026-04-24 refinement distinguishes two sub-branches within Research:

| Branch | Activity | Per-study horizon | Canonical example |
|---|---|---|---|
| **Operational** | Daily decision-making with promoted methods | Continuous | The `swing/` codebase |
| **Applied Research** | Testing rules developed elsewhere | Weeks–months per study | Earnings-proximity-exclusion (Sessions 2a/b/c) |
| **Basic Research** | Discovering/refining rules at first principles | Months–years per investigation | QuantEcon program (Themes 1–4) |

**Branches are permanent capability, not time-bounded projects.** Idle ≠ failure ≠ dismantle. Branch infrastructure (harness scaffolding, method-record format, cache directories, study templates) persists across idle periods. Time budget is allocated dynamically — 100% to whichever branch has an active study/investigation, idle when none.

Promotion path: Basic Research → Applied Research → Operational.

Full detail: `reference/Future Work/QuantEcon/2026-04-24-quant-econ-companion-trigger-purpose-three-branch.md`.

---

## Currently in-flight work

> **This section decays fastest. Update on every meaningful change.**

> **Archive companion (2026-05-18 Phase 12.5 #3 T-3.3 split — zero-yield):** This section inspected for pre-2026-05-13 entries during the Phase 12.5 #3 archive-split pass; ZERO entries qualified (all "Prior state" snapshots are dated 2026-05-17 or later). No content moved from this section; pointer retained for symmetry with the "Lessons captured" pointer below + audit-trail integrity. See [`docs/orchestrator-context-archive.md`](docs/orchestrator-context-archive.md) for archive companion structure.

### Currently in-flight: PHASE 22 ACTIVE — **22-A4 MERGED + LIVE-MIGRATED; NO ACTIVE ARC, NO CELL IN FLIGHT** (2026-09-10)

**Nothing is dispatched and no cell is running.** The next arc is the operator's to commission. Every fact in this section was re-derived from disk on 2026-09-10; re-derive rather than carry them forward.

**22-A4 (the per-attempt identity primitive) IS MERGED AND LIVE.** Merge `82d20042` (`--no-ff`, parents `0af3cf07` + `3b7140a7`); the plan/ledger merge is `0fac27ff`. **Schema v38** — migration `0038` was applied to the live DB and **operator-witnessed 2026-09-08 in ONE contiguous attended sitting** (W0 · W1 · W1.5 · W2 · W3 · W4 · W5, one step per operator result, nothing batched). 0038 is ADDITIVE: one `ADD COLUMN` (`trades.attempt_id`, the 58th and last), one partial `UNIQUE` index `ux_trades_attempt_id`, one `BEFORE UPDATE` trigger `trg_trades_attempt_id_immutable`, **no backfill** — `attempt_id` is NULL on all 28 trades and **the first post-migration ENTRY mints the first token.** Both pre-images (`~/swing-data/backups/swing-20260908T222007.db` and `~/swing-data/swing-pre-22a4-migration-20260909T082013Z.db`, 1,496,616,960 bytes each) were verified RESTORABLE — `integrity_check` ok, `schema_version` 37, `attempt_id` absent — not merely present; neither is deleted (the gate's copy sits in the swing-data root under D32).

**Both director gates cleared BEFORE the merge, and both post-migration reads agree.** CHARC 9 of 9; RD 7 of 7, his clearance attaching to the merge commit BY MEASUREMENT (46 branch + 20 main blobs, zero differing) rather than by tree hash — a naive "tree must equal `fd69bc22f661`" check false-alarms, because ledger commits legitimately move the tree hash while the code/test delta stays empty. At W3 **CHARC's pre-migration fingerprints reproduced EXACTLY** over the pre-existing 57 columns: the four named-pending rows `11ca855eb954` and all 28 trades `138ed687f35a`, both matching his W0 values — every value on every trade row byte-identical across the migration. The binding suite figure is the OPERATOR's `-n auto` on `4d9463fa`: **12,312 passed / 13 skipped / 0 failed**; the two `-n 4` cell runs (12,310) are cell-seat evidence and are NOT the gate.

**Live verification is done, twice.** Run **172** (attended, 2026-09-08 22:30) and run **173** (unattended, the 17:30 scheduled task, 2026-09-09) are both `state=complete` with **ZERO warning classes absent from the run-171 baseline** — compared as a per-class Counter equality, not by eye. `export_status=failed` on both is **D42**, pre-existing on every run since 160 (2026-08-21), and may NOT be read as a migration effect; that is what a named baseline is for. **One qualification, adopted into the record by CHARC and not to be dropped: the 171/172 pair is NOT a controlled A/B on the schema alone** — the bars are the same session but the finviz screen rolled (22:30 HST is 04:30 ET the next day), so the candidate pools differ (eval 157 total 79 vs eval 158 total 68; `aplus` 0 on both). RD separately established that the same-session re-run did NOT double-write the measurement chain (zero duplicate detection/observation keys; the drumbeat scorecard lines identical) — the question nobody had thought to ask.

**The worktrees and branches are GONE (2026-09-10).** `.worktrees/22-a4-exec` and `.worktrees/22-a4-plan` removed; branches `22-a4-exec` (`3b7140a7`) and `22-a4-plan` (`f5e03921`) deleted with `-d` (not `-D`), each proven fully contained in `main` first. The gitignored review evidence was reconciled **by sha256, not by filename**, against `~/swing-data/review-transcripts/22-a4-{exec,plan}/` — 34 evidence dotfiles, zero content mismatches, and **two real gaps found and closed**: `.codex-diff-r3.txt` and `.codex-diff.txt` (~380KB each, the diffs actually fed to Codex) existed ONLY in the worktree, and were copied in and hash-verified before anything was removed. Codex artifacts are DOTFILES; an `ls` without `-a` concludes they are missing.

**What this arc is remembered for: the merge made the next step in the recited ladder UNRUNNABLE, and five seats had recited it.** `connect()` refuses any schema ≠ `EXPECTED_SCHEMA_VERSION`; the merge moved that constant to 38 while the live DB held 37; `runner.py:768` opens every run through it. So *"a BLOCKING live pipeline run, THEN the witnessed migration"* could not execute after the merge. **CHARC's resolution required running nothing** — the baseline already existed as run **171**, executed by the real scheduled task on pre-merge code against the live v37 DB about three hours before the merge, with better provenance than any hand-run from a checkout. The rule now lives in CLAUDE.md as an **amendment to the pre-image bullet rather than a new one, because that bullet already stated the guard — it stated it about COMPARISONS**: *a step that OPENS THE LIVE DB is unrunnable between a schema-bumping merge and its migration, so the baseline is the last PRE-MERGE run and the live verification is POST-migration by construction.* The merge-time composition read checks FILE SETS; this was the RUNTIME composition of code with the live schema — a question that rung did not have on its list, and now does.

**Three gotchas banked at `626eba83`**, all bought by the witness: the live-DB rule above; **prove no process holds the DB by ACQUIRING THE EXCLUSIVE LOCK, never by enumerating processes** (a process list covers only the holders you thought of; and `-wal`/`-shm` absence is NOT a holder test — a read-only connection recreates the `-shm` and cannot delete either file, so the probe moves the mtime itself); and **`swing db-migrate` writes TWO backups, not one** (the CLI's unconditional one plus the version gate's, which echoes nothing — the console shows one path and the disk holds two).

**QUEUE, owners named** (CHARC's post-migration list, 2026-09-09). **Orchestrator's:** the `_is_head` version-mirror rename rider — *its trigger was AFTER this merge and has FIRED* — as its own commit, never landed alongside a version bump; plus this section's own upkeep. **CHARC's:** the **Gotchas cap triage — §Gotchas sits at 54,637 chars against a ~55,000 soft cap, 363 chars of headroom, so the NEXT gotcha commit carries a compression pass rather than a bare append** (the 22 bullets over ~700 chars are the budget; full forensic to `docs/CLAUDE.md-archive.md`); D32 (the swing-data root now holds ~4.2GB of pre-images — move-then-retain, never delete); the register rows; and a charter §4.2 amendment reconciling **two disagreeing cap sets** (`harness_probe.py` enforces total 100,000 / line-3 9,000 and reports OK, while this file's housekeeping trigger enforces Gotchas ~55,000 / line-3 2,000 / ~700-per-bullet and reads OVER — so whichever instrument you happen to run decides whether the file looks healthy). **Then:** `B-2` (single-field corrections silently discard every payload key after the first — a real pre-existing MAJOR standing unfixed at merge BY RULING, on CHARC's register), `ReservedJournalFieldError`'s bare-`Exception` base (D34's third instance, rediscovered independently by Reviewer B), D42's export failure, then D46, D45, D44/D47, the D39 sweep.

**Trading reality, unchanged by any of this: the admitting gate stays open — 131 post-barrier candidates, ZERO A+.** Open trades 23 CADL (partial_exited), 24 RHI, 25 OII, 26 NRIX, 28 PBF. Real money. The four named-pending rows (19 FTRE, 24 RHI, 25 OII, 28 PBF) carry into the October read byte-identical across the migration, per RD's own W3 read.

*(Rewritten 2026-09-10 on the operator's word. The section it replaces described 22-A as PAUSED mid-flight at `22-a-exec` @ `403ea9ff`, with the live DB "UNTOUCHED at v36 — migration `0037` is UNAPPLIED" — every load-bearing fact false, and by the time it was rewritten **the branch and worktree it named had been deleted an hour earlier**. That section already carried TWO prior generations' corrections saying a section-of-record is where a stale claim does the most damage, and it went stale again underneath both of them. The lesson is not "be careful": it is that this section decays BY DEFAULT, so its upkeep belongs in the close-of-sitting ritual and not to whoever next happens to notice.)*

#### (superseded) Earlier phase + arc records — MOVED to the archive companion 2026-09-10

The per-phase and per-arc "superseded" sub-sections that used to sit here — **22-A EXECUTING** (the mid-flight description retaining the 146-of-146 name-coverage falsification), **DEMAND C** (merged + live-applied 2026-08-13), **PHASE 21** (closed 2026-08-04), **PHASE 20** (2026-07-15), **PHASE 19** (2026-07-06), **PHASE 18** (2026-06-27), **PHASE 17** (2026-06-13), **PHASE 16** (2026-06-12), and the pre-Phase-14 snapshots — were moved VERBATIM to [`docs/orchestrator-context-archive.md`](orchestrator-context-archive.md) §"Appended 2026-09-10" at the size-trigger trim. Nothing was summarised away; grep the archive by phase number or arc name. The canonical per-phase records remain where they always were: `docs/phase<N>-scope-charc.md`, `docs/phase<N>-close-audit-charc.md`, and the per-phase `todo` files.

## Recent decisions and framings (don't re-litigate)

These have been settled with the developer's explicit approval. Don't reopen unless they ask.

- **Role scope-limitation + flag-vs-comply (CHARC harness-architecture rule, 2026-06-13).** The orchestrator's scope is intentionally narrow — tactical focus; extra context is creep. Within its swimlane it owes the operator INFORMED CONSENT, not silent obedience AND not re-litigation: flag a consequence ONLY when it is material, non-obvious, AND visible in the orchestrator's own lane (e.g. a waived test that gates merge safety; a skipped migration step that risks data) — then comply regardless; one flag, not a debate. It does NOT flag — and structurally cannot assess — CROSS-PHASE or architectural consequences; those are invisible to it by design and are the director's burden, caught via the §3-equivalent tripwires that route the broad view UP to CHARC. Corollary: a benign, obvious, or cross-scope-only waiver warrants no pushback (e.g. accepting a "these riders aren't this-phase work" waiver is correct). This is CHARC-owned harness architecture (a rule ABOUT orchestrator scope, whose justification lives outside the swimlane — an "unknown unknown" to the role); corrections route through CHARC, not self-authored here.
- **Bifurcated architecture per V2.1.** Settled.
- **Three-branch refinement** (Operational, Applied Research, Basic Research). Settled 2026-04-24.
- **V2.1 Addendum additions adopted in V2.1** (time-budget anchor, demotion pathway, source-of-truth correction protocol). Merged in place.
- **Adversarial review on every code-shipping session** (standing convention). Adopted after Tranche B-ops Session 2 demonstrated value (caught the `open_risk_position_count` bug). Implementer invokes `copowers:adversarial-critic` on the combined diff after task commits land; iterates to `NO_NEW_CRITICAL_MAJOR`; fixes findings in a new commit per no-amend rule.
- **Path A vs Path B framing for QuantEcon program.** Path A = practitioner extension; Path B = quant-rigor overlay. Path B gated on operational system producing above-market returns. Path B is QuantEcon program; not actionable until V2.1 tranches mature AND operational system is proven.
- **Operator-drives, agent-serves principle.** Operator defines problem framing; agent provides knowledge-retrieval + execution. The recursive crowding concern about AI-aided development is narrowed by this discipline.
- **Pre-registration discipline for research studies** (Session 2c). Decision tiers + thresholds committed before viewing data.
- **Survivorship-bias interpretation protocol** (study-level amendment). Absolute metrics treated as lower bound; relative metrics as direction-trustworthy-magnitude-uncertain; weak/null signals → defer not reject.
- **Filter-rule activation-rate sanity check** (forward-looking lesson from Session 2c). Future filter-rule studies pre-register a sanity check that the most aggressive variant must filter ≥10% of signals.
- **(2026-04-25) Production-gating-aware instrumentation as standing pattern.** When instrumenting production logic for diagnostic measurement, mimic production's gating order, not criteria emission order. Caught as R1 Critical in candidate-sparsity diagnostic; would have made primary hypothesis appear 3.5× weaker than reality if uncorrected.
- **(2026-04-25) Bug 7 family confirmed closed in web layer.** Survey query (`grep -rn 'ORDER BY run_ts DESC LIMIT 1' swing/web/`) on the post-`77877c1` tree confirms every primary read path that joins candidates by ticker now binds via `pipeline_runs.evaluation_run_id` (FK-direct or heuristic). Class durably closed in this layer.
- **(2026-04-25) Framework framing.** The framework is what we are building, informed by Minervini and Disciplined Swing Trader as known-good priors. Research branches exist to test, refine, and — where evidence justifies — depart from those references. Doctrinal fidelity is not the constraint; evidence quality is. Implication: research-branch findings can propose framework changes (criteria modification, allowed-miss extension, bucket logic, universe choice); the V2.1 source-of-truth correction protocol governs the formal change process, but the framework is not bound by the references absent that process.
- **(2026-04-25) Evidence gap framing.** Current operational rate (~2 trades/year confirmed by operator; harness-derived ~2.5 A+/year on SPX+NDX 1×) is too low to produce trade-outcome data sufficient for framework evaluation. Research-derived rate-uplift candidates (universe broadening, allowed-miss extension, criteria refinement) are tools to escape the rate-vs-evidence recursive bottleneck. As of 2026-04-25, operational branch has produced n=1 trade outcome (VIR); the loop has begun to break but evidence accumulation will take time.
- **(2026-04-25) Sub-A+ trading is in operator's actual practice.** VIR trade (2026-04-20) was framework-recommended in `watch` bucket — passed all 8 trend-template criteria, failed two VCP-layer criteria (`proximity_20ma` extended above 20MA; `tightness` zero-day-streak base not formed). Operator took it anyway as a "trade test" per entry notes. Practice precedes principle: the "willing to relax absolute A+ doctrine" framing post-dates the actual deviation. Future workflow discussion should treat sub-A+ trade-taking as a practice-supported reality, not a hypothetical. Specific category for this trade (now backfilled in `hypothesis_label`): "sub-A+ VCP-not-formed test (proximity_20ma + tightness fails); inaugural trade test."
- **(2026-04-25) Operational branch as evidence-generation surface.** Operator is willing to take hypothesis-tagged sub-optimal trades within risk discipline, treating losses as cost-of-development rather than investment loss. Each trade requires a frozen pre-trade hypothesis label (free-text initially via the `hypothesis_label` column shipped 2026-04-25). Pre-registration discipline applies — label is set at entry and frozen; outcome-driven re-labeling is anti-pattern. This shifts operational posture from "execute proven framework" to "execute candidate framework variations to generate evidence" — V2.1 promotion path running in reverse to escape the rate-vs-evidence bottleneck.
- **(2026-04-25) A+ identifications ≠ trades (statistical analysis discipline).** A+ is a production classification (bucket assignment); trade is an operator decision to enter a position. They should be analyzed as separate measurements; do not conflate. Operator's intent is to trade every A+ but that's not a hard rule, AND going forward trades will outpace A+ identifications because of hypothesis-tagged sub-A+ trade evidence collection. Statistical aggregations (rate, expectancy, etc.) should preserve the distinction.
- **(2026-04-25) Binding constraint is capital tie-up, not identification rate.** Capital ceiling at $7,500 × ~14% per position × ~5 concurrent × ~10 cycles/year ≈ 50 trades/year. With identification volume ~40-100 A+/year + ~470/year near-A+ defensible candidates from Finviz study, candidate volume already exceeds throughput capacity. Time, pipeline cadence, manual chart-review, and trade-execution friction are all non-binding at current scale. Implication: rate-uplift levers (universe broadening, allowed-miss extension) matter less than I previously framed; operational use of existing infrastructure matters more.
- **(2026-04-25) Chart-pattern algorithm is for encoding, not throughput.** Operator's manual chart assessment is fast enough to saturate capital today. The algorithm's value is structuring the qualitative chart-pattern dimension of trade decisions into the feedback-loop's analyzable data. Without it, hypothesis-label free-text absorbs chart-pattern info qualitatively (interim solution). When chart-pattern algorithm exists, it becomes a structured field; hypothesis-label holds remaining qualitative dimensions. Chart-pattern algorithm is important but NOT urgent; multi-session copowers cycle when ready. Phase 3e §3e.6 captures the original scope.
- **(2026-04-25) Next-horizon priority: operational use of newly-built infrastructure, not additional development.** Hypothesis-label infrastructure ships; Finviz-pool study identifies near-A+ defensible candidates (SLDB, UCTT). The actually-urgent next move is operational — take hypothesis-tagged trades, accumulate evidence, let the feedback loop run. Watch-staging UI is a small operational change with immediate value. S&P 1500 adoption decision is operator-pending. Chart-pattern algorithm and other development work are not urgent.
- **(2026-04-25) 10% return target math.** With $7,500 capital, ~50 trade/year ceiling at full deployment, and Minervini-typical expectancy (~0.5-0.8% account return per trade), the math gives 20-40% annual return ceiling. The 10% target is well within range, not the ambitious target it was earlier framed as. Compounding + capital injection to ~$100K extends absolute returns linearly to $20K-$40K/year at the same percentage ceiling.
- **(2026-04-25) Hypothesis investigation plan v0.1 longer-horizon framing: implicit, revisit at first closure gate.** Operator and orchestrator agreed that beyond the 4 starting hypotheses (A+ baseline 20-sample target; near-A+ defensible extension 10-sample; sub-A+ VCP-not-formed 5-sample; capital-blocked smaller-position 5-10-sample), there is no longer-horizon plan, and that's the correct posture for now. Reasoning: data from the 4 starting hypotheses will inform what to test next; trade pace is unknown (3-18 months to fill all 4 targets); committing further hypotheses now risks document-worship anti-pattern OR vague aspiration. **Action: when the first hypothesis closes (whichever hits its target sample size or escapes via tripwire first; likely Sub-A+ VCP-not-formed at 5 samples or A+ baseline at 20), explicitly revisit the longer-horizon planning question with operator.** Decision-cadence framing (Phase A: collect; Phase B: review-and-iterate at first closure; Phase C: longer-horizon strategic review at multi-hypothesis closure) is captured here for that future moment but not yet committed as a roadmap document.
- **(2026-04-25) Hypothesis investigation plan v0.1 OPERATIONAL.** Migration 0008 seeded 4 hypotheses (A+ baseline 20-target; Near-A+ defensible: extension test 10-target; Sub-A+ VCP-not-formed 5-target; Capital-blocked: smaller-position test 10-target). Tripwire values per-hypothesis: consecutive-max-loss N (3 for n=5; 4 for n=6-10; 5 for n=11-20) AND absolute-loss 5% of starting equity. Per-hypothesis status mutation only via `swing hypothesis update --status --reason "..."`; tripwire/sample-size/decision-criteria are immutable post-data (require formal new migration). VIR is sample 1 of 5 in Sub-A+ VCP-not-formed. Dashboard surface and CLI pre-fill operational; operator can take hypothesis-tagged trades from Monday onward.
- **(2026-04-25) Prefix-label convention (operator-facing).** Hypothesis-label matching against the registry uses **case-insensitive PREFIX** match (not substring; chosen by hyp1 R1 to prevent double-counting). **When operator manually composes a `--hypothesis` value** (e.g., for off-pipeline trades or override of pre-fill), the label MUST start with the canonical hypothesis name (e.g., `"Sub-A+ VCP-not-formed test ..."`, NOT `"my custom test for sub-A+"`) for tripwire/progress aggregation to correctly attribute it. The CLI pre-fill emits matcher's `suggested_label_descriptive` which already follows this convention; manual labels are operator-responsibility.
- **(2026-04-25) Hypothesis-recommendation engine framing: dashboard PROPOSES, operator DISPOSES.** The dashboard's Hypothesis-driven recommendations panel is an active recommendation surface — not just a listing. It tells the operator "if you take this trade, it advances hypothesis X (currently N/M samples)." Operator validates the recommendation (chart pattern, risk, sector preference) and either takes the trade or declines. Tripwire-fired hypotheses surface visually (red row); operator evaluates whether to pause/escape via `swing hypothesis update --status paused --reason "..."`. Pre-registration discipline applies — hypothesis plan and tripwires are frozen at migration 0008; only `status` is mutable via CLI.
- **(2026-04-25) Entry discipline for hypothesis trades: wait for pivot (stop-buy at pivot).** All hypothesis-tagged trades enter at-pivot via stop-buy order (or stop-limit for higher-volatility names where slippage control matters). Do NOT chase more than ~1% above pivot; if price gaps significantly above pivot at open, skip that day. Rationale: (a) pivot is the framework's prescribed entry trigger; (b) entry-execution is a confound on per-hypothesis expectancy aggregation — pre-committing to at-pivot eliminates that confound from the per-hypothesis statistics. Applies to ALL four hypotheses uniformly, including Sub-A+ VCP-not-formed (where the "pivot" is somewhat placeholder since base isn't formed; entry-at-pivot is still the cleanest discipline). The framework's initial_stop discipline caps the downside if pivot turns out to be the day's high → pullback. Operator workflow: review hyp-tagged dashboard listings → manual analysis (chart pattern, sector, risk) → if proceeding, stop-buy at recommended pivot → accept that pivot-as-day's-high is a known failure mode budgeted by the initial_stop.
- **(2026-04-26) `/prices/refresh` anchor consistency closed Bug-7 family in this layer.** The route's cache-prewarm path was using `MAX(run_ts) FROM evaluation_runs` (the pre-Tranche-C mixed-anchor pattern) while `build_dashboard` and `build_watchlist` use pipeline-eval-first via `latest_evaluation_run_id`. Session 2 R1 caught the divergence as part of sort-anchor consistency review; the route now consumes the same pipeline-eval-first anchor. Survey query (`grep -rn 'MAX(run_ts) FROM evaluation_runs' swing/web/`) confirms no remaining occurrences in the web layer. Class durably closed.
- **(2026-04-26) Chart-pattern shape estimator V1 scope locked (six decisions).** Brainstorm output at `docs/superpowers/specs/2026-04-26-chart-pattern-flag-v1-design.md` (commit `081f689`). Locked: (1) **One pattern only — `flag_pattern`**; other patterns (pennant, base, cup-handle, tight channel) are V2+ additions. (2) **Governance: display + persist on trades + confidence metric; production scoring/bucketing UNTOUCHED.** Promoting any aspect to production decision logic requires V2.1 §VII.F. (3) **Compute timing: pipeline-time on chart-scope tickers** (extends `_step_charts`, shares in-hand OHLCV — zero scope expansion). (4) **Display surface: watchlist rows + trade-entry form + chart overlay.** (5) **Trade-entry consumption: cached-only.** Out-of-chart-scope manual trades have no override surface in V1. (6) **Operator override: algo and operator values stored separately** on trade row (4 columns: chart_pattern_algo, chart_pattern_algo_confidence, chart_pattern_operator, chart_pattern_classification_pipeline_run_id audit anchor). Effective-pattern-for-analysis = COALESCE(operator, algo). Algorithm approach: rule-based geometric (deterministic; 11 gates; min-of-clearances confidence). Watchlist tag rendering: parallel `pattern_tags` VM field — `_sort_watchlist` byte-for-byte UNCHANGED (sort-neutrality structurally guaranteed). Spec passed 5 adversarial Codex rounds (22+ findings dispositioned).
- **(2026-04-25) Vocabulary for confirmed hypotheses: "promoted" (per V2.1 promotion-path).** A hypothesis whose investigation closes positively (target sample met AND decision criteria evaluated positive AND operator decides to retain as ongoing recommendation surface) is **promoted**, not "lemma" / "validated" / "confirmed" / other generic terms. Reuses V2.1 three-branch promotion-path language (Basic Research → Applied Research → Operational; here: under-investigation → promoted-to-operational). Behavioral implications of `promoted` status: (a) continues to appear on dashboard recommendation surface but with different visual treatment (no "N/M progress" since target was met; instead lifetime stats like "promoted; lifetime: N trades, mean R X.XX"); (b) tripwire stays armed — if performance degrades post-promotion, the tripwire surfaces it for operator re-evaluation; (c) per-trade attribution continues so we can monitor for degradation. **Implementation deferred until first closure approaches:** a future small migration `0009_hypothesis_status_promoted.sql` will add `'promoted'` to the `hypothesis_registry.status` CHECK constraint enum (currently `active`/`paused`/`closed-escaped`/`closed-target-met`). Pre-registration discipline preserved — status enum widening is a formal migration, not a CLI-mutable operation.

**ARCHIVED 2026-09-10 (size-trigger trim, CHARC-ruled).** Twenty-one settled entries were moved VERBATIM to [`docs/orchestrator-context-archive.md`](orchestrator-context-archive.md) §"Appended 2026-09-10". The test CHARC ruled: an entry archives only if **(1)** a NAMED LIVE DOCUMENT now owns the rule (so the entry is a decision *record*, not the operative statement) or **(2)** it records a COMPLETED ACTION. A closed *finding* is knowledge, not an action — it archives only when the pointer names the artifact that owns it, and **an unowned finding STAYS, because the archive would then be its only home.** Nothing here was summarised away; each row names where the content now lives.

| Tier | Date | Entry | Owned by |
|---|---|---|---|
__ROWS__

**DELIBERATELY KEPT, having FAILED the owner test** (their content has no live home, so archiving them would lose it): *10'| A | 2026-04-27 | (2026-04-27) Subject-only grep regex amended to ERE + POSIX digit class | §"Binding conventions" of this file (the ERE + POSIX form is stated there operatively) |\n| A | 2026-04-27 | (2026-04-27) Orchestrator-vs-implementer brainstorm-pattern decision. | **SUPERSEDED BY REPLACEMENT** — the orchestrator-spawned sub-agent dispatch model (2026-06), [`docs/implementer-dispatch-recipe.md`](implementer-dispatch-recipe.md) §0 + §"Operating processes" → "Dispatch execution". The archived entry prescribes dispatching a fresh implementer instance for substantive brainstorms and is WRONG as written; follow the recipe, not it. |\n| A | 2026-04-26 | (2026-04-26) Phase 4 scope-deviation acceptances (R1 Major 2). | completed action; Phase 4 closed |\n| A | 2026-04-27 | (2026-04-27) Manual verification round 1 complete; Tier-1 mathtext fix dispatch queued. | completed action; the fix shipped at `2fd0ecc` |\n| A | 2026-04-26 | (2026-04-26) Phase 3 dispatch discipline: disjoint-task-partitioning, no worktree isolation initially. | §"Binding conventions" (worktree isolation is now mandatory, not a fallback) |\n| A | 2026-04-27 | (2026-04-27) Phase 7 FP/FN aggregator: deferred to operator-manual classification | completed action; Phase 7 closed |\n| A | 2026-04-26 | (2026-04-26) Phase 4+ dispatch discipline: continue partitioning + ADD observable verification. | §"Binding conventions" + the recipe |\n| A | 2026-04-26 | (2026-04-26) Phase 6 mathtext fix landed as standalone tiny commit (`2fd0ecc`). | completed action (`2fd0ecc`); the durable rule is CLAUDE.md §Gotchas "Matplotlib mathtext" |\n| A | 2026-04-26 | (2026-04-26) Internal-Codex `(internal)` qualifier convention | §"Binding conventions" |\n| A | 2026-04-26 | (2026-04-26) Base-layout 5-VM rule scope. | CLAUDE.md §Gotchas "`base.html.j2` is shared" |\n| A | 2026-04-26 | (2026-04-26) Observable-verification subject-only grep refinement. | §"Binding conventions" |\n| A | 2026-04-26 | (2026-04-26) Review-fix commit message convention formalized. | §"Binding conventions" |\n| B | 2026-04-25 | (2026-04-25) Capital-sensitivity finding interpretive disposition: informational, not workflow-changing. | [`research/studies/candidate-sparsity-diagnostic.md`](../research/studies/candidate-sparsity-diagnostic.md) — carries the 1x vs 5x `risk_feasibility` comparison the entry summarises |\n| B | (undated) | Russell 3000 as primary broader-universe variant | [`research/studies/candidate-sparsity-diagnostic.md`](../research/studies/candidate-sparsity-diagnostic.md) |\n| B | 2026-04-25 | (2026-04-25) S&P 1500 universe expansion: Tier 2 — Mixed. | [`research/studies/sp1500-universe-expansion.md`](../research/studies/sp1500-universe-expansion.md) — defines the Tier-2 band verbatim |\n| B | 2026-04-25 | (2026-04-25) Hypothesis 5 closed. | [`research/studies/harness-vs-production-parity.md`](../research/studies/harness-vs-production-parity.md) |\n| B | 2026-04-25 | (2026-04-25) Path 1 selected for residual-gap question. | [`research/studies/harness-vs-production-parity.md`](../research/studies/harness-vs-production-parity.md) |\n| B | 2026-04-25 | (2026-04-25) Identification rate recalibration. | [`research/studies/2026-05-26-v2-selection-mechanic-analysis.md`](../research/studies/2026-05-26-v2-selection-mechanic-analysis.md) |\n| B | (undated) | Tranche 2 of V2.1 §X satisfied formally by Session 2c\'s defer outcome. | [`research/studies/earnings-proximity-exclusion-results.md`](../research/studies/earnings-proximity-exclusion-results.md) + its method record |\n| B | 2026-04-26 | (2026-04-26) Watchlist sort uses four-key composite ordering. | the LIVE CODE — `swing/web/routes/pipeline.py:_sort_watchlist` and `swing/pipeline/runner.py:_tag_aware_sort_key`, whose comments state the key |\n| B | 2026-04-25 | (2026-04-25) Next-move post-Tranche-C: parallel operational + applied-research parity check. | completed ACTION — the parity check it queued was run and closed; [`research/studies/harness-vs-production-parity.md`](../research/studies/harness-vs-production-parity.md) |'eturn target math* (2026-04-25) · *Bug 7 family confirmed closed in web layer* (2026-04-25) · *`/prices/refresh` anchor consistency closed Bug-7 family in this layer* (2026-04-26). **Also kept, for a different reason —** *Filter-rule activation-rate sanity check* binds FUTURE studies, so it is not closed at all and fails archivability on forward force rather than ownership.

## Operating processes

### Brief drafting

Briefs live in `docs/` with naming pattern `{tranche-name}-{session-name}-brief.md`. Examples: `tranche-a-brief.md`, `tranche-b-ops-session-2-brief.md`, `tranche-c-pipeline-linkage-brief.md`.

A brief MUST include:

- Audience statement ("Fresh Claude Code instance with no prior conversation context").
- Mission paragraph.
- Expected duration estimate.
- §0 "Read first" — list of files the implementer must read, with rationale.
- §0 "Skill posture" — which superpowers/copowers skills to invoke or NOT invoke.
- Strategic context section (compressed; what they need that isn't in linked references).
- Scope section with explicit "out of scope" sub-list.
- Binding conventions (commit style, no-amend, TDD, test discipline, etc.).
- Per-task specifications with acceptance criteria.
- Adversarial review section (target + watch items).
- Done criteria.
- Return report format.
- "If you get stuck" section.

Briefs typically run 200–500 lines. Tight is better than padded. Self-contained — the implementer should be able to execute end-to-end from the brief + linked references without your conversation context.

### Paste-ready initial prompt

Always provide alongside the brief. Format:

```
You are dispatched as the {session-name} implementer for the Swing Trading project in this repo.

Step 1 — Read `docs/{brief-filename}.md` in full. {one sentence on what's in it}.

Step 2 — Read the references §0 of the brief points at, particularly {key references}.

Step 3 — Execute the brief directly. {Skill posture summary; key disciplines; key out-of-scope reminders.}

Step 4 — Produce the return report per §{N} of the brief as your final message.
```

#### Model + effort recommendation (added 2026-06-13, operator-directed)

Every implementer dispatch MUST be accompanied — in the chat alongside the paste-ready prompt — by an explicit **model** (haiku / sonnet / opus / fable) + **effort-level** (low / med / high / xhigh / max) recommendation for the tasking, with a one-line rationale. This is operator-facing *launch configuration* (the operator sets the knob when spinning up the implementer instance), NOT part of the implementer's in-prompt instructions.

**Ownership (closes a seam, CHARC-flagged 2026-06-13):** the ORCHESTRATOR supplies this recommendation for EVERY dispatch — including arcs commissioned or briefed by CHARC or RD. The brief's author does not supply it; do not assume a director will. The orchestrator owns the launch-config rec because it owns the dispatch.

- **The orchestrator role STARTS at Opus 5 / `high`** (operator-ruled 2026-08-03, recalibrated for the Fable 5 / Opus 5 / Sonnet 5 generation; the Opus-4.x-era `xhigh` default is **RETIRED** — generation uplift covers it). **TWO named `xhigh` escalations: (1) the merge-integration / composition step** — the ONLY place the cross-arc composition class is caught (`harness-architecture.md` §5.1) — **and (2) phase-close QA.** Directors START at **Fable 5.1 / high** (operator-ruled 2026-09-02; the START configuration for all three roles is now declared at the top of each `scripts/*_bootstrap.md`). Full allocation + grounding: [`docs/implementer-dispatch-recipe.md`](implementer-dispatch-recipe.md) §2A and the brief [`docs/harness-model-effort-recalibration-brief.md`](harness-model-effort-recalibration-brief.md).
- **Opus-5 prompt hygiene (2026-08-03).** Do NOT write legacy self-verification prods into dispatch prompts ("double-check your answer", "add a final verification step", "use a subagent to verify your own work") — Opus 5 self-verifies unprompted and these cause over-verification at real token cost. Delegate to sub-agents for genuinely independent, sizeable tracks, never to check your own work. **The discriminating rule: an instruction is removable only if it compensates for a MODEL limitation; never if it encodes a PROJECT fact or a CROSS-AGENT evidence gate.** The merged-head suite, the per-round Codex banner assertion, the trailer audit, and QA-on-disk are evidence gates BETWEEN agents — they all stay. (A broader prescriptiveness audit is deferred to the Phase-21 close, one artifact at a time.)
- **For implementers, recommend deliberately** — a blanket "Opus xhigh" adds no value; differentiate by reasoning-density, scope, and downstream leverage:
  - **PHASE DEFAULTS (operator-ruled 2026-09-07, a measured spend experiment — supersedes the 2026-09-01 Opus-everywhere default): WRITING-PLANS → `implementer-opus-high`; EXECUTING/CODING → `implementer-sonnet-high`.** A named reason moves the notch: `xhigh` for a particularly difficult plan (state why in one line — 22-A4's "a read that LOOKS conclusive" is the model); Opus for executing when the code is measurement-chain, a migration, carries an open design fork, or is must-converge-Codex work on a critical instrument. **Report the summed `tokens used` per arc in the merge request** (recipe §4) so the experiment is measured, and treat rework (rounds-to-convergence vs the Opus-era baselines) as its cost side. Recommend the default unless a named reason moves the notch. The Opus-5 generation covers at `high` what earlier generations needed `xhigh` for; a reflexive `xhigh` buys real token cost for little differentiation, which is the same reasoning that retired the orchestrator's own `xhigh` default on 2026-08-03.
  - **`xhigh` is now the EXCEPTION and carries a stated justification** — reserve it for high reasoning-density / high-leverage / must-converge-Codex work touching a critical instrument (design + writing-plans phases, measurement-chain code, anything an RD/CHARC gate blocks), and say in one line WHY the notch moved. "It's important" is not a reason; "a wrong answer here is confident and hard to detect" is.
  - Locked-plan disciplined TDD execution → **Sonnet high** (the 2026-09-07 default; the Codex-convergence + multi-eyes gates are the quality bar and are unchanged). Escalate to Opus high with a stated reason, never silently.
  - Genuinely mechanical / low-judgment / large-but-simple volume → consider **sonnet** or a lower effort notch.

Memory: `feedback_dispatch_model_effort_recommendation`.

#### Dispatch execution — orchestrator-spawned implementer sub-agents (ADOPTED 2026-06-14)

**WRITING-PLANS DISPATCH CHECKLIST — the orchestrator's half of the PLAN-STAGE PROTOCOL (CHARC, `dc1b0ed3`, 2026-09-07; binds from 22-A4's executing dispatch onward).** The protocol's five rules live in the recipe §3; these three are the ones *I* execute and cannot delegate:

1. **RUN `python scripts/cell_depth.py --live <h>` BEFORE EVERY DISPATCH AND AT EVERY ROUND GATE.** It is a precondition, not a caveat. **A cell cannot see its own depth** — no hook fires for a subagent — so a cell's self-estimate is not a record and the ledger's depth column is mine to fill. Past the 400K cap the loop re-dispatches to a FRESH cell off the committed plan plus the per-round preserved evidence; that is a normal outcome, not a failure. *(First real use, 2026-09-07: the 22-A4 planner measured 779,749 — nearly 2× the cap — and the gauge flagged it OVER before I dispatched. Every round in that cell had been paid at ~1.9× a round at 400K, and neither the cell nor I could see it.)*
2. **ROUND 0 IS A PREMISE + FORK CENSUS WITH NO CODEX, AND THE RULING PACKET GOES OUT AS ONE PACKET.** No review round opens while a ruling is outstanding; a fork discovered mid-loop STOPS the loop and re-enters round 0. *(Why: 22-A4 settled design INSIDE the review loop at one ruling per round. Rounds 8, 9 and 10 each spent most of their yield on the PREVIOUS ruling's residue — round 10 returned 6 of 7 findings residual, 4 of them residuals of the amendment written to satisfy the prior ruling. The loop was reviewing its own wake. RD confirmed the diagnosis and banked the directors' half: rule a packet in ONE pass, because a ruling that arrives as a stream is a stream of rounds.)*
3. **VERIFY THE BASE SHA: a worktree carries the rules that existed when it was CUT, and a brief saying "follow the recipe" is only as good as the recipe in THAT tree** (CHARC, `harness-architecture.md` §5.1, 2026-09-07). Before dispatching, branch the worktree off `main` at or above the commit carrying the rules the brief depends on; NAME those rules in the brief; VERIFY each one in the branch's own copy of `implementer-dispatch-recipe.md` and `harness-architecture.md`; and RECORD the base SHA you checked. *(Live instance: `.worktrees/22-a4-plan` is based on `edfea928`, which sits BELOW every rule of 2026-09-07 — the plan-stage protocol, dispatcher-read depth, per-round evidence preservation, the ruling-intake check, ONE RULER PER ITEM and wake-on-mail. A dispatch into that tree would have cited six rules none of which were in it, and the cell would have read the older text and been right to.)*
4. **ONE RULER PER ITEM** (`harness-architecture.md` §3, 2026-09-07): every packet names exactly ONE ruling seat per item — `PRIMARY: <role>` for the whole, or a per-item ruler when a packet spans lanes. **A packet that names two seats for one open question is MIS-ADDRESSED.** An item needing both is SERIALIZED by me ("CHARC rules, then RD reviews"). As a CC seat I hold, and speak only to dissent from a LANDED ruling, upward. **Re-list the inbox immediately before every post** — and with wake-on-mail armed, the operator no longer types "inbox updated," so a stale listing is now the default failure rather than an unlucky one.

5. **A FOURTH COUNTED ROUND NEEDS MY WRITTEN AUTHORIZATION NAMING THE TASK-BEARING FINDING**, written after reading the cell's depth. Three counted rounds → self-sweep → execute is the default. When residuals of the loop's own fixes dominate, the remedy is a DEDICATED UNCOUNTED SELF-SWEEP followed by ONE confirming round on the settled artifact — recorded under `SS-N` ids, no round number, no effect on convergence. **Residuals findable by searching our own diff must be found by search, not bought at ~400K tokens a round.**

**The dispatch is executed by the orchestrator spawning an implementer sub-agent via the Agent tool** (the `.claude/agents/implementer-<model>-<effort>` library cells) on the operator's dispatch "go" — replacing the operator hand-pasting a prompt into a fresh CC window + relaying the return. Proven on the 18-B writing-plans pilot + the library smoke-spawn; CHARC-passed; operator-approved. **Authoritative sources (do NOT duplicate here):** the protocol SPOF [`docs/implementer-dispatch-recipe.md`](implementer-dispatch-recipe.md); the cells `.claude/agents/implementer-*.md`; the design + conditions [`docs/orchestrator-subagent-dispatch-automation-proposal.md`](orchestrator-subagent-dispatch-automation-proposal.md) + [`docs/orchestrator-subagent-dispatch-charc-architecture-pass.md`](orchestrator-subagent-dispatch-charc-architecture-pass.md).

**Flow:** operator commissions + "go" → orchestrator selects the cell + spawns it `run_in_background` (NO `model` override — the cell carries model+effort) → the sub-agent works in `.worktrees/<name>`, hand-runs Codex to convergence, returns its report to the orchestrator (the Agent result) → orchestrator QA-against-disk (incl. verifying convergence from the REAL `.copowers-findings.md`, never the sub-agent's claim) → posts the QA'd return report to the directors → the merge gate (three-eye where applicable) → operator authorizes → orchestrator integrates onto main and re-runs the suite on the merged head. **Merge form:** rebase + `merge --ff-only` ONLY while nothing cites the branch's SHAs; **once a committed ledger, brief or block-quoted ruling cites them, use `git merge --no-ff` and never rebase or squash** — a rebase falsifies every citation while leaving it reading true. A history rewrite is a TIP-ONLY operation; past the tip, a message defect is recorded, not rewritten (CHARC, 2026-09-09, 22-A4; full clause in the recipe §1).

**Conditions (C-a..C-e, CHARC):** **C-a** staged — cleared for non-Codex + writing-plans + executing (executing cleared once the writing-plans pilot proved hand-run-Codex convergence). **C-b** the cell uses `.worktrees/<name>` — NEVER the Agent tool's `isolation: worktree`. **C-c** hand-run Codex is acceptable (the copowers Skill is absent in a sub-agent); the orchestrator verifies convergence from the persisted REAL transcript. **C-d (orchestrator owns failure handling):** Agent-returns-`null` → re-dispatch once then escalate; WSL-Codex unreachable → orchestrator takes over the review; stall/no-return → check the task output, recover or escalate (`run_in_background` notifies on completion, not on a hang). **C-e (model/effort knob = the CELL choice):** the Agent tool has NO per-call effort param — a sub-agent's effort comes from the cell's `effort:` frontmatter (else inherits the session at spawn; no post-spawn propagation; not runtime-observable). So the orchestrator's model/effort decision IS the cell selection — **announced in chat + vetoable before spawn** (the handshake is required). This supersedes the earlier "set the knob on the Agent call" phrasing.

**Cell selection (rubric):** select by TASK (reasoning-density / scope / leverage / risk), NOT by phase. Floor `sonnet-med`, ceiling `opus-max`; **no `low`/`haiku` implementer cells** (even mechanical implementer work carries the TDD+Codex+return load; this codebase's gotcha density makes a too-weak implementer net-negative — rework > savings; trivial-enough-for-`low` work is done inline, not dispatched). `opus-max` = break-glass irreversible / measurement-chain.

**Live-pickup:** a NEW cell registers at a turn-boundary registry rescan (NOT the same turn it's written; a full restart is not strictly required but guarantees a reload). **Verifying a new cell:** config-correctness (frontmatter, tracked) + a smoke-spawn (loads + reads the recipe + acts + returns) — NOT an effort readout (impossible; effort is not runtime-observable).

### Triage of return reports

When a return report comes back, triage in this order:

1. **Verify the work matches the brief.** Commits landed? Tests green? Adversarial review verdict?
2. **Validate the substantive decisions.** Did the implementer make sensible calls on judgment-call items?
3. **Triage adversarial-review findings.** Each ACCEPTED-with-rationale finding deserves a sentence of acknowledgment; each FIXED finding deserves verification that the fix is correct.
4. **Flag follow-ups.** Items the implementer flagged for future work go to `docs/phase3e-todo.md` or appropriate backlog at the next housekeeping opportunity.
5. **Capture lessons.** Process insights go into this file or into memory.
6. **Propose next moves.** Don't decide unilaterally; offer options with recommendation.

#### Posting to the directors via the comms mailbox (added 2026-06-11, comms Stage 1)

After you relay a return report to the operator in chat (UNCHANGED — that is the operator's control point and it stays), ALSO post the same report to both directors via the file mailbox so they track arc state without the operator hand-relaying it:

```
cd "c:/Users/rwsmy/swing-trading" && python scripts/role_mail.py post --from orchestrator --to charc,rd \
  --type return_report --subject "<arc>: <one line>" --body-file <return-report.md>
```

**Three posting rules, each bought with a real misdelivery or a lost message (banked 2026-08-09, CHARC-folded):**

1. **`--body-file` ALWAYS; never an inline `--body`.** A body containing a dollar amount broke PowerShell's argument parsing and the post FAILED rather than sending (the good outcome — but only by luck of where the shell split). `--body-file` sidesteps shell quoting entirely, and it leaves a file on disk to diff the delivered message against.
2. **The `cd` to the MAIN repo goes in the SAME invocation, every time, and echo the cwd.** `role_mail.py` resolves its comms root from the SCRIPT's repo, so a worktree cwd silently misdelivers into the worktree's gitignored `comms/` tree while printing a success line. **PowerShell's cwd persists independently of Bash's** — a `Set-Location <worktree>` issued for a suite run will still be in effect several tool calls later. Three instances now; the third cost both directors an entire QA report they never received.
3. **VERIFY DELIVERY ON DISK. The `posted ->` line is not evidence** — it prints relative path segments and reads identical on a misdelivery. `ls comms/<role>/inbox/ | grep <timestamp>`. Standing check: `find .worktrees -path '*/comms/*/inbox/*'` must be EMPTY — **anchor that pattern to the mailbox shape**, because a loose `*comms*` match false-positives on the many tracked docs whose filenames contain "comms," and a detector that cries wolf is one you learn to ignore.

4. **A RULING IS A MUST-PERSIST ITEM, AND THE COURIER'S COPY CARRIES AN HONEST LABEL** (CHARC amendment to `harness-architecture.md` §3 + RD's correction, both 2026-09-08; CHARC lands the §3 text at his next touch, this is the orchestrator's half). The mailbox is TRANSPORT, NOT A TRACKER: a director ruling that lives only in `comms/` is one clone away from gone and its FINDABILITY decays with every ack — the failure is DISCOVERY, not loss (`comms/` itself does survive a handoff on this machine). So a ruling is transcribed into the arc's **COMMITTED ledger** (executing ledger for executing-stage rulings, plan ledger for plan-stage), with the **ruling seat named as author and the transcriber as courier only**. **The packet is NOT LANDED until the courier's transcription is committed and its path posted back** — until then the ruling is in flight, and saying otherwise is the Phase-21 close-audit class. **Label the copy honestly:** either a literal block quote, OR the label **"re-set, verified by the ruling director"** — a re-setting labelled "verbatim" is the preserve-the-quote class one step removed, and only the ruling director can move it from the first form to the second by verifying it. *(Live instance: the 22-A4 fork ruling, re-set in `docs/22-a4-fork-fix-leg-dispatch-brief.md` §2 and labelled "transcribed verbatim" in the handoff; RD verified the CONTENT faithful and corrected the LABEL, and the correction itself arrived by role-mail — i.e. into the same hole. Both labels corrected in git.)*

**And when an inbox reads empty: RE-READ before concluding it.** A bare "inbox is empty" immediately after a posting notification can be a write/read race — observed once, resolved on the next read moments later. There is no timestamp filter in the reader (`_now()` only stamps outgoing posts), so an empty result is not evidence that a director did not post. Cheap to re-check; expensive to conclude wrongly.

**The IMPLEMENTER never posts to the mailbox — the ORCHESTRATOR does, and only AFTER QA.** Return reports flow: implementer → orchestrator (the implementer's final chat message, operator-relayed) → orchestrator QA against disk → THEN the orchestrator posts the QA'd report to the directors. A dispatch / executing-plans prompt MUST NOT instruct the implementer to run `role_mail.py post` (and NEVER `--from orchestrator` — that impersonates this role and bypasses the QA gate). The implementer's final brief step is always "return report as your final chat message," nothing more. (Caught 2026-06-12: the Arc 17-A executing prompt's Step 9 told the implementer to post its `return_report` straight to charc+operator, skipping QA — a brief-template defect, not an implementer deviation. A brief §8 / dispatch step that says "return report via the mailbox" must be read as the orchestrator's post-QA action, and dispatch prompts must be authored accordingly.)

Additionally, post LIFECYCLE events as `--type status` to both directors as they happen, so the directors follow arc state in real time:

- copowers-phase transitions: brainstorm / writing-plans / executing-plans **dispatched** or **returned**.
- generational handoff: include the handoff-brief path in the body.
- phase close.

The information-vs-authority line: the mailbox carries *information* (status, queries, return reports) between roles. **Dispatch-direction** (commissioning briefs, implementer dispatch prompts, approvals) carries *authority*, which is the operator's alone. **Amended 2026-06-26 (operator):** a director MAY post a dispatch directly to the orchestrator's inbox (`comms/orchestrator/inbox` — a SINGULAR inbox since arc 21-D, 2026-07-27; the old per-generation `comms/orchestrator/<sid>/inbox` is retired and a `--to orchestrator:<sid>` address now FAILS with an actionable message rather than misrouting) **once the operator has pre-authorized the action** — a director's action-bearing inbox message carries the operator's IMPLIED approval (authority granted before the director sends; the director is the courier, not the source of authority; the operator reviews via the comms GUI). Treat such a dispatch as you would an operator-hand-carried prompt. `decision_request` stays the operator's type only; `role_mail.py` refuses to route it to a non-operator (the L1 lock). Bootstrap a fresh orchestrator generation with `scripts/orchestrator_bootstrap.md`.

### Bug-fix briefs and operator-confirmation gate

For bug-fix briefs where the mechanism is not yet diagnosed (scope: "Investigation comes first; fix comes second"), require an explicit **operator-confirmation gate** between the investigation phase and the fix phase. This prevents the failure mode demonstrated by Bug 2 (2026-04-25) — implementer assumes a plausible mechanism, builds a fix that's internally correct but addresses a different path than the one operator is hitting.

**Brief language template (insert between investigation phase and fix phase):**

```
### Investigation-phase operator-confirmation gate (before §X fix phase)

Before designing the fix, draft a "mechanism candidate" message back to
the operator containing:
  - The mechanism you believe is causing the bug
  - The reproduction sequence you used to confirm it (concrete steps)
  - Specific evidence (network trace, response body, DOM state, etc.)
  - Explicit confirmation request: "Does this match what you see?"

Wait for operator confirmation before proceeding to design the fix. If
the operator says "that's not what I see," repeat investigation with the
new information. Do NOT design the fix until the mechanism is
operator-confirmed.
```

For FIX-DIRECT briefs (known mechanism, specified fix), the gate is not needed.

**Adversarial-review watch items for ALL bug-fix briefs:**

Standing watch items the brief should pass to `copowers:adversarial-critic` for any bug-fix dispatch:

- "Did the investigation empirically reproduce the operator's EXACT symptom (not a plausible-but-different mechanism that produces a similar-looking failure)?" Bug 2 (2026-04-25) demonstrated this failure mode.
- "Did the fix address the root cause, or only the surface symptom?" Sometimes the symptom can be made to go away without understanding why — that's brittle and likely to recur.
- For UI bugs specifically: the project lacks a JS test harness (see `docs/phase3e-todo.md` JS-execution test harness gap). String-match assertions on rendered HTML confirm structure but NOT runtime JS behavior. Operator manual verification is the actual confidence source for JS-behavior fixes; document the verification steps in the return report.

### Housekeeping commits

Periodically, accumulate untracked drift + small backlog updates + minor documentation corrections into a single small "housekeeping" commit. Pattern: `docs/{phase}-housekeeping-brief.md` brief; one-session implementer work; landing commits like `docs: track {description}`. Examples shipped: `4f74493` (Tranche B cleanup), `b03f66a` (B-ops cleanup), `2df7adb..6c179de` (post-2c housekeeping).

**Don't let housekeeping accumulate.** When 5+ untracked artifacts exist or 3+ small follow-ups have been deferred, dispatch a housekeeping commit.

---

## Binding conventions (project-wide)

These come from CLAUDE.md but are restated here because you'll be drafting briefs that enforce them:

- **Branch:** `main`. No feature branches.
- **Commits:** conventional-commits. **No Claude co-author footer. No `--no-verify`. No amending.** Commit-message conventions (formalized 2026-04-26):
  - **Task implementation commits** MUST include task ID: `feat(area): Task X.Y — <description>`. Partitioning-prevention surface; makes duplicate-task detection trivial.
  - **Adversarial review-fix commits** SHOULD include round + finding ID: `fix(area): Codex R1 Major 2 — <description>` or `test(area): Codex R3 Minor 1 — <description>`. Audit-trail surface; not partitioning-relevant.
  - **Internal-Codex review-fix commits** (subagent-driven within-task review BEFORE orchestrator-wrapper Codex round) use the `(internal)` qualifier: `fix(area): Codex R1 Major 1 (internal) — <description>`. Distinguishes from orchestrator-wrapper Codex commits without breaking the subject-only grep regex (matches both forms when invoked correctly per the regex syntax note below). Phase 6 surfaced the disambiguation need (commit `c215c79` was internal-Codex; `13d0deb` was orchestrator-Codex; both labeled "Codex R1 Major 1" caused audit confusion).
  - **Subject-only grep observable verification** (regex amended 2026-04-27 post-Phase-7-implementer Q1): subagent invokes `git log -E --pretty='%s' --grep='^[a-z]+\([a-z]+\): Task X.Y'` (ERE flag `-E` + POSIX digit class) BEFORE each task implementation commit. **The `-E` flag is required** — git's default Basic Regular Expression mode treats `+` as a literal character, not as a quantifier; without `-E`, the grep silently returns empty even when matching commits exist (the "expected empty" output then matches for the wrong reason). For matching Codex/internal-Codex round labels, the canonical regex form is `^[a-z]+\([a-z]+\): Codex R[0-9]` (POSIX `[0-9]` instead of `\d` because POSIX regex doesn't support Perl-style character classes). Phase 7 implementer-side discovered the BRE incompatibility empirically (commit chain `528d38b..ca66216`); convention amended to specify ERE + POSIX explicitly.
  - **Internal code-review fix commits** (per Phase 5 precedent) use `code-review` prefix: `fix(area): code-review I1 — <description>` or `fix(area): code-review T6.1 — <description>`. Distinguishes from Codex review by review source.
  - **Format-only cleanup commits** (ruff, comment, whitespace) no task ID needed: `style(area): ruff UP037 cleanup`.
- **TDD:** failing test first, minimal implementation, pass, commit. One red-green cycle per logical change.
- **Phase isolation:** during Phase 3 work, `swing/trades/` and `swing/data/` are read-only unless an explicit carve-out is granted in the brief. Carve-outs require justification and listing of specific files touched.
- **DB location:** `%USERPROFILE%/swing-data/swing.db` — outside the Drive-synced folder. Never violate this; SQLite + Drive sync = corruption.
- **Tests:** `python -m pytest -m "not slow" -q` is the fast suite; must stay green. Slow suite (`-m slow`) is network-dependent; don't require it for routine validation.
- **Frozen-clock convention for date-touching tests (R2 rider, added 2026-06-12 with the Phase 17 Arc 17-A dispatch; debt item D9).** NEW tests that exercise date/session logic (`datetime.now()`, `date.today()`, `action_session_for_run`, session anchors) MUST pin the clock via a frozen-clock fixture rather than reading the live wall clock — this closes the day/DST-boundary false-green family (memory `feedback_no_false_green_claim`, 2026-05-30; ~90 legacy files call live clocks per CHARC register D9). **No retrofit** — the convention applies to newly-added tests only, not a sweep of existing ones.
- **Out-of-scope catches get a DURABLE landing the moment they are noticed (convention amendment, operator-approved, CHARC-originated, 2026-06-12).** When an implementer or orchestrator notices a defect or gap OUTSIDE the current dispatch's scope, it gets a durable home in the SAME breath as the notification — post a `role_mail` fyi (`--to charc,operator`) OR add a line to the current phase's open bug-container arc (17-D this phase). A chat-only mention is NOT sufficient: chat notifications evaporate with the session — a Phase 16 implementer's shape-identification invariant catch was lost exactly this way. (Complements the §Anti-patterns "flag in return reports, don't fix inline" discipline — this governs WHERE the flag durably lands.)
- **Ruff:** `ruff check swing/` baseline is 18 errors (E501 only) as of the 2026-05-10 polish-bundle ship (`efd3e15` cleared 8 N818 via mechanical exception-class rename batch; `9c9b57c` had previously brought the broader baseline 78 → 26 — see `docs/phase3e-todo.md` 2026-05-10 entry for residual breakdown). Earlier baselines for historical reference: 26 post-sweep / pre-N818; 98 pre-2026-05-10 sweep; 91 pre-Phase-5; 81 pre-Phase-7 (drift between historical anchors was pre-existing-legacy or ruff-version drift, not introduced by dispatches). Briefs forbid introducing new violations; the residual 18 E501 are explicit banked-for-bundling items per the phase3e-todo entry, not free territory for incidental fixes outside the bundle. Verify via `ruff check swing/ --statistics` not `wc -l` (default ruff output is multi-line per violation).
- **Adversarial review** on code-shipping sessions is mandatory (standing convention).
- **Executing-plans dispatch convention (formalized 2026-05-02 post-Phase-5).** Direct invocation of `superpowers:subagent-driven-development` followed by `copowers:adversarial-critic` (NOT the `copowers:executing-plans` wrapper, which bundles both phases without marker-file management between them). Workflow: (1) `superpowers:using-git-worktrees` to create isolated worktree (REQUIRED per `subagent-driven-development` skill docs); (2) `touch .copowers-subagent-active` to activate the global PreToolUse Codex-blocking hook (`~/.claude/hooks/block-copowers-during-subagent.sh`, registered in `~/.claude/settings.json`) which physically prevents subagents from invoking `copowers:adversarial-critic`, `copowers:review`, or `mcp__plugin_copowers_codex__codex*`; (3) invoke `superpowers:subagent-driven-development` to execute tasks; (4) `rm .copowers-subagent-active` after all tasks complete; (5) invoke `copowers:adversarial-critic` directly with PHASE/SPEC_PATH/PLAN_PATH/BASELINE_SHA; (6) operator-witnessed verification gate; (7) merge worktree to main. Hook is global (active for ALL Claude Code sessions across ALL projects on this machine); subagents physically cannot bypass. See `docs/phase5-configuration-page-executing-plans-brief.md` (`671451f`+, revised) as the canonical brief template for this workflow.
- **Worktree + editable-install verify-command (formalized 2026-05-02 post-Phase-5).** When a worktree-isolated dispatch needs runtime/browser verification via a CLI entry point (e.g., `swing web`), the verify-command MUST point at the worktree's package, not the editable-install path. PowerShell: `$env:PYTHONPATH = "."; python -m swing.cli web` from inside the worktree dir. Bash: `PYTHONPATH=. python -m swing.cli web`. Pytest is not affected (cwd-based discovery); CLI entry points ARE affected (editable-install resolver). Specify in any brief that uses worktrees + needs runtime verification.
- **Worktree directory path MUST be `.worktrees/<branch>/` at repo root (formalized 2026-05-09 post-polish-bundle-ship + cleanup-script extension).** Worktree-isolated dispatch briefs MUST specify the worktree directory path explicitly in §3 binding conventions OR §8 dispatch metadata. Required path: `.worktrees/<branch>/` at repo root — NOT `.claude/worktrees/<branch>/` (the `superpowers:using-git-worktrees` skill default). Rationale: `.worktrees/` is the project-precedent location aligned with the elevated-cleanup script `cleanup-locked-scratch-dirs.ps1` (which scans both paths as of 2026-05-09 but `.worktrees/` is the canonical naming) AND aligned with Phase 5/6/7/8 ship history (cleanup recurrence patterns + ACL-handling discipline). The 2026-05-08 lesson on worktree directory path discipline is now elevated to a binding convention; new briefs MUST include the explicit path. Failure mode (from Phase 8 V1 polish dispatch 2026-05-07): brief specified branch name only; implementer's `using-git-worktrees` invocation chose `.claude/worktrees/phase8-v1-polish/` per skill default; husk required separate `git worktree remove --force` to clean up because cleanup-script targeting was `.worktrees/` only. Cleanup-script extension landed 2026-05-09 covers both paths; brief discipline still required.
  - **(2026-06-12 reinforcement — home-dir-leakage chore.)** Sibling-of-repo worktree dirs (`C:/Users/rwsmy/swing-<arc>-plan`, `../swing-trading-sqlite-lock`, etc.) are **DEPRECATED** — they are the leak source that scattered orphaned husks one level above the repo (cleaned 2026-06-12). **ALL implementer worktrees live at `<repo>/.worktrees/<name>`** — repo-contained, gitignore-covered, swept by the cleanup script. Every dispatch brief MUST specify the `.worktrees/<name>` path; never let `using-git-worktrees` pick a sibling or `.claude/worktrees/` default. The `.worktrees/` ignore was moved out of the untracked per-clone `.git/info/exclude` into the **tracked `.gitignore`** (2026-06-12) so the ignore is reviewable and travels with the repo.

---

## Anti-patterns to avoid

These have caused real problems; resist the impulse:

- **Drafting briefs that reference "uncommitted" files without verifying current `git status`.** I made this mistake on the post-2c housekeeping brief (claimed Bug 7 in Bugs.txt was uncommitted; it had been committed by Session 2b's mid-session catch-up). Always verify before asserting tracking state.
- **Padding triage responses with structure that doesn't earn its space.** Headers + bullets + tables when a few sentences would do is noise. The developer reads carefully; respect their time.
- **Introducing new strategic framings without operator approval.** This is the operator-drives discipline. If you have a new framing in mind, present it as "want to discuss?" not as fait accompli.
- **Proposing action when only triage is needed.** Sometimes the right response is "clean session, standing by." Don't manufacture next steps just because the developer asked for triage.
- **Re-litigating decided framings.** The decisions in §"Recent decisions and framings" are settled. Don't reopen them unless the developer does.
- **Vacuous regression tests.** A test that passes under both pre-fix and post-fix code is worse than no test. Memory file `feedback_regression_test_arithmetic.md` captures the canonical example.
- **Mid-session scope expansion.** Bug-class issues discovered mid-session in OTHER surfaces should be flagged in return reports, not fixed inline. The pipeline-linkage session correctly flagged `build_watchlist` per this discipline.
- **Treating "diagnose, don't decide" as soft.** When a study or diagnostic is scoped as descriptive, sneaking in implicit recommendations through "should" framings or threshold suggestions violates scope. The reviewer will catch this; better to write the discipline in correctly the first time.
- **Re-fetching expensive data when it can be cached.** yfinance has rate limits. Diagnostic studies should use cache-warm patterns; never burn yfinance quota for re-runs of already-fetched data.
- **Brief internal inconsistency between "mirror canonical" and prose-asserted counts.** When a brief points the implementer at a canonical template AND prescribes an independent count of cases, the count must match the canonical OR the deviation must be called out explicitly. The build_watchlist mixed-anchor fix brief had §0 say "mirror canonical" (3 tests) and §4.1 say "add a second test" (2 implied); implementer correctly chose canonical-template fidelity but had to do judgment work I should have done at draft time. Always cross-check prose counts against any canonical references the brief points at.
- **Bug-fix investigation that tests plausible mechanisms instead of operator's actual reproduction.** Bug 2 (trade entry form vanishes mid-typing, 2026-04-25) demonstrated this failure mode: implementer interpreted operator's ambiguous symptom report ("when I adjust the price") as form submission with stop≥entry; built TestClient probe of POST /trades/entry with stop=entry; got 500 + bare-div response that gets hoisted out of `<tbody>` by HTML parser; declared mechanism identified; built fix for that path. Adversarial review approved because the fix was internally correct. Operator manual verification revealed the actual mechanism was different (sizing-hint span hx-target inheritance from parent form). First fix `04ef355→20d2cab` was correct for ITS mechanism but wasn't operator's bug; required follow-up `2a167d1` for the actual cause. **Pattern to avoid:** treating implementer's interpretation of operator's symptom as ground truth. For UI bugs especially: TestClient confirms server-side behavior but doesn't verify the bug fires through the path the operator is hitting. **Mitigation:** see §"Operating processes" §"Bug-fix briefs and operator-confirmation gate" — INVESTIGATION-FIRST bug-fix briefs must include an operator-confirmation gate between investigation and fix.

---

## Pre-Codex review + brief-authoring disciplines

> **Relocated (compressed) from CLAUDE.md 2026-05-28** per the operator-paired CLAUDE.md size restructure (Option B: compress code gotchas in CLAUDE.md + split process/review disciplines here). These are the **process / review / brief-authoring meta-disciplines** — they fire at orchestrator / dispatch / Codex-review time, NOT at code-write time (code-failure gotchas stay in `CLAUDE.md`). Full pre-compression verbatim text (dates, commit SHAs, Codex rounds, findings docs) → [`docs/CLAUDE.md-archive.md`](docs/CLAUDE.md-archive.md) §"Appended 2026-05-28". `#N` / "Expansion #N" labels are preserved so cross-references in shipped briefs still resolve. **Apply all of these in the pre-Codex review pass at every dispatch's brainstorming + writing-plans + executing-plans phases** (the cumulative "C.C lesson #6 validation").

### Pre-Codex review "Expansion #N" catalog (verify-before-lock)

- **Expansion #2 — brief-vs-actual-production-function-signature.** When a brief/spec/plan references a production function, grep its DEFINITION + verify (a) signature (param names, positional vs keyword, types); (b) side-effect contract (read-only vs write vs fetch-on-miss); (c) error semantics (raises vs None vs default); (d) documented invariants. Re-grep at writing-plans.
  - **#2 sub-refinement — cascade-call-graph.** Also verify whether the function invokes its documented sibling helpers (grep the body); don't infer cascade from naming/docstring. Under `from __future__ import annotations`, resolve return annotations via `typing.get_type_hints`, not raw `inspect.signature` (returns string forms).
- **Expansion #4 — SQL skeleton column verification.** Every SQL skeleton's columns / JOIN-ON / WHERE / subquery verified against the actual `swing/data/migrations/*.sql` before publishing. Brief-vs-actual schema reality check: grep migrations for any proposed NEW table/column before claiming it's new (it may already exist).
  - **#4 refinement — JOIN-cardinality + downstream-sufficiency.** Per JOIN, enumerate 1:1 vs 1:N; verify the result row-set is SUFFICIENT for the consumer (e.g. an RS-criterion evaluator needs the FULL universe, not just candidates); re-check the universe after any harness mutation (cleanup/fetch/fill).
  - **#4 sub-refinement — runtime-binding-shape + empty-result-set.** Per parameterized SQL, enumerate the binding shape (scalar vs list vs dict) and empty-input handling. (The sqlite3 list-bind / dynamic-`?` / empty-short-circuit specifics are also kept as a code gotcha in CLAUDE.md.)
- **Expansion #6 — content-completeness audit.** For each spec data-surface checklist item, enumerate per-field disposition LIVE / V1 PLACEHOLDER / V1 STUB before Codex. Silently rendering a stub as if it were live is the failure mode.
- **Expansion #7 — cross-row semantic scope audit.** For any POST handler consuming operator input + a cross-row lookup, enumerate the lookup SCOPE (ticker / pattern_class / candidate / pipeline_run) + cross-check against the spec's wording; add a plant-different-scope discriminating test.
- **Expansion #8 — per-counter / SQL-aggregation UNIT audit.** For each COUNT/SUM/GROUP BY AND each Python accumulator, state what unit it counts; add DISTINCT or CTE-then-aggregate to prevent JOIN-cardinality inflation; verify LIMIT applies at the right unit. Applies to ANY counter, not just SQL aggregates.
- **Expansion #9 — form-render anchor lifecycle audit.** For any hidden form anchor driving POST-time validation, audit 4 dimensions: (a) soft-warn confirm `form_values` round-trip; (b) GET-time query-param consumption; (c) candidate-snapshot consistency across pipeline runs; (d) explicit-anchor-vs-latest-snapshot validation order. (POST-time rejection-ladder + server-recompute are code gotchas in CLAUDE.md.)
- **Expansion #10 — architecture-location audit (+ 4 sub-disciplines).** When wiring NEW logic into an EXISTING module, verify the module has the dependency-context to host it (else new module + DI). Sub-disciplines: (a) triangulate template-vs-VM-parser-vs-emitter for "doesn't render" gaps; (b) renderer-kwargs uniformity LOCK + cache-collision test when a surface enum is reused by 2+ callers; (c) SQL LIKE wildcard-escape raw-vs-escaped per binding position; (d) orphan-label preservation when refactoring exact-match → delimiter-aware groupings.
- **Expansion #11 — taxonomy / attribution propagation audit.** When introducing a NEW enum (`kind`/`status`/`type`) OR any attribution metadata (`variable_name`/`source`/`tier`), propagate to all derived dataclasses + serializers (CSV/JSON/markdown headers) + test fixtures; downstream rendering must map by the FIELD, not a value-matching heuristic; paired `old_X`/`new_X` must source from the SAME baseline.
- **Expansion #12 — sibling-route audit under single-anchor-binding.** When introducing a single-anchor-binding discipline at one route, enumerate ALL sibling routes touching the same data/cache layer + verify each carries the anchor; the NO-RUN scenario must refuse a silent "resolve-latest-now" fallback (explicit None-guard + unavailable banner).
- **Expansion #13 — cumulative regression cascade audit.** When a Codex MAJOR fix RESTRUCTURES code (extract function / move logic out of a loop / new field), run an "imagined next-round" pass for 2nd-order regressions before invoking the next round; add tests for the NEW invariants the restructure creates.
- **Expansion #14 — recency / filter / dedup semantic-ordering audit.** For N sequential filter/dedup/aggregation steps, audit order of operations + attribution-metadata propagation (max/min/all of which field) + the downstream consumer's reference asof (filter-admit vs walk-forward must use the same asof).
- **Expansion #15 — narrative artifact path/fact lag.** A post-fix-bundle commit MUST sweep ALL narrative docs (findings, return reports, study writeups, status lines) for stale artifact paths + per-row facts (entry dates, R-values, session/column counts) whenever a new smoke artifact is emitted or any outcome shifts.
- **Expansion #16 — ASCII discipline scope clarity.** Declare ASCII scope EXPLICITLY across ALL flowing-through-stdout surfaces (narrative + source + tests + smoke + manifest + CLI help) and assert programmatically via `text.encode("ascii")` over the declared set. (The CLI-stdout cp1252 crash is a code gotcha in CLAUDE.md.)
- **Expansion #6/#7 process note — the 5-expansion pass does NOT catch content-completeness vs spec text NOR cross-row semantic scope on operator-input flows** unless #6 + #7 are run explicitly; pre-Codex review must walk each spec data-surface item + each cross-row lookup scope.
- **Pre-Codex review must cross-check spec source-of-truth against dispatch-brief sketches** — the brief's prescriptions (caps, tuples, thresholds) may be wrong vs the spec's BINDING text at the cited section; verify against the spec, not the brief alone.

### Brief-authoring + applied-research methodology disciplines

- **(#33) Cohort-validity-vs-verdict-criteria.** Briefs with criterion-based verdict thresholds MUST additionally bind the evaluation cohort; if the canonical cohort yields fewer than N patterns, report INSUFFICIENT SAMPLE — do NOT substitute a more-favorable alternative cohort. (Banned narrative terms LOCK also lives here.)
- **(#34) Brief-prescription cross-table verification.** When a brief prescribes a (sweep_point + count) tuple from an analytical artifact, cross-check the artifact SUMMARY TABLE (authoritative) against the per-variable drill-down header; the summary table wins on disagreement.
- **(#35) Substrate-density metric disambiguation.** When a brief carries a numerical anchor (density/survival/rate/fraction) from a prior arc, quote the exact numerator + denominator + pre-filter + semantic intent; verify metric-compatibility with the new brief's usage (e.g. `F/T` per-ticker productivity ≠ `F/R_raw` survival rate).
- **(#36) Two-Codex-chain default for applied research dispatches.** Default to TWO Codex chains: chain #1 implementation review BEFORE smoke-artifact emission; chain #2 methodology + narrative review AFTER smoke + findings draft. Single-chain requires explicit Sec 7 justification (e.g. <100 LoC, no smoke, no findings narrative). The single C.C-lesson-#6 validation slot spans both chains.
- **(#37) Substrate-freshness sensitivity.** Briefs carrying a prior-arc cohort fixture + R-value anchor MUST cite (a) the cohort fixture SHA; (b) the filter params; (c) the source-artifact SHA the fixture derived from; (d) a regeneration-stability assertion. Implementer Slice-1 discriminating test asserts brief-stated N matches actual filtered-N within tolerance; escalate via Brief Amendment on mismatch (cohort fixtures regenerated over time drift their FILTERED membership — `max_observed_asof_date` shifts patterns in/out of recency windows).
- **(#38) Pre-commission premise verification — does the capability already exist?** Before scoping a NEW-capability arc (new command/module/mechanism), grep ALL of `swing/` for a PRE-EXISTING mechanism that already provides it — not just the one adjacent mechanism you happen to know. The capability-level analog of Expansion #4's "grep migrations before claiming a table is new." Failure mode (17-C, 2026-06-13): the orchestrator commissioned `swing exports cleanup` for exports retention having found only the adjacent `_prune_shadow_expectancy_artifacts`; `swing/rendering/retention.py:archive_old_exports` (a DIFFERENT package) already zip-retained dated `exports/<date>/` dirs every pipeline run → the arc was redundant at the 90d default + data-UNSAFE at shorter windows. Caught only at writing-plans by the implementer's brief-vs-live-code grounding (Expansion #2). Grep BEYOND the package you expect; verify the arc's FOUNDING PREMISE ("X doesn't exist yet"), not just the referenced-function signatures. Memory: `feedback_brief_premise_check_existing_mechanism`.
- **(#39) Schema-boundary defensive-scope — don't build per-case handling for schema-forbidden data (operator, 2026-06-15).** Data states the SCHEMA forbids (`NOT NULL` / `CHECK` / `UNIQUE` / typed columns) are caught at the WRITE boundary (the constrained writer / repo / migration). A downstream READER (monitor / consumer / aggregator over OUR OWN constrained DB) MUST NOT proliferate per-value-shape branches for out-of-schema values; it needs only (a) a GENERAL error handler that degrades gracefully (never crashes) + (b) LOGGING sufficient to IDENTIFY the gap if a hole ever lets bad data pass. In briefs/plans for readers, scope defensive handling to genuinely-unconstrained inputs (missing / pre-schema tables, absent / corrupt FILES, external-API payloads) + that one general degrade+log path — NOT per-malformed-value cases for schema-constrained columns. **Review-adjudication corollary:** a Codex finding premised SOLELY on a malformed / out-of-range / duplicate / NULL value inside a schema-typed column is OUT-OF-SCOPE-for-V1 (cite the constraint) — NOT a blocking major; converge once only that class remains. This BOUNDS what counts as a blocking major; it does NOT reinstate the suspended round cap (memory `feedback_codex_round_limit_suspended`). Origin: the 18-D executing review treadmill (~13 `review-strong` rounds, most surfacing new degraded-VALUE permutations on the same coverage/structural date-parsing — one guard against a schema-`UNIQUE`-prevented duplicate whose test skipped; one R10→R11 fix-introduced regression). Memory: `feedback_schema_boundary_defensive_scope`. **Orchestrator QA check (CHARC-mandated, 2026-06-15; `docs/18-D-treadmill-review-adjudication-charc.md` `a8632d41`; recipe §3 `94ac2905`):** at convergence-verification (the transcript-read of `.copowers-findings.md`), confirm EVERY finding adjudicated "schema-prevented / out-of-scope" CITES the exact constraint (the migration / `CHECK` / `UNIQUE` / `NOT NULL` / FK line) AND verify that constraint actually prevents the value — READ the migration; never ASSUME the defense (the 18-E lesson: a `CHECK` weaker than claimed, or a column missing the constraint, is a REAL hole, not dead code). A dismissal WITHOUT a verified citation is wrongly-dismissed → re-open it (it stays in-scope). This citation-verification is the safety valve that keeps the corollary from becoming a footgun.
- **V1-simplification banking discipline.** Every V1 placeholder / stub / simplification the implementer ships MUST be enumerated in the return report (§6 or equivalent) WITH its V2 dependency cited. Pre-Codex review's content-completeness audit (#6) is the gate; the return-report table is the permanent ledger.

### Process hygiene

- **(#1) Test-count drift in plan docs.** Plan/brief test-count estimates go stale — trust `pytest` output, not the plan. (Same failure family as cohort-size estimates being empirically falsified.)
- **Auto-memory staleness.** The auto-memory at `~/.claude/projects/.../memory/` can go stale (e.g. `project_refactor_intent`); verify against current `git log` before relying on it.
- **Executing dispatches run the FULL fast suite BEFORE the Codex review AND after it converges (universal; banked 2026-06-15, operator-directed).** Two runs, two distinct failure modes: **(1) BEFORE** — after all task-commits land, run `pytest -m "not slow" -q` and fix any failure BEFORE starting the Codex loop, so the review converges on a GREEN diff. This catches **cross-cutting / global-invariant tests** that per-task TDD does NOT exercise — e.g. `test_topbar_cross_vm_consistency` ("every base-layout VM in the manifest"), `test_theme_css` ("no raw hex outside the theme blocks"), schema-enum-mirror tests — which otherwise stay latent until the end-of-run suite, AFTER the review has already converged, forcing a wasted fix + re-review cycle (the 18-F cost: the theme-token + VM-manifest regressions surfaced only at the final full-suite run, post-convergence → an extra cycle). **(2) AFTER** — once Codex converges, re-run the full suite on the final diff: the binding no-false-green gate that catches review-FIX-introduced breaks. The orchestrator includes BOTH runs in every executing-dispatch prompt's verification steps. (Flagged to CHARC 2026-06-15 to mirror this in `docs/implementer-dispatch-recipe.md` §verification — the implementer SPOF.)

---

## Maintenance: retention discipline

> Added 2026-05-05 as part of the handoff-document structural separation refactor. This section governs ongoing curation of this file + `docs/phase3e-todo.md` to keep fresh-orchestrator bootstrap consumption bounded over time.

### Active vs archive boundary

Two pairs of handoff docs:

- `docs/orchestrator-context.md` (active; canonical filename) + `docs/orchestrator-context-archive.md`
- `docs/phase3e-todo.md` (active; canonical filename) + `docs/phase3e-todo-archive.md`

Bootstrap discipline: fresh-orchestrator session reads only the active files (this one + `docs/phase3e-todo.md`) + `CLAUDE.md` + `git log -20` + `git status`. Archive companions are searchable on demand via Grep / Read.

### Brief-corpus archival at phase close (CHARC-authored — harness convention; canonical text in `tool-director-context.md §4.3`)

At each phase close, the close-housekeeping ritual `git mv`s that phase's DEAD dispatch artifacts — commissioning/dispatch briefs, writing-/executing-plans, implementation plans, orchestrator handoffs, per-arc audits + Codex review transcripts — into `docs/archive/phase<N>/`. **No cooldown** (a merged arc's brief is dead; this differs from the one-phase-cooldown for `phase3e-todo.md` SHIPPED entries below). The live durable docs stay top-level: charters, the `*-state.md` pointers, `harness-architecture.md`, the active-phase `todo`, `implementer-dispatch-recipe.md`, `runbooks/`, comms-design docs, references. This makes the existing `docs/archive/phase16`/`phase17` practice a standing rule. The probe (`harness_probe.py`, §4.2) counts top-level `docs/*.md`, so this archival reduces the tracked corpus. **Phase-18 close = ALSO sweep the one-time pre-phase-16 + Phase-18 backlog (~450 top-level files; bucket by phase where determinable, else a `docs/archive/pre-phase-16/` catch-all).** CHARC's phase-close audit verifies the top-level count dropped. **Sweep safety (CHARC-authored 2026-07-03 — D21):** a docs-only `git mv` is NOT suite-neutral — research L2-reinforcement tests hard-code `docs/<brief>.md` paths (6 broke at the Phase-18 sweep; main sat 6-red for 6 days). Before committing a sweep, grep `tests/` + `swing/` + `scripts/` for every moved filename (repath or defer any referenced file); re-run the fast suite AFTER the sweep commit — the close's "suite green" claim must postdate the close ritual's LAST commit. When that grep hits a TEST reference, consult the test's retirement marker: brief-coupled doc-assertions are ARC-LIFECYCLE-SCOPED (RD standard 2026-07-03, D21) — retire-at-close once the content is banked per RD's close-time check, repath only the rare still-load-bearing case; artifact/harness LOCKS in the same files stay.

### Cooldown rules (when to migrate)

Migration triggers, in order of frequency:

1. **End of phase ship.** When a phase merges to main, migrate that phase's SHIPPED `phase3e-todo.md` entries to the archive. One-phase cooldown (don't archive the same phase that just shipped — give one ship-cycle of "still warm" context). Worked example: Phase 7 shipped 2026-05-05 at `c617777`; Phase 6 SHIPPED entries (Phase 6 sub-bundle of journal v1.2) migrated to archive at this dispatch. Phase 7 SHIPPED entry migrates to archive at end of next phase ship (Phase 8 or Phase 9, whichever lands first).
2. **Lessons-captured cap.** Active `Lessons captured` section maintains last ~30 entries. When a new lesson lands and pushes the count past 30, the oldest lesson migrates to archive (or promotes to CLAUDE.md if it's durable code-failure prevention; see below).
3. **Recent-decisions supersession.** When a "Recent decisions and framings" entry is fully superseded by a later decision, archive the old entry with a cross-ref to the superseding one. When refined (not fully superseded), keep both with cross-ref. Default-conservative: when in doubt, KEEP in active. Re-litigation risk dominates.
4. **Tripwire-fired entries.** When a trigger-gated `phase3e-todo.md` entry resolves (e.g., 2026-05-04 worktree-cleanup-script entry RESOLVED 2026-05-05), migrate to archive with `TRIGGER FIRED + RESOLVED YYYY-MM-DD` footer. Mirror the worktree-cleanup-script + handoff-document-growth precedents.

### Lesson promotion: archive vs CLAUDE.md

For lessons being aged out of the active section:

- **Promote to CLAUDE.md gotchas** if the lesson durably prevents code failure for future sessions (e.g., yfinance API regressions; HTMX failure surfaces; Windows ACL gotchas; SQL/Python idiom collisions; matplotlib mathtext quirks). CLAUDE.md is auto-loaded so the gotcha fires every session, not just when grep'd.
- **Archive (no promotion)** if the lesson is process-only / single-incident-historical / discipline-applied-to-orchestrator-thread (e.g., commit-message convention refinements; subagent-collision diagnosis history; specific phase-handoff items).

Most older lessons (the 96 archived 2026-05-05) fall into "archive only" — their durable code-failure prevention has already landed in CLAUDE.md gotchas. Re-promotion would duplicate.

### Archive-split trigger (hierarchical decomposition deferred)

If an archive file exceeds **~80k tokens** (mirrors the active-file pressure point that motivated the original split), revisit hierarchical decomposition. Likely categorization at that point: SHIPPED-by-phase + lessons-by-domain (HTMX / yfinance / Windows / SQLite / dispatch-discipline / brief-drafting) + decisions-by-quarter. Defer category invention until the trigger fires — data informs categories better than upfront design.

### Size-check trigger at housekeeping-commit time (added 2026-05-18 PM per CLAUDE.md evaluator pass — Option B2 restructure)

At every housekeeping-commit step (when appending a new SHIPPED entry to status-tracking docs), verify the following soft thresholds — if exceeded, the housekeeping commit MUST include a triage step (archive-split, restructure, or compact-summary swap) rather than silently growing the surface:

| Doc | Surface | Soft threshold | Trigger response |
|---|---|---|---|
| `CLAUDE.md` line 3 ("Current state" summary) | Single paragraph; pointer-heavy; not a SHIPPED ledger | **>2,000 chars** | Trim back to ~5-10 sentences; preserve as compact summary; do NOT regress to a ledger paragraph (history goes to `docs/CLAUDE.md-archive.md`). |
| `CLAUDE.md` §"Gotchas" (added 2026-05-28 Option B) | Code/runtime/test failure-prevention; **trigger + fix only** | **>~55K chars total, OR any single gotcha >~700 chars, OR a process/review discipline added here instead of to orchestrator-context** | Compress the new/oversized gotcha to trigger+fix at banking time; relocate any process/review/brief-authoring discipline to this file's §"Pre-Codex review + brief-authoring disciplines"; append the full forensic detail (dates/SHAs/Codex-rounds) to `docs/CLAUDE.md-archive.md`. Do NOT bank verbose multi-paragraph forensic gotchas into CLAUDE.md. |
| `docs/orchestrator-context.md` §"Currently in-flight work" | Active + "Prior state" sub-sections | **>10 "Prior state" sub-sections retained** (per L-W2 conservative cap) | Trim oldest "Prior state" sub-sections to `docs/orchestrator-context-archive.md`. |
| `docs/orchestrator-context.md` §"Lessons captured" | Most-recent N retained per cap target | **>~40 entries** (cap target ~30; trigger at +10 over) | Migrate oldest 5-10 to archive companion. |
| `docs/phase3e-todo.md` (active SHIPPED entries) | Top-prepended SHIPPED entries | **>~25 SHIPPED entries** retained (or one quarter's worth) | Archive-split old SHIPPED entries to `docs/phase3e-todo-archive.md`. |
| `docs/CLAUDE.md-archive.md` + `docs/orchestrator-context-archive.md` + `docs/phase3e-todo-archive.md` | Append-only history companions | **No size threshold** (append-only by design) | N/A — companion docs grow; grep-on-demand only. Per §"Archive-split trigger" above, hierarchical decomposition reconsidered at ~80k tokens per file. |

**Rationale for the line 3 cap:** the Phase 12.5 #3 evaluator pass (2026-05-18 PM) surfaced that line 3 had grown to ~133K chars (~40K-50K tokens loaded into every fresh Claude Code session). Option B2 restructure replaced it with a compact ~1.3K-char "Current state" summary; this cap discipline prevents regression to the wall-of-text shape. The "current state" line is meant to be a 5-10-sentence orientation for fresh sessions, pointing them at `docs/orchestrator-context.md` + `docs/phase3e-todo.md` for detail.

**Pattern for triage at housekeeping-commit time (operator-driven OR orchestrator-self-checked):**
1. Pre-commit (before drafting the housekeeping commit message): compute size of each surface above (`wc -c`, char counts, sub-section counts).
2. If any threshold exceeded: PAUSE the housekeeping-commit + draft a restructure plan + escalate to operator decision (do NOT defer to next session — defer leads to drift; the wall-of-text shape that motivated this discipline emerged precisely because per-session size pressure was below per-session deferral pressure for months).
3. If thresholds clear: proceed with housekeeping-commit normally.

**Where this discipline applies:** every housekeeping commit landing after an integration merge OR after a meaningful in-flight decision worth recording in handoff docs. The operator-facing daily routine at [`docs/cycle-checklist.md`](docs/cycle-checklist.md) does NOT include this discipline (it's purely operator-trading-cadence; housekeeping is an orchestrator action). A brief cross-reference is added at the bottom of cycle-checklist.md so operators reviewing the routine doc are aware that orchestrator-side housekeeping discipline lives here.

### Invocation cadence

- **At session-end after each ship:** quick check whether SHIPPED items in `phase3e-todo.md` should be migrated; whether the lessons cap has been exceeded; whether any "Recent decisions" have been fully superseded.
- **Operator-explicit:** operator can request retention-discipline pass at any time (e.g., "do a housekeeping pass on the handoff docs").
- **Quarterly or longer:** revisit the active-vs-archive boundary holistically; archive entries that are now firmly historical even if they didn't fire a per-incident trigger.

### What this section does NOT govern

- The structural-separation refactor itself (one-time work; SHIPPED 2026-05-05).
- Removing content from `CLAUDE.md` §"Quick Start" / §"Strategy" / §"Architecture" / §"Invariants" / §"Conventions" / §"Windows + gitbash" sections (these are curated by their own discipline; project-conventions are append-mostly). **Note (2026-05-18 PM Option B2 restructure):** the CLAUDE.md line 3 "Current state" summary IS governed by the size-check trigger above. **Note (2026-05-28 Option B restructure):** the §"Gotchas" section is NOW governed by the size-check trigger above and is NO LONGER exempt — new code gotchas are banked as compressed trigger+fix; process/review/brief-authoring disciplines are banked into this file's §"Pre-Codex review + brief-authoring disciplines" (NOT CLAUDE.md); full forensic detail goes to `docs/CLAUDE.md-archive.md`. The remaining body sections (Quick Start / Strategy / Architecture / Invariants / Conventions / Windows + gitbash) are NOT governed (per this exclusion).
- Memory entries (`MEMORY.md` index + per-memory files at `~/.claude/projects/.../memory/`); those have their own retention semantics.

---

## Lessons captured (with cross-references)

> **ARCHIVED 2026-06-12 (Phase-16 close, retention discipline):** the 30 full lesson
> narratives (~48K chars, Phase-12→15 era) moved verbatim to
> [`docs/orchestrator-context-archive.md`](orchestrator-context-archive.md)
> §"Lessons captured — archived at Phase-16 close". The durable code-facing
> essence lives in CLAUDE.md §Gotchas; the process essence in §Operating
> processes / §Pre-Codex disciplines above. The TITLE INDEX below is the
> grep-trigger — match a title here, read the full text in the archive.

- Schema-CHECK + Python-constant + dataclass-validator MUST land in the same task for atomic consistency.
- Cross-column CHECK precedence: schema-defended is defense-in-depth; service-layer is primary path.
- Plan-author schema additions DURING the writing-plans Codex chain need explicit spec-amendment-or-escalation BEFORE landing — not bank-after-write.
- Plan-size budget for architectural-pivot writing-plans: 3000-3700 lines for 4 sub-sub-bundles × ~50 tasks; 25% over schema-design-plan budget.
- 9-substantive-round Codex chain is the new project high-water mark (Phase 12 Sub-bundle C brainstorm 2026-05-15 at `d682c25`); chain shape healthy when finding-count taper is monotonic-with-cascade-cleanup-spikes; 4C+26M+15m total findings; ZERO ACCEPT-WITH-RATIONALE.
- Brainstorm-time composition-source claims need empirical verification BEFORE spec encoding; brief-author "spec will compose validators from shipped repos" is unfounded if shipped repos don't expose callable validators.
- Persisted-JSON-tier-1 vs re-fetched-tier-1 asymmetry: data shape constrains classifier determinism — when V1 mapper exposes less than the source provides, the missing-detail case MUST tier-2 even if the operator-locked tier-1 model would naively apply.
- Synthetic-fixture-only acceptance test for production-write-contract surfaces: don't contaminate production audit trail when payload-required choices exist in a multi-choice resolution menu.
- Brief enumeration of shipped CHECK enums needs empirical verification against migration files BEFORE encoding as binding §1.5 / §0.7.
- Orchestrator MUST commit the executing-plans dispatch brief to main BEFORE providing the inline dispatch prompt to operator — recurring procedural gap (2026-05-15 instance + prior unspecified instances; operator-surfaced 2026-05-15: "This is not the first time").
- Operator-paired-gate-caught implementation gap → orchestrator-inline gate-fix (precedent: 11B `34be84e` + 12A `e2c0384` + 12B `7b75d4a` — now 3 instances cumulatively).
- Operator architectural pushback supersedes orchestrator scope assumptions; reframe before bandaging.
- Brief-recommended technical micro-decisions should be empirically pre-tested against multi-row + same-second cases before plan adoption; "clever value-mangling" patterns (sign-flip, negative IDs, sentinel encoding) are fragile under concurrent insertion + tiebreak edge cases.
- Convergent multi-round Codex chains are healthy at 4-9 rounds when fix-introduced regressions are the failure mode; R-final confirmation pass with no new findings is a valid stopping pattern; tapered finding count is the diagnostic.
- Brief-premise empirical-verification extends to brainstorm-phase, not just writing-plans-phase.
- Repo functions must NOT call `conn.commit()` — caller controls transaction scope.
- Subprocess cfg-propagation: child-process CLI body is the binding override point, NOT the parent process that spawns it.
- HTMX form-driven endpoints have two browser-only failure surfaces TestClient cannot detect: HX-Request header reset on embedded forms + HX-Redirect for success-path response.
- Worktree-isolated dispatches + editable installs need verify-command pointed at the worktree, not the editable-install path.
- Exchange-session helper family has multiple members; brief author MUST specify forward (`action_session_for_run`) vs backward (`last_completed_session`) semantically.
- Brief-scoped read-only consumer modules force scope-vs-DRY tradeoff at writing-plans time.
- State-bearing entities require enumeration of ALL state-transition UI surfaces in the brief, not just the creation path.
- Production-write classifier soft-block under auto-mode: AskUserQuestion responses are NOT visible to the auto-mode classifier; only chat-text "yes, run X" authorizations are.
- `tomli_w.dump` is a one-way TOML serializer: comments + key-order + whitespace are dropped on write.
- Operator's "pause" means STOP all forward motion immediately, even items appearing independently confirmed.
- At worktree-side operator-witnessed gates, the `swing` console-script routes to the editable-install path (main repo), NOT the worktree's code. Use `python -m swing.cli <subcommand>` from worktree cwd.
- Orchestrator's wall-clock duration estimates for dispatched work are routinely 3-5x too long. When estimating Phase work, divide naive estimate by 3-5x to land on operator's actual experienced wall-clock.
- Sub-bundle architectural fix can hold in negative sense (no regression) while positive lift fails to fire — synthetic-fixture-vs-production-emitter shape drift family.
- Per-run-vs-per-fill re-emission family: each fresh reconciliation_run that finds no Schwab match for an open fill emits a new `unmatched_open_fill` discrepancy on that same fill, regardless of prior resolutions.
- Bash tool's persistent cwd across invocations CAN drift away from the primary worktree if earlier commands `cd` into a subdirectory. Use `git -C "<absolute-path>"` for cross-worktree git operations rather than relying on cwd.

## External tools available

Capabilities outside the repo that orchestrator/implementer sessions may consult during conversation. Listing them here so future sessions know they exist; details and governance status live in the linked docs.

- **`qullamaggie` MCP server** — knowledge-base wrapper around Kristjan Kullamägi's trading commentary (437 stream sessions, Oct 2019 – Dec 2021; ~2.5M words; 3,980 rules; 84 setup types; 1,214 tickers). Eight tools surfaced as `mcp__qullamaggie__*`. Configured user-global in `~/.claude.json`; runs as a daemon at `http://localhost:9871/mcp`. Source repo: `C:\Users\rwsmy\qullamaggie-mcp\`. **Reference-only; not a source-of-truth.** Promoting any aspect to production criteria or methodology requires V2.1 §VII.F. Full tool inventory, invocation patterns, and gotchas: `docs/qullamaggie-mcp-capabilities.md`.

---

## Memory entries (cross-session persistence)

The Claude memory system has these durable entries relevant to this project:

- **`MEMORY.md`** index lists project memories (3 new banked 2026-05-17):
  - `project_references.md` — Disciplined Swing Trader PDF + Minervini physical-only book.
  - `project_refactor_intent.md` — refactor later, not now.
  - `feedback_regression_test_arithmetic.md` — verify test arithmetic distinguishes pre-fix from post-fix.
  - `feedback_pause_means_pause.md` (NEW 2026-05-17) — operator's "pause" means STOP all forward motion immediately, even items appearing independently confirmed.
  - `feedback_worktree_cli_invocation.md` (NEW 2026-05-17) — at worktree-side gates, `swing` routes to editable-install path NOT worktree; use `python -m swing.cli` from worktree cwd.
  - `feedback_time_estimates_overstated.md` (NEW 2026-05-17) — orchestrator wall-clock estimates 3-5x too long; divide naive estimates by 3-5x for actual operator-paced wall-clock.

If you make a meaningful process discovery worth carrying across sessions, save it as a memory entry AND update this file's "Lessons captured" section.

---

## Key file locations

| Location | Contents |
|---|---|
| `CLAUDE.md` (root) | Current-state, conventions, gotchas. Auto-loaded. |
| `docs/Bugs.txt` | Operator-reported bug list. |
| `docs/phase3e-todo.md` | Operational backlog (active; canonical filename). |
| `docs/phase3e-todo-archive.md` | Archived SHIPPED + closed entries (grep on demand). |
| `docs/cycle-checklist.md` | Daily/weekly/monthly operator routine. |
| `docs/*-brief.md` | Dispatch briefs (one per implementer session). |
| `docs/superpowers/specs/` | Phase-design specs (e.g., Tranche B-ops session 1 design). |
| `docs/orchestrator-context.md` | This file (active; canonical filename). |
| `docs/orchestrator-context-archive.md` | Archived older lessons + superseded framings (grep on demand). |
| `docs/qullamaggie-mcp-capabilities.md` | Reference for the qullamaggie MCP server (tool inventory, governance status, suggested invocation patterns). |
| `reference/Future Work/` | V2.1, rebuttal-response, archived predecessors. |
| `reference/Future Work/QuantEcon/` | Forward-looking strategic content (program + companions + external references). |
| `reference/methodology/` | Source-of-truth methodology references (e.g., Minervini Trend Template transcription). |
| `research/README.md` | Research branch intro. |
| `research/method-records/` | Method records per V2.1 §IV.B format. |
| `research/studies/` | Study designs and evidence summaries. |
| `research/notes/` | Research notes (data-source evaluations, decision memos). |
| `research/harness/` | Research code (e.g., earnings_proximity replay harness). |
| `swing/` | Production codebase (consumed read-only by research branch). |
| `~/swing-data/swing.db` | Production SQLite DB (outside Drive). |
| `~/swing-data/research-cache/` | Research-branch OHLCV + earnings caches (outside Drive). |

---

## Session-start checklist for fresh orchestrator sessions

1. Read this file end-to-end.
2. Check `git log --oneline -20` to see recent commits.
3. Check `git status` to see untracked files or modified files.
4. Read `CLAUDE.md` (auto-loaded but worth re-skimming for the gotchas list).
5. Skim `docs/phase3e-todo.md` for current operational backlog.
6. Ask the developer: "What's currently in flight or recently dispatched? What's today's question?"
7. If the developer is mid-decision, present options with recommendation; don't decide for them.
8. If the developer raises a new strategic question, propose where in the existing framing it fits before drafting anything.

---

## Session-end checklist (when wrapping up a working session)

1. Update §"Currently in-flight work" with current state.
2. If a meaningful framing decision was made, add to §"Recent decisions and framings."
3. If a process insight was captured, add to §"Lessons captured."
4. If a new file or convention was introduced, update §"Key file locations" or §"Operating processes."
5. **Retention discipline check (per §"Maintenance: retention discipline" above):** end of phase ship → migrate that phase's SHIPPED `phase3e-todo.md` entries to archive (one-phase cooldown); lessons-captured cap exceeded → migrate oldest to archive (or promote to CLAUDE.md if durable code-failure prevention).
6. Don't update for trivia. Bias toward fewer, higher-quality updates.

---

## How to update this file

Small commits via the regular implementer-dispatch pattern, OR direct orchestrator edit during conversation (the developer will commit later as part of housekeeping). Either is fine.

When updating: keep sections in their current order. Add new sub-bullets rather than restructuring sections. The next orchestrator's mental model is shaped by the current organization; preserve it unless the developer agrees to a reorganization.

If active sections grow large enough that bootstrap becomes a token-budget issue, see §"Maintenance: retention discipline" — the structural-separation pattern is established (active vs archive companion); migrate aged content to `docs/orchestrator-context-archive.md` rather than splitting active into multiple files.
