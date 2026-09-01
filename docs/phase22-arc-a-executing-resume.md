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

1. **A money-bearing web entry can still be blocked by cohort metadata** (B, P2). `swing/web/routes/trades.py:1106` returns HTTP 400 **before `record_entry`** when a submitted envelope carries a numeric/blank/non-string order id — and the arc's own test at `tests/web/test_routes/test_22a_task10_entry_route_ext2.py:352` *proves* no trade is written. **Production-reachable** via a stale or tampered form. **This is RD's governing principle — cohort bookkeeping never blocks a money-bearing entry — for the FOURTH time in this arc, and the first time shipped.**
2. **Case 4's test measures the opposite of its specification** (B, P2; §above). Fix it, then re-audit all 146 bindings.
3. **`22A-R15-03`** (A, major) — `contextlib.suppress(sqlite3.Error)` around `conn.rollback()` in `cohort_provenance_correction.py:2185-2192`: when savepoint creation *and* rollback both fail, the owned deferred transaction leaks. **It contradicts `AL-15`, written four commits earlier in the same leg.** ~6 lines plus a both-verbs-fail proxy row.
4. Cheap: **`except Exception` → `BaseException`** in the correction rollback (B, P3, `cohort_provenance_correction.py:2463`).

**ROUTE TO CHARC:** the citation trigger still **re-derives** latest-validity-child (`0037:1507`), governing place cycle (`:1565`) and freeze-tier verdict (`:1729`) — against his own *SQL verifies a FACT, never re-derives a JUDGMENT* ruling. Raw-write-only; the migration acknowledges the gap at `:1752-1756`. His line between fact and judgment (the R5-02 epoch comparison SURVIVES as a fact comparison) is the frame.

**DECLARED AND ACCURATE — do not "fix":** the `-1` REPLACE residual (B confirmed the declaration is correct).

**ROUND 15's SEVEN** (A) are in the ledger, classified production-vs-instrument, **with no owner assigned** — assigning them is the operator's call. Measured since: `R15-02`'s live incidence is **ZERO** (0 of 5 latch intents carry a non-finite limit; the mechanism is real — `+inf` passes `CHECK (p > 0)`, `json.dumps` emits bare `Infinity`, `json_valid` rejects it).

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

Fix items 1–4, re-audit the case bindings, route the trigger question to CHARC, then **one confirming round**. Then: orchestrator QA → the merge gate (both directors waiting) → **S9 step 0, a BLOCKING full live pipeline run** → the operator-witnessed step-by-step application. **This arc corrects NEITHER trade 24 NOR trade 25**; both carry as named pending rows into RD's September read.
