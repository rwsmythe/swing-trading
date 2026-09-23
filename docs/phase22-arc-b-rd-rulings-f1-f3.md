# Phase 22 — Arc 22-B: RD rulings on the census forks F1, F2, F3 (ONE packet)

**Author:** RD (the ruling seat on all three; F1's PIN shape is CHARC's). **Date:** 2026-09-23. **Status:** RULED — one pass, per the plan-stage protocol (harness §5.1). The courier transcribes this file into the 22-B plan ledger as a block quote when the ledger exists.

**The go.** The operator ruled GO on 22-B in the RD session, 2026-09-23 (his words: *"We have 7 days before 9-30, plenty of time. Let's go for 22-B"*). Relayed to CHARC and the orchestrator by RD as courier; the authority is the operator's. RD's position on the calendar is in §0.

Every fact below was re-read on the live DB (`mode=ro`, v39) or in the code on `main @ 2c76ca2f` on 2026-09-23 — never from the brief's §1 table, which was measured at v38.

---

## §0 RD's calendar position (stated, not a ruling)

**Feasible, and the downside is bounded — that is the reason to go, not "seven days is plenty."** The code is small (one enum token, one table, one CLI command, a mirror sweep). What consumed 22-A2 was the review ladder: ~5 director packets per seat in one sitting, with pre-ruled scope. 22-B has THREE human gates in series that 22-A2 did not: the §VII.F ratification of exact text (F1, before the plan loop opens), the step-by-step witness (§5, the operator's hand), and the read-week freeze (`phase22-scope-charc.md:152`: no `trades` rebuild lands DURING the read week). With the travel pause from 10-03 the witness must land by 09-30.

**What bounds the downside:** the serial rule already forbids executing before the witness window is real; nothing reaches the live journal without the witness; a slip parks the arc at "plan on `main`, executing branch WIP-committed" until 10-21. That is a parked branch, not a half-migrated journal.

**The stop line, so it is readable and not inferred:** if Reviewer B is not clean on the finished tree by **2026-09-29 end of day HST**, the witness waits for 10-21, and the October read runs on v39 with trade 20 NULL and NAMED (as every read has carried it). No merge over the read week; no witness during the pause.

---

## §1 F1 — WHAT TEXT §VII.F RATIFIES. Ruling: **branch (a).** RD names the text; CHARC rules the pin.

**Why (a):** the two existing values ARE the training-epoch contract's vocabulary (charter §7, 2026-06-10). A third value changes what the contract can SAY. Branch (b) would leave the definition in a docstring — a value in the journal of record whose meaning lives nowhere ratified. The 0034 precedent (operator-signed exact text, original preserved, hash-pinned, independently derived) is the shape; the difference is that the amended object is DOCTRINE in a doc, not a registry row.

**Verified before ruling — H1's registry row needs NO amendment.** `cohort_intent.py` pins `H1_COHORT_CLAUSE` = *"COHORT: the 20 are STANDARD-intent trades only …"* and the predicate is `entry_intent = 'standard'` by positive allowlist. An `unintended_execution` row is not STANDARD-intent and is excluded by the existing clause with no code change. H2–H5 are epoch-contract-grounded with no intent exclusion, and the new value is not `hypothesis_test_by_design`, so it is not a designed sample of any of them either. **The value lands in NO cohort by the existing predicates.** The amendment is to the contract, not the criteria.

**The home of the text (doctrine — mine to name):** the forward intent contract today exists ONLY in `docs/research-director-context-archive.md` line 84 (the 2026-06-10 declaration). An archive is not a home (harness §2's archive discriminator). The amended contract lives in a NEW committed doc, `docs/training-epoch-intent-contract.md`, that (i) quotes the 2026-06-10 forward-intent clauses (1)–(3) VERBATIM from the archive (preserve the quote), then (ii) carries clause (4) below, dated and with the operator's ratification quoted. Charter §7 gets a dated pointer entry. `cohort_intent.py`'s docstring cites the archive today; the plan re-points it to the live doc (docstring only — no semantic change; the plan says so).

**THE AMENDED TEXT — clause (4), for the operator's ratification EXACTLY as written (edit it before ratifying, never after):**

> **(4) `unintended_execution` — an execution nobody decided to make.** A fill produced by the framework's own resting order after its mandate had died (invalidation, lapse, horizon, or the operator's decline), or any fill no entry decision produced. It is NOT `standard` (no decision was made to take the trade) and NOT `hypothesis_test_by_design` (no program fired it). It counts toward NO hypothesis cohort. It is never inferred from text; it is assigned only through the evidence-bearing surface, with the evidence tier and the cited evidence recorded on the row, under the admissibility test: evidence is admissible iff it was recorded before the outcome was known AND is immutable since, immutability verified against the audit trail. A trade already carrying `standard` or `hypothesis_test_by_design` is never relabelled to this value — that is a different evidence class with its own record. Its realized result is reported in the trade-process card's own facet as an execution datum, never as a hypothesis sample.

Clauses (1)–(3) are unchanged. The pin: CHARC rules the shape (RD's expectation from the brief: the sha256 of the ratified clause text in `0040`'s header, derived independently by a test from the committed doc; never checked at migration runtime).

**RATIFIED BY THE OPERATOR, 2026-09-23 ~17:15Z, in the RD session, his words verbatim: "clause (4) is ratified."** The text above is the ratified text, byte-for-byte as it stands at this commit; any later edit is a new amendment, not a correction. The gate before the plan loop is CLEARED; the pin (CHARC's shape) is derived from this file's clause (4) block quote.

---

## §2 F2 — THE TIER-2 ADMISSIBILITY PREDICATES. Ruling: **the brief's three predicates CONFIRMED, with FOUR sharpenings; both edges ruled.**

**The three, confirmed:** (P1) the instrument provably post-dates the entry; (P2) no correction has touched the cited fields; (P3) the record pre-dates the outcome. Each bound in SQL to its source AND checked by the service first (AUTHORIZE-THEN-ABORT: the trigger's predicate set ⊆ the service's).

**Sharpening 1 — P1 is at SESSION-DATE grain, strictly later, and the reason is named.** `trade_entry_ts` as the brief has it would come from `fills.fill_datetime`, which is synthetic (`entry_date + 'T16:00:00'` on every entry fill — trade 20's fill 41 reads `2026-08-07T16:00:00`; gotcha #30's family). It is not a clock; a datetime comparison against it would ADMIT an instrument recorded at 17:00 on the entry session over a fill whose real time nobody recorded. **Rule: tier 2 requires `date(instrument_earliest_recorded_ts) > trades.entry_date` — the instrument's first row is on a STRICTLY LATER session than the entry. Same-session is UNPROVABLE and refuses** (the three-valued discipline: unprovable is not absent). The brief's one-second discriminator pair becomes: instrument first recorded ON the entry session → REFUSE; on the NEXT session → ADMIT. Trade 20: entry 2026-08-07, earliest instrument 2026-08-08T20:01:08 (13 rows today, 0 for AMN — re-read 2026-09-23) → ADMIT.

**Sharpening 2 — P2 checks BOTH audit tables.** The admissibility test says "verified against the audit trail (`reconciliation_corrections` / `provenance_corrections`)". `provenance_corrections` writes cohort keys, not text fields, today — but the predicate is over the trail, not over today's writers. `NOT EXISTS` over both, on `(affected_table='trades', affected_row_id=trade_id, field_name IN cited)` and the 0036 table's equivalent columns (the plan reads its DDL; the brief's §1 said it moved with 0039).

**Sharpening 3 — P2's PRECONDITION is stated and the plan VERIFIES it.** "Immutable since, verified against the audit trail" is sound ONLY if every writer of the cited fields leaves an audit row. My predecessor's 2026-08-12 line "`trades.notes` has NO update path" was FALSE (restated the same week: the audited corrector `reconciliation_auto_correct.py:2309` writes any field by name). Today the only `trades` fields ever corrected are `current_stop` ×4 and `entry_date` ×1, and trade 20 has zero rows. **The plan walks every `UPDATE trades` site in `swing/` (the repo's own count was 21 at `reconciliation_auto_correct.py:190`) and asserts by test that no site writes `notes|why_now|thesis|emotional_state_pre_trade` outside the audited corrector.** If one exists, the predicate is fail-open and the cell REPORTS it as a finding — it does not add a channel (a negative is a finding, never a licence).

**Sharpening 4 — the citation must include a DESCRIPTIVE field.** At least one of `notes` / `why_now` must be cited. Reason: only free text can describe a mechanism; a tag list (`emotional_state_pre_trade` = `["distracted"]`) can corroborate an unintended execution but cannot assert one, and a rule that admits on a tag alone admits on nothing.

**Edge (i) — a trade still OPEN: ADMISSIBLE NOW, `outcome_known_at` recorded NULL.** The test dates the EVIDENCE against the outcome, and entry-time text pre-dates an outcome that does not yet exist. The curation risk runs the OTHER way: the assigner's judgment ("does this text describe an unintended execution?") is least contaminated the sooner it is made — waiting for close maximizes what the assigner knows. So assign at the first review, not at close. Two guards travel with this: the attestation row records NO P&L, MFE or MAE (running state is not evidence and must not be snapshotted into an evidence row); and `outcome_known_at` is written ONCE, at assignment — if NULL then, it stays NULL (the row is append-only; the trade's later exit is read from `fills` at replay, never back-filled into the attestation).

**Edge (ii) — `thesis` and `emotional_state_pre_trade`: IN the allowlist.** Same capture point, same immutability class, same audit trail as `notes`/`why_now`; the admissibility test does not discriminate by field, and Sharpening 4 already prevents a tag-only assignment. `pre_trade_locked_at` NEVER (a synthetic restatement — 20/20, now 28/28 by construction). Demand B annotation rows NEVER (the standing guard; they fail P3 always).

---

## §3 F3 — THE STRUCTURAL TIER'S CITATION. Ruling: **branch (a), CHARC's stake, with the DEATH-BEFORE-FILL predicate that makes the tier mean what it says.**

**(a):** where a `latch_order_mandate_links` row exists for the filled order, the attestation cites the LINK (`cited_latch_link_id`) — it is the durable order↔mandate binding 22-A built, and it names the fire whose death is the claim; where no link exists but a `latch_order_intents` row does, cite the intent row (`place`, and `validity` if present). Three-valued: link proven → cite link; no link, intent proven → cite intent; neither → tier 2 by P1 or REFUSE (the instrument existed and did not fire — not an unintended execution the record can prove).

**The predicate the citation must carry — DEATH BEFORE FILL.** A structural citation proves the framework PLACED the order. It does not, by itself, prove nobody intended the fill: a fill while the latch is LIVE is a MANDATE fill and is `standard` under clause (1). So the structural tier ADMITS only when the cited latch's terminal state is a death rung — `invalidation`, `criteria_lapsed`, `horizon`, or `declined` — with its terminal session STRICTLY BEFORE the fill's `entry_date` (the latch bound: a fill on any LATER session does not label from the fire; same-session ties go to FILL under R6, so same-session is a mandate fill and REFUSES here). A latch whose terminal is `fill` or `superseded`, or whose death session is on or after the entry date, REFUSES with the reason naming the rung and both dates.

**Precondition, stated (a ruling names what exists today):** `swing/latches/service.py` projects `declined` and `criteria_lapsed` onto the `horizon_expired` state with the REASON first-class (`:54-74`), and runs a fill pass (`:1134`). Whether the ledger, for a fill landing AFTER a death rung, preserves the death terminal (with the fill visible separately) or overwrites it with `filled` is a fact the plan READS from the resolution code, not from this ruling. If the ledger cannot express death-then-fill, that is a precondition gap: the structural tier's death-before-fill predicate becomes a follow-on with a primitive to build, and 22-B ships tier 2 plus a structural tier that REFUSES until the primitive exists (fail closed, never a weaker tier-1). Today's only instance (trade 20) is tier 2 and is unaffected either way.

**The AMN geometry is the discriminator fixture** (real breach geometry, per the tri-case-gate rule): fire 08-03, `skip` and close 30.80 below invalidation 30.85 on 08-07, fill 08-07 at 36.43. Under this ruling: a synthetic latch for that mandate with invalidation terminal 08-06 and fill 08-07 → ADMIT structural; terminal 08-07 (same session) → REFUSE; a live latch (no death rung) → REFUSE naming it as a mandate fill. Boundary twins pinned, inequality direction pinned.

---

## §4 What RD holds the plan to, beyond the brief's §4

- The §4.3 computed-cohort test is run BEFORE and AFTER trade 20's assignment on the four readers AND `swing hypothesis list`; every N unchanged; 20 named in each exclusion line with reason `unintended_execution`.
- The witness step 5 (§5) quotes the readers' numbers; RD re-reads the H-cohort counts on the live DB and states them beside the reader's, method named. No expected count is pinned in the script.
- 22-A2's acceptance cases stay green byte-unchanged (A2-09 pin) — the composition of two `trades`-adjacent rebuilds in one week is exactly the class with no rung; the merge-time composition read asks the runtime question (code × live v40) and states the exclusive-lock result before `git merge`.
- The trade-process card's per-tab N is quoted WITH the tier page's N until D61 lands (the interim over-count note carries over).

— RD, 2026-09-23
