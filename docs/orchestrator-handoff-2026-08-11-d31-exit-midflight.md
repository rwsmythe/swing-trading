# Orchestrator handoff — 2026-08-11 — the boundary wave, D31-exit mid-flight

**From:** the generation that ran items 3b→5, the render fix, the sweep, and D31-exit. Handing off on context exhaustion at a clean boundary.
**Bootstrap:** `scripts/orchestrator_bootstrap.md` → `docs/orchestrator-context.md` → this file.
**Main HEAD `80c346c5`.** Schema **v35** (live DB migrated). Main is **8 ahead of origin, UNPUSHED** (director docs commits).

**Every fact below was re-derived from disk or the live DB at handoff time, not recalled.** That discipline is the reason this file exists: the H1 amendment sat undone five days because a handoff enumerated obligations from memory, and it recurred twice more this wave.

---

## 1. YOUR FIRST ACTION — **the arc RETURNED after this file was written. Read this section, not the one below it.**

**UPDATE, same session, minutes after the above was committed: the implementer completed every gate and returned.** The §1.OLD text below is preserved only because a successor may find the worktree mid-something; **it is superseded.**

**State now: branch `d31-exit` @ `7bf581ff`, 27 commits, clean, review scratch RESTORED to the worktree root (50 files, `.copowers-findings.md` 40,214 bytes, rounds 1-23).** My two comment edits were verified comment-only by the implementer (identical AST on the VM file; the template diff entirely inside one Jinja comment block) and committed as `7bf581ff` with attribution. **Converged at R23** — `NO_NEW_CRITICAL_MAJOR`, all four assertions, on the tree that ships including my edits.

**WHAT IS NOT DONE, and it is yours:**

1. **ORCHESTRATOR QA ON DISK. I did none of it.** The implementer reports suite **10800 / 7 / 0** off the final head — **that number is unverified by me. Re-run it; do not carry it forward.**
2. **THE B REVIEW. Run it yourself** — §2. This is the gate that caught an introduced-and-blessed regression on this very arc, twice, and it has NOT been run against `7bf581ff`.
3. RD's merge gate, then merge with byte-identity proof, then suite on the merged head.

**Two residuals the implementer cited for your call**, both the load-bearing-comment class this arc met repeatedly:
- `exit_auto_fill.py:1371` and `routes/trades.py:2473` still describe future-render dedupe as falling back to the `(date, price, quantity)` tuple. **Since the ruling that channel neither dedupes nor excludes.** Runtime is correct; the stated risk is that the comment "could encourage reintroducing forbidden silent exclusion" — the one behaviour the ruling forbids outright. Two comment edits.
- `exit_auto_fill.py:183` and `view_models/trades.py:1020` say every anonymous row is `operator_typed`. **True of the live ledger and the ruling rests on it — but it is not the channel's definition**, which also admits imported fills and `selected_candidate_order_id`-only envelopes. A live-population fact stated where a structural invariant belongs.

**Expect one flaky test at merge and do NOT read it as a regression:** `tests/integrations/schwab/test_ladder_stress_production_path.py::test_forced_finish_lock_leaves_in_flight_row` failed once on a loaded box and passed in isolation, as a module, and on the final run. It is `busy_timeout_ms=1` plus a background lock-holder thread and `sleep(0.1)` coordination under 16 xdist workers — **load-sensitive by construction**, with zero references to anything this arc touched. The mechanism is the proof, not the re-run.

**Two things landed as the ruling predicted:** `existing_fill_value_tuples` had **no production contributor left**, so the parameter was removed outright rather than left dormant (a test now asserts the channel is *absent from the call*, not merely empty) — and **MAJOR 1 dissolved**, because the multiplicity problem was a property of a SET being asked to say "one of these two", and the set is gone.

---

## 1.OLD (SUPERSEDED) — an implementer was MID-TASK when this was written

**`.worktrees/d31-exit`, branch `d31-exit` @ `f9046921`, with TWO UNCOMMITTED comment fixes in the working tree** (`swing/web/view_models/trades.py`, `swing/web/templates/partials/trade_exit_form.html.j2`). **Those uncommitted edits are MINE, not the implementer's** — see §2.

A resumed implementer (`implementer-opus-xhigh`, agent id in the session task list) has been sent a message it has not yet acted on. It was told to:

1. **Commit my two comment fixes** (they are in its files; its commit discipline is better than a stray orchestrator commit mid-arc).
2. **Run ONE more Codex round (R23)** covering them — **because my edit changed the tree after R22's clean verdict**, and convergence attaches to the tree that ships. If R23 is clean, that is convergence; if it finds something in my wording, fix and run once more, then cite any residual rather than chasing wording.
3. **Restore the review scratch** (`.codex-*`, `.copowers-findings.md`) from the session scratchpad to the worktree root, rounds 16-23 appended. **This is non-obvious state — QA reads them there.**
4. **Full fast suite off the FINAL head** (the last full run, 10796/7/0, predates the R16-R21 fixes and mine — it is stale).
5. Trailer audit on the KEY, then the return report.

**If that agent is unreachable from your session, dispatch a fresh `implementer-opus-high` at those five steps.** The work is committed and safe; only the agent's context is at risk.

**R22 verdict, already read by me: `NO_NEW_CRITICAL_MAJOR`, ZERO findings**, all four assertions (`gpt-5.6-sol` / `high` / anchored `^ERROR` 0 / anchored `^tokens used` 1). The loop closed itself; do not open rounds hunting wording.

---

## 2. THE ONE RULE THAT CHANGED THIS SESSION — **YOU run the B review**

**Operator ruling, CHARC-canonicalized in `harness-architecture.md` §5.1.** `codex-auto-review` ("B") moves from the implementer's gate list into **the orchestrator's QA sequence**. A (the iterative `strong` loop) stays with the implementer.

**Why:** B is a single pass over a finished tree and its whole value is a *different perspective*; the author choosing its prompt, inputs and adjudication erodes exactly that. The transcript-read control catches a fabricated verdict but not a prompt quietly narrowed — the narrowed prompt IS the transcript.

**It paid for itself on first use.** The author's B found 6 majors and the arc then converged at R13 with zero findings; **my independent B on that same tree returned `NEW_CRITICAL_MAJOR_FOUND`**, including a regression the arc's own test *blessed*. A second round found two more (both pre-existing) and nothing introduced — which is the correct success shape: **a second eye stops being productive when the work is good.**

**How I ran it** (foreground; background tasks were killed three times this session, same commands succeeded in foreground):
```
wsl.exe bash -lc 'export PATH="$HOME/.local/node22/bin:$PATH"; cd <worktree> && cat <prompt> | codex exec -s read-only -c model_reasoning_effort=high --skip-git-repo-check - > <out> 2>&1'
```
Prompt at `scratchpad/orch-b-review-prompt.md` — **neutral framing on purpose** (adversarial-security wording trips a provider content filter; see §5). **Do not adopt the implementer's offered "areas worth pointing it at"** — taking the author's map is the coupling the ruling removes.

**RECIPE EDITS ARE QUEUED, NOT YET MADE.** CHARC holds them for the post-D31 window (no rule changes under an in-flight implementer): §3 reassignment, brief/return-template cleanup, and **the VERDICT-LINE anchor**. Until they land, **you must run B yourself and tell each dispatch not to.**

---

## 3. D31-EXIT — where the substance actually is

The exit half of the entry-date defect. **FIX-ONLY: no data correction, no migration** — of 21 non-entry fills only fill 40 differed, and the operator had already hand-corrected it.

**Two director rulings govern it, the second superseding the first:**

- **RD 15:03Z** — a three-state identity model.
- **RD 16:58Z SUPERSEDES his own state 2.** He queried provenance: **all 10 anonymous fills are `operator_typed`**, so their stored-date *grain* is unknowable **in principle, forever** — his state 2 was "drawn through a variable that does not exist." **The line moved from GRAIN to PROVENANCE: silent exclusion requires PROVEN identity (order id); anonymous value-tuple matches FLAG at either grain, never exclude, never offer clean.**
- **Operator closed the last open half: "Flag noise is fine."** The MAJOR-1 override is DECLINED, the provenance rule is unqualified, the `#27` count-and-surface floor is **MOOT** (no halfway house), and **MAJOR 1 leaves the cited list entirely** for the anonymous population.

This deliberately **supersedes a prior arc's shipped contract** (`test_exit_form_auto_fill.py:859`) and the newer pin (`test_exit_auto_fill.py:1625`). Both are **REWRITTEN, not deleted**, with `:1625`'s docstring recording that the behaviour it froze was ruled out 2026-08-11.

**Still cited, not fixed:** the `split("T")`-vs-`[:10]` parse (pre-existing, Phase-13 arc — but the implementer was told to fix it since the flag's accuracy now depends on it); the client-forgeable auto-fill envelope; `_normalize_trade_event_date_to_iso` accepting compact/week forms with `assert_canonical_fill_datetime` unwired (needs a `swing/data` carve-out); `test_h_critical1_...` non-discriminating.

---

## 4. THE WAVE — what is merged and what remains

**MERGED:** item 1 (D29) · item 2 (sizing-basis) · `coverage_gaps` · 3a (`declined`) · 3b (`criteria_lapsed`) · item 4 (cancel decoupling) · the trail-eligibility render fix · **item 5 (entry-date arc, schema v35, live ledger corrected)** · the three-site manifest sweep · the recipe window.

**REMAINING, in CHARC's ruled order:** **D31-exit** (in flight) → **item 6** (D32 backups retention — *composition watch: it shares the backup-destination default with item 5, so name merge-integration as a gate*) → **item 7** (D9 ambient-state sweep) → **Demands A and B** at Phase-22 scoping.

**Demands A/B are PRE-AUTHORIZED by the operator, gated on satisfactory completion of item 5 + the sweep (both now done).** Two boundaries he set, and both must survive into your generation:
- **A "go" on Demand A is NOT its ratification.** It is a governance amendment in the V2.1 §VII.F family; that family ratifies **specific amended text**, and none exists yet. The wording returns to him.
- **The third `entry_intent` value's NAME is posed to him, never chosen** — RD declined to name it ("naming is design"); the operator's own word was "non-standard."
- Demand A's migration is a **table REBUILD** copying `0031`, **not** `0027`'s cheap ADD COLUMN. Anyone scoping from `0027` under-estimates it.

---

## 5. OPEN OBLIGATIONS, each with its parent — nothing here lives only in a head

| obligation | parent | owner |
|---|---|---|
| **96/97/98 disposition on trade 19** — 3 still open | **RD's forward-test ruling**: the next nightly reconciliation run DECIDES. No fifth emission → close all three `journal_corrected`, **each with a reason describing ITS OWN row** (97/98 say "ambiguous match", not 95's zero-delta). A fifth → they are LIVE, the fix did not take | **RD owns the watch** and posts either way |
| **Wave-close warning-cleanup pass** | `docs/phase21-boundary-paydown-commissioning-brief.md` **§8.5** | orchestrator, after item 5 + sweep (both done) |
| Recipe edits (B reassignment, verdict anchor) | CHARC, post-D31 window | CHARC |
| Exit-side D31 | in flight | this arc |

**Nothing is operator-pending.** Every decision he owed has been given.

---

## 6. LIVE TRADING STATE — re-read at handoff, and it MOVED

**THREE open positions now, not one:**

| trade | ticker | size | `entry_intent` |
|---|---|---|---|
| 20 | AMN | 5 | **NULL — DELIBERATELY**, per operator ruling, until Demand A supplies a truthful third value |
| 21 | LQDA | 2 | `hypothesis_test_by_design` |
| 22 | ORKA | 1 | `hypothesis_test_by_design` |

**LQDA and ORKA were resting orders that matched no latch; they have since FILLED.** That is new since the item-4 witness and it is exactly the population RD's Phase-22 latch-on-acceptance demand exists for.

**Trade 20's NULL is a DECISION, not an omission.** Record it that way wherever it comes up: none of the three available values is true for it, `standard` would contaminate the H1 cohort on a 2/20 denominator, and `hypothesis_test_by_design` would be false. **The realistic failure is someone "helpfully" setting it to `standard`.**

Trade 19 (FTRE) entry_date is **2026-07-31** (corrected, witnessed). Discrepancy 95 is `journal_corrected`. `latch_order_intents` holds 3 rows — the ledger's first ever.

---

## 7. WHAT THIS GENERATION LEARNED — the parts that cost something

- **A check you do not gate on is not a check.** I wrote a content-equality guard before a destructive delete, printed DIFFERS, and the delete ran anyway because it was a separate line. The guard was *also* wrong (LF vs CRLF). Safe by luck, not by the check.
- **A verification tool is an artifact like any other.** Two of my self-checks were wrong while the code was fine — an AST comparison and a stray-comms detector that cried wolf on 18 tracked docs. "My checker says so" needs the same sourcing as "my grep says so", and the direct reading is often cheaper and stronger.
- **Report every count with the method that produced it.** Six counts in this wave were short until someone stopped matching and started reading. I broke this rule four hours after committing it to the recipe: "zero consumers" came from a `head -12` cap read as a total, and a second capped grep corroborated it.
- **Cite the content search, never a bare SHA, across a rebase.** I cited a commit my own rebase had destroyed, in two messages warning about stale artifacts.
- **Merge-then-migrate is forced for any migration-bearing arc.** `db.py` refuses a DB newer than the code, so witness-before-merge is structurally impossible. RD had this right on 3b and I second-guessed it.
- **My last act as this generation was the same class:** the comment I wrote went stale hours later when a director ruling changed underneath it, and I did not revisit it. Discharged-deferral, authored by the person cataloguing discharged deferrals.

**Do not read the honesty in this file as self-flagellation.** Every one of those was caught and reported in the same message that shipped clean work, which is the standard the wave runs on.
