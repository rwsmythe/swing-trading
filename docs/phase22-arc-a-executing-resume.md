# 22-A EXECUTING — resume record (rewritten 2026-08-31 at a generational handoff)

**The arc is at a clean boundary and is NOT mergeable yet.** Nothing is half-written; branch coherent, suite green. This file is written so a cold resumer needs no conversation history. **It supersedes the 2026-08-27 version, which was stale on state.**

## STATE

- **Branch `22-a-exec`**, worktree `.worktrees/22-a-exec`, base `a18a3771`, **HEAD `403ea9ff`**, **81 commits**, tree clean, **zero trailer-bearing commits** (filtered on the trailer KEY).
- **Suite: 11,937 passed / 13 skipped / 0 failed.** `ruff check swing/` clean.
- **Live DB UNTOUCHED at `schema_version = 36`; migration `0037` is UNAPPLIED.** That fact is what keeps the amendment-before-merge ruling alive — the migration is still editable in place. **Re-verify it at the merge gate.**
- `main` is at `081c7de4`, **44 commits ahead of origin, unpushed**.
- **Fifteen counted review rounds; thirteen of them full-diff; NONE clean. 102 findings, zero reopened, zero reverted, zero dismissed.** The loop never misbehaved.

## ⚠ A CLAIM THIS DOCUMENT PREVIOUSLY MADE IS FALSE

Earlier versions — and every status report the prior orchestrator gave — said **"146 of 146 cases implemented, each traced to a passing node id."** **That figure is NAME COVERAGE, NOT SEMANTIC IMPLEMENTATION.** The closure gate binds a case id because a test *function is named* `..._case_N`; it cannot see whether the test measures what the case specifies.

**Demonstrated:** the plan's **S3.4 specifies case 4 as "RHI — place-intent WITHOUT a validity row → falls through."** The test named `..._case_4` builds **a broker-ACCEPTED order and asserts ADMISSION** — the opposite. Case `4b` asserts only that the lookup returns empty, never the end-to-end persisted outcome S3.4 requires.

**Do not restate 146/146 until case 4 is fixed AND the other 145 bindings are re-audited for the same shape.** A gate that can bind a name to a contradicting test has probably done it more than once.

## REVIEWER B RAN FOR THE FIRST TIME (2026-08-31) — and it is the reason the arc is not mergeable

Fifteen rounds of Reviewer A had run; **B — the orchestrator's own gate, required by CHARC charter §2.9 — had never run.** It ran CLAIMS_FIRST (the artifact's own headline promises measured end-to-end before any code-level lens) and returned `NEW_CRITICAL_MAJOR_FOUND`.

**Its output is preserved at `~/swing-data/review-transcripts/22-a-exec/REVIEWER-B-cold-audit-2026-08-31.txt`** (25,137 lines) with its prompt beside it. **It was written to a session scratchpad and would have been lost; it is the only B pass this arc has had.**

**Of five headline claims: one HELD, four failed — but TWO of those failures were the orchestrator's imprecise claim WORDING, not the code.** Claim 1 was stated without the post-barrier qualifier the design always had (B: *"for an eligible post-barrier link, the path itself is clean"*). Claim 4 said "structurally immutable" where `0037` **declares that exact residual itself** (B: *"the declared residual is accurate"*). **B's own summary is the fair one: the L-series limitations accurately describe their instruments; the headline claims are broader than those limitations permit.**

## THE OPEN LIST

**MUST FIX before merge:**

1. **A money-bearing web entry can still be blocked by cohort metadata** (B, P2). `swing/web/routes/trades.py:1106` returns HTTP 400 **before `record_entry`** when a submitted envelope carries a numeric/blank/non-string order id — and the arc's own test at `tests/web/test_routes/test_22a_task10_entry_route_ext2.py:352` *proves* no trade is written. **This is RD's governing principle — cohort bookkeeping never blocks a money-bearing entry — for the FOURTH time in this arc.**

   **STATUS CORRECTED 2026-09-01 (RD, verified independently at the code): the defect is ARC-INTRODUCED, NOT SHIPPED.** This document previously said "the first time shipped" and that was **false**. `SCHWAB_ORDER_ID_ENVELOPE_KEY` has **ZERO** occurrences in `swing/` on `main`; the rung was introduced by **`bc85c5e1`** ("Task 10 -- EXT-2"), which is **not an ancestor of main**. It has never been reachable in production. The two statuses route to opposite places — "shipped" sends someone to a production hotfix for a defect that has never existed there. Under RD's introduced-versus-banked boundary, introduced means **fix in the arc, never cite**: the remedy is unchanged and the urgency is not.

   **RULED (RD, 2026-09-01) — the refusal MOVES, it does not disappear.** The detection is right; the DISPOSITION is the error. **A malformed `schwab_order_id` REFUSES THE LATCH BINDING, never the ENTRY.** The trade is recorded; the cohort keys land honest-unset (`manual_off_pipeline` + NULL + NULL); a warning names the malformed envelope. Same shape as R3-13 and 37c. **Discriminating case:** a submitted envelope with a numeric `schwab_order_id`, ticker in today's decision table -> the trade IS written, keys honest-unset, warning names the malformation. A 400 fails it; admitting and stamping `pipeline_aplus` fails it too.

   **THE CLASS, NAMED (RD):** four instances in ONE arc -- `NotSessionError`, 37c, `R11-02`'s uncontained `record_identity`, now this. **Every guard added to protect the cohort keys has defaulted to blocking the entry. That is not four slips; it is a default that must be inverted at the seam.** Standing requirement: every remaining and future cohort-provenance guard states, AT ITS SITE, which of ENTRY or LABEL it refuses -- and the answer is always LABEL.
2. **Case 4's test measures the opposite of its specification** (B, P2; §above). Fix it, then re-audit all 146 bindings. **The re-audit is DISPATCHED FIRST, as its own read-only leg** (`docs/22-a-case-binding-audit-brief.md`) -- it sizes the fix leg, and discovering more contradicting bindings after a fix leg converges buys a sixteenth round.
3. **`22A-R15-03`** (A, major) — `contextlib.suppress(sqlite3.Error)` around `conn.rollback()` in `cohort_provenance_correction.py:2185-2192`: when savepoint creation *and* rollback both fail, the owned deferred transaction leaks. **It contradicts `AL-15`, written four commits earlier in the same leg.** ~6 lines plus a both-verbs-fail proxy row.
4. Cheap: **`except Exception` → `BaseException`** in the correction rollback (B, P3, `cohort_provenance_correction.py:2463`).
5. **`22A-R15-01`** (A, major, PRODUCTION) -- require the operand key set at the `0037` insert trigger and BIND each value to the cited fill. **Fix NOW because `0037` is UNAPPLIED and the trigger is still editable in place**; after application the same fix costs a migration against the live DB. Insert-time rule, so legacy four-key rows are unaffected.
6. **`22A-R15-02`** (A, major, PRODUCTION) -- **narrow fix only:** reject a non-finite `actual_limit_price` at the AUTHORIZATION boundary so the operator gets a typed refusal instead of a raw DB error. Live incidence measured **ZERO**. **The CLASS routes to CHARC** (below) -- this is the FIFTH authorize-then-abort instance in this arc and is not patched a sixth time at one site.
7. **`22A-R15-05`** (A, minor, INSTRUMENT) -- `SEEDING_INSERT` matches `INSERT [OR ...] INTO` only, so a bare `REPLACE INTO` seeds the table with both the empty-ships pin and its splice discriminator GREEN. Verified BY EXECUTION. The migration's re-attestation carve-out rests on that emptiness. **This is CLAUDE.md's own `REPLACE` gotcha landing inside the arc's own instrument for the second time.**
8. **`22A-R15-06` / `22A-R15-07`** (A, minor, INSTRUMENT) -- **complete the DECLARATIONS, do not widen the walks.** Add the undeclared spellings to AL-12's rows (parenthesised `json_extract`, `import json as j`) and AL-14's (case-sensitivity, `main.`-qualified references). No production occurrence for either; the routed class fix (token-aware scanning) is unchanged. This is the standing declare-versus-widen ruling applied.
9. **CHARC's two comment sentences** at `0037:1507` and `:1565` recording WHY the ordering is a FACT -- citing the `0033:704-712` format constraint **by line** -- so the next reader does not read them as violations and "fix" them into the hole. Zero logic change.

**ROUTED ITEM: RULED AND CLOSED (CHARC, 2026-09-01). It split three ways, not one.**
- **`0037:1729` (freeze-tier): COMPLIANT -- DO NOT TOUCH.** It IS the R5-02 ruling correctly encoded. It binds `input` to the stored `freeze_tier` AND compares a stored fire position against a stored boundary row -- both operands in SQL's domain, which CHARC ruled explicitly SURVIVES as a FACT comparison. A "fix" here reintroduces the exact hole R5-02 closed: a forged link carrying the live tier for a pre-barrier candidate.
- **`0037:1507` and `:1565`: THEY STAY.** `recorded_ts` is format-constrained by `0033:704-712` (length exactly 19, GLOB-pinned canonical shape, `datetime()` non-null, both date halves, component ranges) and all five live rows conform. **A fixed-width canonical ISO string orders lexically exactly as it orders chronologically**, and Python's authority `_order_key` (`swing/latches/classification.py:330` = `(recorded_ts, intent_id or 0)`) compares the same strings by the same tuple. The engines cannot disagree because the schema removed the degree of freedom. **The rule's boundary, stated:** it targets INTERPRETATION (parsing, normalization, coercion, semantic predicates) where the engines hold independent opinions -- an ordering over stored keys is a QUERY ABOUT THE TABLE, provided the key carries no interpretive freedom. Where the key is an UNCONSTRAINED TEXT timestamp the query IS an interpretation wearing a query's clothes (D38) and the rule binds. Second reason, kept if the first ever fails: their divergence direction is a wrong REFUSAL of a truthful row (cheap, legible, adjudicable) while removal loses a real defense against a forger citing a genuine-but-not-GOVERNING row.
- `:1752-1756`'s residual declaration is **correct as written** (it does not compare trigger bodies -- that is R3-02, unfixed-not-reopened).

**ROUTE TO CHARC (NEW, orchestrator-raised):** the **authorize-then-abort CLASS** -- five instances in this arc. `R15-02` is patched narrowly at its site; the class is architectural and belongs to CHARC.

**DECLARED AND ACCURATE — do not "fix":** the `-1` REPLACE residual (B confirmed the declaration is correct). **`22A-R15-04`** joins it -- the reviewer had to LOWER `SQLITE_LIMIT_LENGTH` to reproduce it; production envelopes are ~200 bytes against a 1e9 default, and the direction is a wrong REFUSAL. Its fix changes the freeze FORMAT, which must not be touched at the merge boundary of an arc already carrying residuals-of-residuals.

**ROUND 15's SEVEN — DISPOSITIONED 2026-09-01 (operator concurred with the orchestrator's split).** FIX: `R15-01`, `R15-03`, `R15-05`. NARROW-FIX + ROUTE THE CLASS: `R15-02`. DECLARE: `R15-04`. COMPLETE THE DECLARATION: `R15-06`, `R15-07`. Nothing is deferred that carries a live incidence above zero.

**THE COMPOSITION IS THE FACT THE MERGE TURNS ON.** Round 14 was seven-of-eight INSTRUMENT; round 15 was **four-of-seven PRODUCTION, and three of those four are residuals of round 14's own fixes** -- the Expansion-#13 cascade signature for the second consecutive round. The dispatch's stop rule was grounded on the round-14 composition continuing; it did not. This is round 15 of a chain the project's own lesson calls healthy at 4-9, and the composition got WORSE rather than tapering.

## ARTIFACTS

`~/swing-data/review-transcripts/22-a-exec/` — the ledger `.copowers-findings.md` (**2,728 lines, fifteen rounds**), `.codex-review-r1..r15`, prompts, probes, **and reviewer B's audit**. All gitignored in the worktree and would die with it. The worktree copy is the working one.

## STANDING RULINGS — INHERIT, DO NOT RE-DERIVE

- **SQL verifies a FACT; it must never re-derive a JUDGMENT across an engine boundary** — the twin mirrors the authority by consuming its OUTPUT, not reimplementing its reasoning. (`R5-02`'s epoch-boundary comparison SURVIVES: stored position vs stored boundary is a fact.)
- **Cohort bookkeeping never blocks a money-bearing entry** (RD, ruled twice; violated four times).
- **A commit message is a CLAIM; staging a file is not changing it** — read the DIFF of the commit you just made (CHARC, against his own work).
- **`-1` PK contract:** `(NEW.pk != -1 AND pk = NEW.pk)`; NEW tables carry `CHECK (pk > 0)`; every site ships the three-direction set (ordinary append SUCCEEDS · conflicting REPLACE ABORTS · explicit conflicting id ABORTS).
- **A refusal-only test set cannot establish that a guard can EVER accept.**
- **A trigger whose `WHEN` can evaluate to NULL does not fire — it fails open, silently.**
- **Do not claim exact when you are not.** A heuristic declared with its blindness named is honest; one widened and called closed is not. Widening an instrument along the reported axis answers the EXAMPLE, not the CLASS.

## TRANSPORT AND HARNESS HAZARDS (all measured on this arc)

- Full diff **1,382,975 chars** vs Codex's **1,048,576** cap → use recipe §3's **`$HOME` staging fallback**; never improvise a split. A capped delivery shows banner + echoed input + **no footer** and is NOT a round.
- **FIVE distinct exit-0-and-nothing-happened mechanisms:** the dead npm shim · a missing redirect target · CRLF line endings · MSYS path-mangling · **passing WSL a Windows `C:/...` path instead of `/mnt/c/...`** (the orchestrator did this on the first B launch — it printed "No such file or directory" and exited 0; caught only by checking the redirect target). **Always verify the redirect target is non-empty BEFORE reading it.**
- The harness **collapses `\\` → `\` inside a bash heredoc, including a quoted `<<'EOF'`**. Exit codes stay 0; corruption surfaces only on execution. Use Edit/Write for content with backslashes; `printf` + `file` for shell scripts.
- Poll the **exit file**, never the transcript tail; use the anti-self-match `pgrep -af codex | grep -v 'pgrep\|grep'`.

## WHAT A RESUMER DOES NEXT

**The sequence is SET (operator, 2026-09-01) and the ordering is load-bearing:**

1. **THE 146-BINDING SEMANTIC RE-AUDIT, FIRST, as its own read-only dispatch** -- `docs/22-a-case-binding-audit-brief.md`, cell `implementer-opus-xhigh`, worktree `.worktrees/22-a-audit` branched off `22-a-exec`. **It sizes the fix leg.** If it surfaces twelve more contradicting bindings, those are test fixes belonging in the SAME leg as everything else; finding that out after a fix leg converges buys a sixteenth round. Its method must be SEMANTIC and its result reported WITH that method -- both directors said so, and **neither will restate the 146 number before it lands.**
2. **ONE fix leg, not split** -- items 1 through 9 above plus every contradicting binding the audit found. Do not split the fixes; splitting them re-creates the cross-arc composition class (§5.1: no review rung reviews the COMPOSITION of two arcs).
3. **One confirming round** of Reviewer A.
4. **REVIEWER B, A SECOND TIME.** **This is not optional and it is not satisfied by the existing transcript.** CHARC's merge gate now REQUIRES the B transcript -- its path, its five mechanical assertions, and its verdict -- NAMED IN THE MERGE REQUEST; no transcript, no clearance. The only B pass that exists audits `403ea9ff` and its verdict is **`NEW_CRITICAL_MAJOR_FOUND`**. A stale-tree transcript satisfies the LETTER of that gate and not its purpose: you cannot merge citing a transcript that says that. B runs again on the post-fix tree.
5. **Orchestrator QA** -> **the merge gate** (both directors waiting) -> **S9 step 0, a BLOCKING full live pipeline run** -> the operator-witnessed step-by-step application.

**Re-verify at the merge gate that the live DB is still at `schema_version = 36` and `0037` is UNAPPLIED.** **This arc corrects NEITHER trade 24 NOR trade 25**; both carry as named pending rows into RD's September read.
