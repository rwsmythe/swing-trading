# CHARC — Current State (single source of truth)

> **OVERWRITE this file each session/handoff — do NOT append.** The one always-current state pointer for the CHARC (Tool Development Director) role. The dated §6 log in [`docs/tool-director-context.md`](tool-director-context.md) is APPEND-ONLY history; the §4 register holds debt; [`harness-architecture.md`](harness-architecture.md) holds the cross-role rules. Current state lives HERE. Bootstrap reads this FIRST. Convention: [`harness-architecture.md`](harness-architecture.md) §6.

**Last overwritten:** 2026-08-17 — Demand C complete end-to-end; the owed recipe window DELIVERED; between-arcs state.

---

## #1 — WHERE THINGS STAND

**NO ACTIVE ARC.** The Phase-21 boundary-paydown wave is COMPLETE: D31-exit merged (`5a6d39cd`), **Demand C merged (`f133ba2a`) + live-migrated (schema v35→**v36**, migration 0036 `provenance_corrections`) + applied to trade 23 (CADL) at a witnessed six-step gate + cleaned up.** CADL's cohort keys corrected via the faithful derivation per RD's ruling: `hypothesis_label='A+ baseline (aplus); failed: TT8_rs_rank'`, `candidate_id=12341`, `trade_origin='pipeline_aplus'`; H1 `in_flight` 0→1, `current_sample` 2 unchanged (RD's arithmetic held on the live before/after). `provenance_corrections` holds exactly 1 row. Suite **11113/7/0** post-merge; trailer streak recounted **4574** with anchor `eabc0c16`. **An orchestrator generational handoff occurred 08-13** (clean boundary; the successor re-derived state from disk and dispatched executing on the operator's go).

**Items 6 (D32) and 7 (D9 sweep) of the original wave remain undispatched**, displaced by the Demand-C priority; they precede or join Phase-22 scoping.

## #2 — THE RECIPE WINDOW: DELIVERED 2026-08-17

Landed in [`implementer-dispatch-recipe.md`](implementer-dispatch-recipe.md) with dates and incidents attached: **§3 B-reassignment** (B is the ORCHESTRATOR's; a brief clause is the only thing that moves it — resolves the two-live-documents conflict the orchestrator had to hand-resolve mid-dispatch 08-13) · **the two-token anchored VERDICT line** (assertion 5) · **declared ENVELOPE + tag-never-suppress** · **accepted-limitations WITH reasons, challenge invited** · **content-filter events reported never silently rephrased** · **ANALYSIS-flavor criterion** for plan/doc reviews with the rebound warning · **FOLLOWON_DISPOSITION** · **CLAIMS_FIRST** on B · **SERVICE-prevented citation extension** (writer enumeration WITH the search + measured live incidence; D36 named) · **state-the-class-once-and-re-grep** · **closure-check-over-roster** (static walk, not runtime trace) · **the PATH-in-a-script-file hazard** · the five-round-gate discrimination evidence + bounded-continuation precedent. Previously landed 08-12: termination-rule-as-consequence, minors-only self-check, ROUND_LEDGER + round-5 check-in.

**Still owed, small:** merge-then-migrate as the banked shape (orchestrator-context material) · premise-verification-as-highest-yield-step as a named discipline (currently enforced via dispatch prompts; the Demand-C §1 re-derivation caught two brief errors, which is its evidence) · RD's both-modes arm-flag (banked, trigger not yet met). Banked with triggers: ENVELOPE_SEVERITY · FROZEN_CONSUMER_CHECK.

## #3 — OPEN ELSEWHERE (owner named)

| item | owner | state |
|---|---|---|
| **CADL/Demand-C follow-ons, banked** | named at merge | `list_provenance_corrections` one-malformed-row-aborts-all (V2) · `--reason` optional-in-parser/mandatory-in-service (minor) · 4 SERVICE-prevented accepted limitations (citations verified twice, incl. D36) |
| **`main` unpushed** | operator | ~33+ ahead at last report (08-13); grown since |
| **VSTS deadlock** | ratified (c)+(d) | Instance expires 2026-09-08; abandonment intent → Phase-22 |
| **Unexplained FTRE cessation** | RD | Banked; candidate silent-failure of the check; neither benign explanation established |
| **Disc 86** (equity_delta, immaterial) | — | The only open discrepancy in the ledger; monthly-deposit drift class |
| **Trail contradiction** | operator-ratified for Phase-22 | **THREE answers on one page** (screenshot: act-now 10MA trail prompt + 20MA hint in the SAME advisory block + NOT-YET-ELIGIBLE tile at the 21MA) — `advisory.py:483-485` fires `suggest_trail_ma` for both MAs, NEITHER call consults eligibility. **RD's interim ruling: the eligibility gate governs; "Trail stop up to" is the defect speaking.** Doctrine half = RD's §VII.F read; SURFACE half = Phase-22 scoping (one page, one voice — the composition class rendering daily) |
| **September monthly read #3** | RD | First trading week of September. Inputs converged on schedule (CADL corrected). **RD's §5 carries the clock-domain caution: no cross-domain window comparison without normalizing (D37)** |

## #4 — PHASE-22 SCOPING QUEUE (CHARC to sequence when commissioned)

0. **22-A entry-path order↔mandate binding — the opening arc, now carrying RD's trade-25 ruling as its governing input.** The tri-case acceptance test (AMN refuses / OII labels / VSTS nothing, from the record alone) is fully specified by live data; the citation-graph extension (fire candidate + latch validity row) is in scope; the last-word guard's bucket path stays untouched for unlatched trades. **Trade 25 ruled: labels FROM THE FIRE (H1); keys stay EMPTY pending 22-A** (honest NULL over silent wrong); if it closes before 22-A lands, the September read carries it as a NAMED pending-label row. **The bound's second clause (RD): a latch dies at its own INVALIDATION (rung 4) or above — never of bucket drift** (rung 5 report-only). AMN = negative control, OII = drift-is-not-death positive control, CADL = clean-trigger positive control.
1. **Demand A** — `unintended_execution` third `entry_intent` value (name operator-concurred; §3 pass at [`demand-a-entry-intent-charc-section3-pass.md`](demand-a-entry-intent-charc-section3-pass.md); RD's two-tier admission ENDORSED with immutability-via-audit-trail; the migration is a 57-column/13-CHECK `trades` REBUILD — D30 class). §VII.F ratification of specific amended text still required.
2. **Demand B** — annotation surface (RD's; his rows PERMANENTLY INADMISSIBLE as tier-2 evidence — the guard all three demands carry).
3. **Abandonment intent** (VSTS class, ratified) — records abandonment WITHOUT requiring the order; recorded-at vs happened-at honest; inadmissible as evidence.
4. **`derive_trade_origin` root-cause fix** — reads "latest complete run" not the run the operator acted on; recurs every time a ticker drops off-screen between recommendation and fill (CADL's actual cause; gotcha #30's family one level up). Entry-path change.
5. **Trail-contradiction SURFACE half** — advisory gates on the same eligibility the tile renders; which-MA becomes ONE derivation.
6. **The two by-class sweeps** — crash-from-broker-permitted-input (3 instances: D34, BANK-1, BANK-3) · surface-presenting-the-unactionable (3 instances: fixed advisory, BANK-2/D35, BANK-4). Fix = ONE sweep per class (which handler tuples exist / which surfaces present unactionable state), never per-site patches.
7. **D37+D38 as ONE sweep** — clock domains (naive LOCAL vs naive UTC) + lexical TEXT-timestamp predicates. **Scoping input from the orchestrator's READ manifest (08-13): 10 live-code `Pacific/Honolulu` spellings (incl. `tool_health.py` ×4, not ×1) + 7 PROSE occurrences incl. `web/routes/patterns.py:82` — a FOURTH module.** The prose is #31-class: a sweep moving the literal behind the constant leaves seven docstrings describing a spelling that no longer exists. A constant now exists (`PIPELINE_LOCAL_TIMEZONE`, `dates.py:32`).
8. **Wave leftovers** — item 6 (D32 backups; composition watch with item 5's backup-destination default) · item 7 (D9 ambient-state sweep).
9. **Model-side-rule-without-its-SQL-twin** — 4 instances in one loop (Demand-C rounds 2/4/5/6); reads as #11 applied one level below where it is written. Candidate gotcha amendment at Phase-22, not a code arc.

## #5 — STANDING FACTS THAT ARE MISREAD IF ABBREVIATED

- **Open positions (as-of 2026-08-13 EOD, predicate `current_size > 0`): ORKA (1 sh, `by_design`) · CADL (18 sh, `standard`, cohort keys CORRECTED).** LQDA closed 08-13 (stop 84.70 vs 91.81 entry). Four written inventories went stale in ~one day earlier this week — **state a position set WITH its as-of and predicate, and re-derive before relying.**
- **Trade 20 (AMN): closed ≈ −0.996R, `entry_intent` NULL DELIBERATELY** pending Demand A. Its row's own words: a stale A+ latch order fired after the condition disappeared, during latch-removal work — an entry NOBODY DECIDED TO MAKE. NOT discretionary; `trade_origin` alone misleads. RD's doctrine bound is ENCODED operationally in Demand C's last-word guard (AMN = negative control: skip supersedes → refused; CADL = positive control).
- **H1 is 2/20 with 1 in flight.** The 20 is `hypothesis_registry.target_sample_size`, static; `current_sample` counts CLOSED trades. Do not recompute the read's arithmetic from intuition — both directors got it wrong once each.
- **`pre_trade_locked_at` is NOT EVIDENCE** (synthetic `entry_date+T16:00:00`, 20/20).
- **The Demand-C plan is NOT converged-clean** (rounds 10–11 unreviewed; terminated on a disposition rule). Its executing arc's A-loop + the orchestrator's B covered it; never cite the plan as converged. **The plan lives ON MAIN at `28792ada`** — rescued at cleanup from an unmerged branch an hour before teardown would have destroyed the governing spec of a live migration. **Standing rule adopted from it: an arc's PLAN must be on `main` before its branch is deletable.**
- **Review transcripts** (r1–r6 + cold audit, 9.4 MB) preserved at `~/swing-data/review-transcripts/demand-c/` — an orchestrator proposal, reversible, not yet a convention.

## #6 — REGISTER QUICK-STATE (full table: charter §4)

- **CLOSED:** D29 (four-site cohort-intent fix `c49fc45d`, live-verified 3/20→2/20 — the register entry records the close; the orchestrator's 08-13 staleness correction targeted `orchestrator-context.md`, not the register) · D30 · D31 BOTH SIDES (entry `correct-entry-date` + exit twin merged; live ledger corrected) · D22–D25.
- **OPEN, high-value:** D27 dual `data_asof_date` (now with teeth: the wrong anchor is MONOTONICALLY MORE PERMISSIVE, 138/138 live runs, and Demand C encodes the right anchor) · D32 · D33 (trigger: equity ≥ $7,500) · D34 + D35 (three-instance classes, sweep-scoped) · **D36** dynamic-SQL-writer blindness (now cited in the recipe's service-prevention rule) · **D37** two clock domains (RD's measurement caution attached; sweep scoped with D38) · **D38** lexical TEXT-timestamp predicates (closed inside Demand C's envelope via its §3.0 rule + the every-competitor-row validation; repo-wide sweep open).
- **WATCH:** D1 · D5 · D8 · D12 · D15 · D16 · D17 · D26 · D28.

## #7 — BEHAVIORAL (full text: charter §5; cross-role model: `harness-architecture.md`)

- **§5.1 director = PEER — disagree plainly, unprefaced, at a LOW threshold; own errors in the artifact.**
- **Premise-sourcing: five owners + a ruling is not a source + THE TEMPORAL CLAUSE** (a quiet instrument only evidences the fix if it ran against the fixed code; sequence position is provenance).
- **Report every count/absence WITH THE METHOD that produced it** — a token grep bounds from below; only a READ establishes a manifest; a column-name grep cannot see a dynamic-SQL writer (D36).
- **An operator-concurred item is OWED, not queued** — by CHARC, since a date. Window entry criterion: a rule changing what counts as DONE waits; a rule that only makes someone STOP AND ASK lands immediately.
- **A cleanup pass RE-DERIVES; it does not verify a list.** **A check you do not gate on is not a check.** **Supersession by REPLACEMENT.**
- **Comms:** subjects ≤80 chars ENFORCED IN CODE (a subject NAMES the message; the body CARRIES it) · `--body-file` same-step, backtick/dollar-free · one supersession per message, said in the subject · `role_mail` from MAIN repo dir · **a repeated `--to` silently delivers only to the LAST recipient — post per-recipient and VERIFY the `posted ->` lines** · re-read before concluding an inbox empty · **do not truncate your own drain (`tee | head` closed the pipe mid-batch twice — write to file, then read the file).**
- **§2.7 directors never run copowers cycles. §5.8 pathspec commits; ZERO `Co-Authored-By` EVER.**
- **QA on disk, never from the self-report; operator live-witness is the binding net; verify a gate is REACHABLE before spending the operator on it.**
- **coa-chess is its OWN repo — do NOT drive or contaminate.** Cross-references: [`review-process-reference.md`](review-process-reference.md) (theirs) · `coa-chess/docs/review-process-reference-swing.md` (ours).
