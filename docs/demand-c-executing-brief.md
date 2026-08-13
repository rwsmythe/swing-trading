# Demand C — executing brief

**Audience:** a fresh Claude Code implementer, no prior conversation context.
**Phase:** executing. **Both director gates are PASS.** Nothing here is open for redesign.

**THE PLAN IS YOUR SPEC:** `docs/superpowers/plans/2026-08-12-demand-c-cohort-provenance-arc.md`
(2624 lines, on branch `demand-c-plan`). Read it in full before writing anything. It survived an
11-round adversarial loop — 39 findings, 5 CRITICAL, 32 MAJOR, zero reopened, zero reverts — and its
reasoning is dense on purpose.

**Worktree:** `.worktrees/demand-c-exec`, branched from current `main`. Repo-contained; never a
sibling dir, never `.claude/worktrees/`.

---

## §0 THE ONE THING TO READ FIRST

**THE PLAN IS NOT CONVERGED-CLEAN, AND YOU MUST NOT CITE IT AS SUCH.** Rounds 10 and 11's fixes are
**unreviewed** — the loop stopped on a mechanical disposition rule after round 11 found a defect
outside the cite-and-converge class, not on a clean verdict. The plan's author flagged this against
its own interest and both directors accepted it on that basis.

**Your A-loop is part of what covers that gap.** Treat §§ touched by rounds 10-11 — the rowid-reuse
drift check and the non-session-date gate — as **carrying more risk than the rest of the plan**, and
say in your return report what your review made of them.

## §1 THE DIRECTOR RULINGS — settled, encode them, do not relitigate

**RD's gate (the evidence rule is his; its encoding is his gate):**

1. **`<=`, not strict `<`, for "PRE-DATE the fill."** The anchor compares SESSION LABELS while
   admissibility test (a) is about CREATION time: a session-N record is produced by the run on the
   evening of session N−1, so its creation strictly precedes any session-N fill by construction even
   when the labels are equal. Strict `<` refuses **10 of 11** live candidate-bearing trades including
   17 and 18 — the very cohort rows the rule was derived from. **A rule that refuses its own
   derivation base is mis-encoded, not strict.** §8.2's boundary tests pin both directions: equality
   ACCEPTS, +1 day REFUSES.
2. **The last-word refusal shape ships exactly as designed.** RD ruled it is not merely conservative —
   it is his AMN doctrine bound encoded (*"a latch does not survive its own invalidation; a fill after
   that point does not label from the fire"*), with **CADL as the positive control** (no row in run
   138, so candidate 12341 remains the last word → correctable) and **AMN as the negative control**
   (a `skip` on the entry session supersedes → refused). The governing asymmetry: **a wrong refusal
   costs a legible message and a human escalation; a wrong acceptance contaminates H1 invisibly and
   permanently.**
3. **The target label is the FAITHFUL DERIVATION: `'A+ baseline (aplus); failed: TT8_rs_rank'`.** The
   clean sibling string is **NOT wanted**. Candidate 12341 carries `TT8_rs_rank='na'` and
   `_non_pass_criterion_names` counts `'na'` as non-pass, so the suffix is TRUE of the cited candidate
   — an RS-rank fallback on the fire row is a fact worth carrying. Reading the clean string off trades
   17/18 would be reading the label off SIBLING TRADES, which is the composition the evidence rule
   forbids.
4. **The cohort arithmetic is `in_flight 0→1`, NOT `2/20 → 2/21`.** `current_sample` counts CLOSED
   trades (23 is `entered`); `target_sample` is a static registry column. It becomes 3/20 only when
   CADL closes. **Compute expected values under BOTH pre- and post-fix paths** per the
   regression-arithmetic rule.

**CHARC's §3 gate — CLEAR, with two standing conditions:**

5. **The migration stays ADDITIVE.** No rebuild enters through review. Option (ii) — the new
   `provenance_corrections` table whose schema IS the evidence rule — is approved; option (i) is dead.
6. **Rounds 10-11's unreviewed status is flagged into your A-loop** (that is §0 above).

## §2 THE ENVELOPE EXTENSION — APPROVED, AND STRICTLY BOUNDED

`PIPELINE_LOCAL_TIMEZONE = "Pacific/Honolulu"` lands in **`swing/evaluation/dates.py`**.

**Approved scope, and no wider:** the CONSTANT, plus wiring the **two `dates.py` defaults**
(`:101`, `:123`) to it, plus **this arc's own imports.**

**CHARC verified the literal is spelled at SEVEN-plus live-code sites across THREE modules** —
`dates.py` ×2, `research_health.py` ×4, `tool_health.py` ×1+. **The other five-plus are NOT yours.**
They belong to the D37 sweep. Touching monitoring code under this approval would be exactly the
scope-creep the bounded grant exists to prevent.

## §3 SCOPE

**In:** `swing/trades/` (the new service module), `swing/data/` (the additive migration + repo),
`swing/cli.py`, `swing/evaluation/dates.py` (§2 only), and tests for all of it.

**Out — flag, never fix:** the other `Pacific/Honolulu` spellings (D37); the repo-wide lexical-TEXT-
timestamp sweep (D38 — you close it INSIDE your envelope via the plan's §3.0 rule, nowhere else);
`derive_trade_origin`'s latest-complete-run defect (flagged in the plan, entry-path, not this arc);
trade 21's post-dating citation; the `daily_recommendations` mutability gap.

## §4 GATES

Conventional commits; **no `Co-Authored-By`, no `--no-verify`, no amending**; quoted heredoc with the
last paragraph plain prose; trailer audit on the trailer **KEY**. Frozen-clock for date-touching
tests. **Report every count with the method that produced it, and every ABSENCE with the search that
produced it.**

1. Full fast suite **BEFORE** the Codex loop.
2. Codex `strong` to convergence. **`NO_NEW_CRITICAL_MAJOR` IS THE END** — first clean verdict
   terminates; post-convergence MINORS are corrected WITHOUT another round and the full suite on the
   final head is their verification; only a critical/major-SCOPE change re-opens.
3. **ROUND LEDGER + FIVE-ROUND GATE.** Keep a cumulative ledger (per round: severity counts, NEW vs
   REOPENED, reverts). **At round 5 and every 5 after, STOP and report the ledger to the orchestrator
   for approval to continue.** Continue only if NEW, in-envelope, non-reopened CRITICAL/MAJOR findings
   are still arriving; minors-only, oscillation, or rabbit-hole depth is stop-and-route.
4. **Declare the accepted limitations to your reviewer WITH THEIR REASONS and invite it to challenge
   the reasons.** A citation without its evidence is a bare disposition and does not count.
5. **DO NOT run `codex-auto-review`**, and do not offer focus areas for it — that second eye is the
   orchestrator's.
6. Full fast suite **AFTER** convergence off the final head.
7. **Codex invocation:** the PATH prefix `export PATH="$HOME/.local/node22/bin:$PATH"` MUST live in a
   SCRIPT FILE, not inline — this harness expands `$VAR` before the command reaches WSL, and without
   it `codex` resolves to a dead npm shim that fails with `exec: node: not found` **and exits 0**.
   Probe `codex --version` (expect `codex-cli 0.147.0`) first. A run with no banner is not a review.
8. **Two known non-regressions.** `test_forced_finish_lock_leaves_in_flight_row` is a load-sensitive
   flake (1 ms `busy_timeout` racing a thread). `test_run_stub_skip_exits_zero` **fails on `main`
   itself** — verified by running it there. Confirm the mechanism, do not chase either, do not "fix"
   them.
9. **Schema is live v35.** Your migration is **0036**. CLAUDE.md line 3 said v34 and has been
   corrected.

## §5 THE LIVE APPLICATION IS NOT YOURS

Shipping the surface and applying it to trade 23 are **separate events**. The CADL application is an
**operator-witnessed gate, step by step**, run after merge. Build it, test it, prove it on fixtures —
**do not touch the live DB.**

## §6 RETURN REPORT

Final chat message. **Do NOT run `scripts/role_mail.py`, do not post to any inbox, never
`--from orchestrator`.**

Include: per-task commits; test counts off the FINAL head with the command that produced them; the
round ledger with per-round assertions; **what your review made of the rounds-10/11 sections
specifically**; your §1 encodings with file:line; whether any accepted limitation was challenged and
how you dispositioned it; the trailer-audit result; and everything flagged-not-fixed.
