# 22-A — the fix leg (dispatch brief)

**Audience:** a fresh Claude Code instance with no prior conversation context.
**Mission:** close every open item on arc 22-A so it can reach its merge gate — four production fixes,
two director-ruled behaviour changes, a class fix, 22 test repairs, two gate repairs, and a sweep.
**Expected duration:** a long session, plausibly more than one. It is a wide leg, not a deep one.

**This is the ONLY fix leg. It is deliberately not split** — splitting recreates the cross-arc
composition class (`harness-architecture.md` §5.1), which is the one defect no review rung catches.

---

## §0 READ FIRST

1. **[`docs/phase22-arc-a-executing-resume.md`](phase22-arc-a-executing-resume.md)** — the state of
   record. **Items 1–14 of its OPEN LIST are your task list**, each with the ruling that governs it.
   Every ruling below is quoted there in full; this brief does not restate them, it sequences them.
2. **[`docs/22-a-case-binding-audit-findings.md`](22-a-case-binding-audit-findings.md)** (1,433 lines)
   and **[`docs/22-a-case-binding-audit.json`](22-a-case-binding-audit.json)** (146 rows) — the
   per-case verdicts. The JSON is your worklist for §4; filter it, do not re-derive it.
3. **`CLAUDE.md`** §Gotchas — in particular gotcha 11 (mirror families), the `REPLACE` gotcha and its
   three facets, the NULL-`WHEN` trigger gotcha, and the Python-vs-SQLite rounding gotcha. **This arc
   has been caught by its own CLAUDE.md gotchas twice.** Read them as live hazards, not history.
4. The plan: `docs/superpowers/plans/2026-08-24-phase22-arc-a-entry-path-order-mandate-binding.md`.

### Skill posture

- Do **NOT** invoke `superpowers:brainstorming` or `writing-plans` — the design is ruled, not open.
- **Do use `superpowers:test-driven-development`.** Every item here is red-green-commit.
- **You run the Codex review chain yourself, by hand**, per `docs/implementer-dispatch-recipe.md` §3.
  The transport hazards on this arc are measured and severe — read §7 below before your first round.

---

## §1 THE STANDING RULINGS YOU INHERIT — do not re-derive, do not re-litigate

These were each bought with a real defect. They bind your implementation:

- **Cohort bookkeeping NEVER blocks a money-bearing entry.** RD, ruled twice, violated four times in
  this arc. **Every cohort-provenance guard states AT ITS SITE which of ENTRY or LABEL it refuses —
  and the answer is always LABEL.** This is the leg where that default gets inverted at the seam.
- **The trigger's predicate set must be a SUBSET of the service's admission predicates.** The trigger
  is a backstop against writes that BYPASS the service, never the discovery point for an input the
  service admits.
- **SQL verifies a FACT; it must never re-derive a JUDGMENT across an engine boundary.**
- **A ladder evaluated from a SEAT makes the refusal reason a property of `(world, seat)`.** Any spec
  or test pinning a reason must name the seat.
- **Where two refusals are both true, prefer the MORE SPECIFIC.**
- **A refusal-only test set cannot establish that a guard can EVER accept.**
- **A trigger whose `WHEN` can evaluate to NULL does not fire — it fails open, silently.**
- **A commit message is a CLAIM; staging a file is not changing it.** Read the DIFF of what you just
  committed.
- **Do not claim exact when you are not.** A heuristic declared with its blindness named is honest;
  one widened and called closed is not.

---

## §2 THE PRODUCTION FIXES (resume-record items 1, 3–9)

Take these first — they are the smallest and they de-risk the leg.

**2.1 The entry-block re-disposition (item 1).** `swing/web/routes/trades.py:1106`. Arc-introduced by
`bc85c5e1`, never in production. RD ruled the refusal MOVES: a malformed `schwab_order_id` refuses the
**LATCH BINDING**, never the **ENTRY**. The trade is recorded; cohort keys land honest-unset
(`manual_off_pipeline` + NULL + NULL); a warning names the malformed envelope. **His discriminating
case is binding:** a submitted envelope with a numeric `schwab_order_id`, ticker in today's decision
table -> the trade IS written, keys honest-unset, warning names the malformation. A 400 fails it;
admitting and stamping `pipeline_aplus` fails it too. **The arc's own test at
`tests/web/test_routes/test_22a_task10_entry_route_ext2.py:352` currently PROVES no trade is written —
it must be inverted, not deleted.**

**2.2 `22A-R15-03` (item 3).** `cohort_provenance_correction.py:2185-2192`. Catch the rollback failure
explicitly, log that the connection must be discarded, raise the cleanup error CHAINED from the
savepoint error. **Add a BOTH-VERBS-FAIL proxy row** — the two existing proxies fail one verb each and
structurally cannot reach the composition. It contradicts `AL-15` four commits older in the same leg;
reconcile them.

**2.3 `BaseException` (item 4).** `cohort_provenance_correction.py:2463`. One line.

**2.4 `22A-R15-01` (item 5).** Require the operand key set at the `0037` INSERT trigger and BIND each
value to the cited fill. **Do this while `0037` is UNAPPLIED and editable in place** — verify that is
still true before you start (`SELECT MAX(version) FROM schema_version` on the live DB is v36; **you do
not touch the live DB, only confirm the migration has not shipped**). Insert-time rule, so legacy
four-key rows are unaffected.

**2.5 `22A-R15-02` (item 6), NARROW.** Reject a non-finite `actual_limit_price` at the AUTHORIZATION
boundary with a typed refusal. Live incidence is measured ZERO; the mechanism is real (`+inf` passes
`CHECK (p > 0)`, `json.dumps` emits bare `Infinity`, `json_valid` rejects it). **The CLASS fix is §5.**

**2.6 `22A-R15-05` (item 7).** `SEEDING_INSERT` matches `INSERT [OR ...] INTO` only, so a bare
`REPLACE INTO` seeds the table with both the ships-empty pin and its splice discriminator GREEN —
measured. **This is CLAUDE.md's own `REPLACE` gotcha inside the arc's own instrument, for the second
time.** The migration does seed nothing today; what is defective is the claim's ENFORCEMENT.

**2.7 `22A-R15-06` / `-07` (item 8) — COMPLETE THE DECLARATIONS, DO NOT WIDEN THE WALKS.** Add the
undeclared spellings to `AL-12`'s rows (parenthesised `json_extract`, `import json as j`) and `AL-14`'s
(case-sensitivity, `main.`-qualified references). The declare-versus-widen ruling governs; the routed
class fix (token-aware scanning) is NOT yours.

**2.8 CHARC's migration comments (item 9).** One sentence each at `0037:1507` and `:1565` recording WHY
the ordering is a FACT — citing the `0033:704-712` format constraint **by line**. Zero logic change.
Purpose: the next reader must not read them as violations and "fix" them into the hole.

---

## §3 THE RUNG-8 LEGIBILITY ENRICHMENT (item 12) — the one with a binding trap

When rung 8 is about to refuse `ambiguous_ticker_orders`, evaluate the SUBJECT's own liveness and
refuse with the more specific reason if the subject's own mandate is dead.

**THE SELECTION MUST BE THREE-VALUED. This is CHARC's binding addition and it is where this task
fails if you rush it:**

| subject's own liveness | outcome |
|---|---|
| proven DEAD | refuse with the specific reason (`mandate_not_alive` + `clear_reason`) |
| proven LIVE | fall through to `ambiguous_ticker_orders` |
| **UNPROVABLE** | **fall through to `ambiguous_ticker_orders`** |

**A two-valued "dead or not-dead" check reintroduces exactly the inversion `R3-03` corrected in the
population rule — the same defect, in the same file, one rung over, six weeks later.** Its
discriminating case is mandatory: a subject whose own aliveness is UNPROVABLE (archive unavailable /
snapshot NULL) beside a live rival must still refuse `ambiguous_ticker_orders`, never
`mandate_not_alive`. An implementation treating unprovable as dead must FAIL that test.

Rung 8 still runs first and still refuses. This only chooses a better reason, so **it can never convert
a refusal into an admission** — verify that property holds in your implementation.

---

## §4 THE 22 TEST REPAIRS (item 11)

Filter `docs/22-a-case-binding-audit.json` for `verdict != "FAITHFUL"`. Each row carries
`spec_location`, `specified_outcome`, `test_node_id`, `asserted_outcome` and a `note`.

**Method, and it is the same one that found these:** read the plan's specification FIRST, form the
expected assertion, and only THEN open the test. The tests are internally coherent and their
docstrings tell consistent stories — reading the test first anchors you and you will ratify it.

- **`4` (CONTRADICTS)** — the test builds a broker-ACCEPTED order and asserts ADMISSION where S3.4
  (`PLAN:1910`) specifies a place intent with NO validity row FALLING THROUGH. **It also inverts lens
  clause 3b, which names case 4 as the case that FAILS an "any armed latch" implementation.**
- **`1-pre` — RD ruled it and it carries THREE requirements, not one.** See resume-record item 11.
  **Do not treat this as twin hygiene: it is trade 25's LIVE outcome and S9's operator gate is written
  around this row.** Copy `5b-pre`'s rung-9 pattern rather than inventing one.
- **`4c-i`** — now resolvable at the LADDER grain once §3 lands. Assert `mandate_not_alive` as S3.4c
  specifies. **The grain does NOT move.**
- **`33` and `36` are VACUOUS** — they cannot fail. Make them able to.
- **Pattern A (9 twins)** — seven share one parametrized body that uses the case id only as a directory
  name. `29d-pre`, `4c-i-pre` and `5b-pre` do it correctly in the same tree; follow them.
- The rest: patterns B, C and E in the findings doc, each with its note.

**When you repair a case, its spec and its test must AGREE on the seat** (§5.3).

---

## §5 THE CLASS FIXES AND SWEEPS

**5.1 Authorize-then-abort closure check (item 10).** Every trigger refusal predicate maps to a named
service-side check, asserted mechanically in BOTH directions, so a predicate added to either side
without its twin fails loudly. **Reuse the `AL-3` / `SS-12` closure-walk shape — CHARC was explicit
that this reuses an instrument rather than authoring a fourth.** Test shape: **a satisfiability proof
in the NEGATIVE direction** — for each trigger refusal reason, prove the SERVICE refuses that input
FIRST with a typed error, i.e. the trigger's refusal is UNREACHABLE through the service. (Mirror of
the proof this arc already built, which shows a guard CAN accept a truthful row.)

**5.2 The ENTRY-or-LABEL site declarations.** Every cohort-provenance guard states at its site which it
refuses. Four instances in this arc each defaulted to blocking the ENTRY; invert the default at the seam.

**5.3 The seat sweep (item 13).** Check EVERY remaining ladder case: **if it pins a refusal reason and
does not name the seat, it is ambiguous and may be passing for the wrong reason.** Report the count you
checked and the count you changed — this is a sweep, so its completeness claim needs a method.

**5.4 The fixture-spec alignment.** S3.4c's sentence says HORIZON-EXPIRED; the fixture builds
SUPERSEDED. Both are proven-dead and the discriminating purpose is unchanged, so **align the SPEC's
incidental example to the fixture — as a declared AMENDMENT WITH ITS REASON, never silently.**
**The boundary, and do not exceed it:** an incidental example may move to the code when the case's
discriminating purpose is provably unchanged. **A specified VERDICT, GRAIN, or the property under test
NEVER may.** If you find yourself wanting to move one of those, stop and report it instead.

**5.5 The gate repairs (item 14).** **G1:** make the six dead `parametrize` calls CONSUME their
`*_CASE_IDS` lists, as the two live sites already do. Your acceptance test is the one the orchestrator
ran: **strip every `FunctionDef` from a module and the gate must NOT report its cases implemented.**
**G2:** give `implemented_case_ids()` the module-level scope test its own docstring already claims.

---

## §6 BINDING CONVENTIONS

- **Worktree `.worktrees/22-a-fix`, branched off `22-a-exec`.** `git worktree add .worktrees/22-a-fix
  -b 22-a-fix 22-a-exec`. **Never commit to `main` or to `22-a-exec`.**
- **Conventional commits. No `Co-Authored-By` footer. No `--no-verify`. No amending.** The project is
  at 4,574 consecutive trailer-free commits.
- **TDD per item:** failing test -> minimal implementation -> pass -> commit. One red-green cycle per
  logical change.
- **You do NOT touch the live DB.** Migration `0037` stays UNAPPLIED; confirming that is read-only.
- **Frozen-clock convention** for any NEW date-touching test.
- **Out-of-scope catches get a durable landing the moment you notice them** — in your return report,
  not a chat aside.

---

## §7 THE REVIEW — and the transport hazards are measured, not theoretical

Run the Codex chain to convergence per the recipe §3. **The 5-round cap is SUSPENDED on this project.**

**Read this before your first round. Every one of these was measured on THIS arc:**

- The full diff was **1,382,975 chars** against Codex's **1,048,576** cap. Use recipe §3's **`$HOME`
  staging fallback**; never improvise a split. **A capped delivery shows banner + echoed input and NO
  FOOTER, and is NOT a round.**
- **FIVE distinct exit-0-and-nothing-happened mechanisms:** the dead npm shim; a missing redirect
  target; CRLF line endings; MSYS path-mangling; and **passing WSL a Windows `C:/...` path instead of
  `/mnt/c/...`**. **Always verify the redirect target is non-empty BEFORE reading it.**
- **The harness collapses `\\` to `\` inside a bash heredoc, including a quoted one.** Exit codes stay
  0; corruption surfaces only on execution. Use Write/Edit for content with backslashes.
- **Poll the EXIT FILE, never the transcript tail.** Anti-self-match: `pgrep -af codex | grep -v
  'pgrep\|grep'`.
- **Three assertions, three windows:** the banner proves a round STARTED, the `tokens used` footer
  proves it FINISHED, an ERROR-grep covers the middle. **Exit code 0 is not evidence a review ran.**
- **Persist every round's RESPONSE** (not just prompts) to `~/swing-data/review-transcripts/22-a-fix/`
  so convergence can be verified independently at QA. The worktree copy dies with the worktree.

**Run the full fast suite TWICE: once BEFORE the Codex loop** (so the review converges on a green diff,
catching cross-cutting global-invariant tests per-task TDD misses) **and again AFTER it converges** (the
no-false-green gate that catches review-fix-introduced breaks).

---

## §8 DONE CRITERIA

- Resume-record items 1, 3–14 each closed or explicitly reported as not-done with a reason.
- The three-valued discriminating case in §3 exists and FAILS a two-valued implementation — **verify by
  writing the two-valued version and watching it fail, then discard it.**
- The §5.5 gate test: stripping every `FunctionDef` from a module makes the gate report its cases
  UNIMPLEMENTED.
- Full fast suite green on the final tree; `ruff check swing/` clean; zero trailers.
- Codex converged, with every round's response persisted.

## §9 RETURN REPORT

As your **final chat message**. Do NOT post to any mailbox and do NOT run `scripts/role_mail.py` —
director comms are the orchestrator's, and posting from an implementer bypasses a QA gate.

1. Per-item disposition for resume-record items 1, 3–14.
2. **The seat sweep's numbers: how many ladder cases checked, how many named no seat, how many changed
   — and the METHOD that produced those counts.**
3. The test-repair count by audit verdict, and **the restated case-binding number with G4's precision
   requirement honoured: say whether it means BOUND or TESTED.**
4. Codex: round count, final verdict, transcript paths.
5. Suite counts (both runs) and ruff.
6. **Every V1 simplification, placeholder or accepted limitation you shipped, with its reason.**
7. Anything you found and did NOT fix, with where it should land.

## §10 IF YOU GET STUCK

- **A ruling that seems wrong:** report it, do not route around it. Several of these were ruled through
  three rounds of correction and the reasoning is in the resume record.
- **A spec and a test that disagree:** that is §5.4's territory — check the seat first (§5.3), and
  remember the incidental-versus-discriminating boundary. If a VERDICT, GRAIN or property under test
  would have to move, **stop and report**; that is a ruling, not a local resolution.
- **If the leg is larger than one session:** commit what is complete and list what remains explicitly.
  A partial leg honestly bounded is useful; one that quietly thinned out at the end is the failure
  this arc has spent fifteen rounds learning to catch.
