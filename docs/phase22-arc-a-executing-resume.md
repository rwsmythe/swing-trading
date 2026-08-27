# 22-A EXECUTING — resume record (paused 2026-08-27, weekly token budget)

**The arc is PAUSED at a clean boundary, not abandoned.** Nothing is half-written; the branch is coherent and the suite is green. This file exists so a cold resumer needs no conversation history.

## STATE

- **Branch `22-a-exec`**, worktree `.worktrees/22-a-exec`, base `a18a3771`, **HEAD `d74f378e`**, **66 commits**, tree clean, **zero trailer-bearing commits**.
- **Suite: 11,831 passed / 12 skipped / 0 failed.** `ruff check swing/` clean.
- **146 of 146 plan cases implemented**, each traced to a **PASSING pytest node id** (219 distinct ids, 303 passed) — verified by RUNNING, never by the static closure meter, which counts a case implemented the moment a file mentions its id. **`DEFERRED_CASES` is EMPTY** and has been for ten consecutive dispatches.
- **Live DB UNTOUCHED at `schema_version = 36`; `0037` is UNAPPLIED.** That is what keeps the amendment-before-merge ruling alive — the migration remains editable in place, and that fact must be **re-verified at the merge gate** before anything lands.
- **The plan is on `main`**: `docs/superpowers/plans/2026-08-24-phase22-arc-a-entry-path-order-mandate-binding.md`.

## ARTIFACTS PRESERVED OUTSIDE THE REPO

The review ledger and all round transcripts are **gitignored** and would die with the worktree. Copied to **`~/swing-data/review-transcripts/22-a-exec/`** (22 MB): `.copowers-findings.md` (**1,993 lines** — twelve counted rounds, every finding with its disposition), `.codex-review-r1..r12`, the prompts, and `.codex-probes/` (the call-graph walk and the case-to-node-id trace).

## WHAT REMAINS — five findings, and leg 11's scope

**Leg 11 was dispatched and stopped before doing any work. Its scope was ONE IDEA: make the arc's own instruments un-foolable.** Round 12's three open non-residual findings are one class in three costumes:

1. **`R12-02` / `R12-03` — the `AL-3` roster declares itself EXACT and is INCOMPLETE.** Two trigger clauses are service-validated in exactly AL-3's sense and named nowhere: the **anchoring-fill clause** (`0037:869-875`) proves the cited fill is *an* entry fill of the trade on the frozen session but never that it is **the authoritative one** (`resolve_authoritative_entry_fill`, `cohort_provenance_correction.py:593`); and **`probe_guards.fill_session_is_session`** (`0037:1252`), whose verdict is read as `pass` with no exchange-calendar membership proved.
2. **`R12-04`** — the whole-tree SQL closure walk matches **per LINE**, so a two-line spelling passes it.
3. **`R12-05`** — `_TYPE_ROSTER` matches only the **exact two-type tuple**.
4. **`R12-01`** — a residual of the write-path class; see the ledger entry.

**THE OPERATOR RULED THE FIX (2026-08-27): make `AL-3` CLOSURE-CHECKED rather than hand-maintained**, and the same for the two evadable walks — **reusing the walk `SS-12` already built** rather than authoring a fourth instrument. The implementer's own sentence at `SS-12` is the instruction: *"the roster is not the fix; the closure check is."*

**His ground for choosing this over shipping, which a resumer should not re-litigate:** merging a roster that says "exact" while we know it is not would ship **a false claim in the document whose entire job is to state what is true** — the precise defect this arc spent twelve rounds eliminating everywhere else, including inside its own instruments.

**Target shape:** every trigger clause reading a service-supplied value is **either SQL-bound or named in AL-3**, asserted mechanically **in both directions**, so a clause added later without a roster entry fails loudly instead of silently widening or narrowing a declared limitation. Each walk ships a **discriminator that fails against the evasion it now catches** (a two-line spelling; a reordered tuple) — an instrument whose evasion case is untested is the same defect one level down.

**Why this roster specifically:** it has been wrong **three times, in both directions**. `R9-05` BROADENED it (the migration records this against itself at `0037:1279-1283` — *"silently broadened a declared limitation roster to cover something nobody had ruled on"*); `SS-12` was the same shape on the barrier roster, one member short; `R12-02/03` are AL-3 short by two.

## THEN: ROUND 13, AND THE GATES AFTER IT

Twelve rounds are counted; **on the FULL diff the loop has run ten (rounds 3–12) and none was clean.** Binding convergence is a **clean verdict on the full diff** `a18a3771..HEAD` — per-leg rounds over a growing subset do not sum to a reviewed whole (orchestrator-ruled, both directors endorsed).

**Transport:** the full `-U8` diff is **1,207,126 chars** against Codex's **1,048,576** cap. Use the recipe §3 **`$HOME` staging fallback** — stage the diff, the `--stat` and a working-tree copy in WSL `$HOME`, run codex from there, prompt only on stdin. **Do NOT improvise a split** (CHARC-ruled, with that measurement as the reason). A capped delivery shows **banner + echoed input + no footer** and **is NOT a round.**

After a clean round 13: **orchestrator QA against disk → the orchestrator's own second eye (reviewer B — NOT the implementer's) → the merge gate, where both directors are waiting → then S9 step 0, a BLOCKING full live pipeline run, then the operator-witnessed step-by-step application.**

**This arc corrects NEITHER trade 24 NOR trade 25** — both carry as named pending rows until 22-A2.

## STANDING RULINGS A RESUMER MUST NOT RE-DERIVE

- **SQL verifies a FACT; it must never re-derive a JUDGMENT across an engine boundary** — the twin mirrors the authority by consuming its OUTPUT, not by reimplementing its reasoning. (The persist-canonical reshape; **verified: zero SQL reads into a fill envelope remain.**)
- **`R5-02`'s epoch-boundary comparison SURVIVES** — a stored fire position against a stored boundary is a FACT comparison. What died is parsing, normalization, coercion.
- **Cohort bookkeeping never blocks a money-bearing entry** (RD, ruled twice).
- **A commit message is a CLAIM, and staging a file is not changing it** — read the DIFF of the commit you just made, not the exit code of the script that made it (CHARC, against his own work).
- **`-1` PK contract:** the clause reads `(NEW.pk != -1 AND pk = NEW.pk)`; NEW tables carry `CHECK (pk > 0)`; every site ships the three-direction set — ordinary append SUCCEEDS, conflicting REPLACE ABORTS, explicit conflicting id ABORTS.
- **A refusal-only test set cannot establish that a guard can EVER accept** — prove a truthful payload accepts, then vary one field out of that baseline.
- **A trigger whose `WHEN` can evaluate to NULL does not fire — it fails open, silently.**
