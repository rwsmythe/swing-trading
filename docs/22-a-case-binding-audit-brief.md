# 22-A — the 146 case-binding SEMANTIC re-audit (dispatch brief)

**Audience:** a fresh Claude Code instance with no prior conversation context.
**Mission:** for each of the 146 live acceptance cases in arc 22-A, determine whether the test bound to
that case **asserts what the plan specifies for it** — and report the result with the method that
produced it. This is a **measurement**, not a repair.
**Expected duration:** a long single session. The work is 146 spec-then-test reads; it does not compress.

**You are NOT fixing anything.** You ship one findings document and its machine-readable companion. Any
code change — including the obvious one-line ones you will be tempted by — is OUT OF SCOPE and belongs
to the fix leg that consumes your report.

---

## §0 READ FIRST

Read these, in this order, before you form any opinion:

1. **`docs/phase22-arc-a-executing-resume.md`** — the arc's state of record. It already carries a
   section headed "A CLAIM THIS DOCUMENT PREVIOUSLY MADE IS FALSE." Your audit is what replaces the
   claim it retracts.
2. **`tests/trades/case_registry_22a.py`** (391 lines) — the case manifest. Its module docstring
   explains why a parsed-prose closure instrument could not be made deterministic and what was done
   instead. `PLAN_CASES` (146 entries) maps case id → owning task. `EXCLUDED_CASES` (34) carries
   reasoned exclusions. `ALIASES` (4) maps a plan id to the pair it was later split into.
3. **`tests/trades/test_22a_case_closure.py`** (254 lines) — the gate. Read
   `implemented_case_ids()` at line 172 closely: **it is the instrument under audit.**
4. **`docs/superpowers/plans/2026-08-24-phase22-arc-a-entry-path-order-mandate-binding.md`**
   (4,187 lines) — the specification. Case text lives at **S3.1–S3.8** (§1788 onward), the omission
   lens at **S3.7** (§2094), the free-dimension audit at **S3.8** (§2179), the reason view at
   **S5.1** (§3070), plus acceptance cells in the task ladder and the `48a-48p` / `49a-49i` families
   introduced in S4.3 bullets that never use the word "case."
5. **`CLAUDE.md`** §Gotchas and **`docs/orchestrator-context.md`** §"Pre-Codex review + brief-authoring
   disciplines" — for the house disciplines, particularly **existence ≠ completeness**.

### Skill posture

- Do **NOT** invoke `superpowers:brainstorming`, `writing-plans`, `executing-plans`, or
  `subagent-driven-development`. There is no design here and no plan to execute.
- Do **NOT** run a Codex chain. This dispatch ships no production code. Your report is verified by the
  orchestrator re-deriving a sample of your verdicts independently, which is a stronger check on an
  audit than an adversarial pass over a document.
- `superpowers:test-driven-development` does not apply — you write no tests.

---

## §1 WHY THIS EXISTS — the class, stated exactly

For fifteen review rounds this arc reported **"146 of 146 cases implemented, each traced to a passing
node id."** That figure is **name coverage, not semantic implementation.**

`implemented_case_ids()` binds a case id to a test by one of two purely lexical conventions:

- a test function whose name **ends** `_case_<slug>`; or
- a module-level literal list or tuple bound to a name **ending** `_CASE_IDS`, whose string elements
  are read as covered case ids.

Neither convention can see what the test asserts. Both directors have canonicalized the class:

> A coverage meter binding a case id to a test **NAME** measures **NOMENCLATURE**, not coverage — the
> existence half of existence-versus-completeness, met now at a coverage meter after counts, greps and
> absences. (CHARC, 2026-09-01)

**The demonstrated instance.** The plan's heading at line 1910 reads *"S3.4 CASE 4 — RHI (trade 24,
LIVE, ITS REAL SHAPE): place-intent WITHOUT a validity row → falls through."* The test bound to case 4,
`tests/trades/test_22a_task4_authorization_ladder.py:257`, builds a broker-**accepted** order via
`_accept(...)` and asserts `verdict.admitted is True` — the opposite outcome, from the opposite world.

**Read the next sentence twice, because it is the methodological heart of this dispatch.** That test is
internally coherent. Its own docstring tells a consistent story ("RHI's shape: a broker-accepted
order"). Nothing about reading the test alone reveals the defect. It is visible *only* by reading the
plan's specification first and then asking whether the test measures it. **Fifteen rounds of a
competent reviewer missed it by reading the code and asking whether the code was right.**

So: **spec first, always.** Form the expected assertion from the plan before you open the test file.
If you read the test first you will be anchored by its internal story and you will ratify it.

### The measurement that sizes your work

Run against the current arc branch, the 146 live cases divide by binding shape:

| binding shape | cases |
|---|---|
| bound by a test **function name** ending `_case_<slug>` | 104 |
| bound by membership in a `*_CASE_IDS` **list literal** | 53 |
| **bound ONLY by list membership — no named function at all** | **42** |

The nine `*_CASE_IDS` sites: `OMISSION_CASE_IDS` (16), `FIDELITY_CASE_IDS` (9),
`COVERAGE_CASE_IDS` (5), `ROUNDING_CASE_IDS` (2), `TIE_BASIS_CASE_IDS` (3),
`SERVICE_LIMIT_CASE_IDS` (1) — all in `tests/data/test_22a_task11_citation_evidence.py`;
`THE_51_CASE_IDS` (5), `THE_35_CASE_IDS` (5) in `tests/data/test_22a_task2_migration_0037.py`;
`RELOCATED_TWIN_CASE_IDS` (7) in `tests/trades/test_22a_task4_authorization_ladder.py`.

**The 42 list-only bindings are the highest-density place for this class to hide, and you audit them
first.** A single parametrized test asserting one generic shape across sixteen cases whose
specifications differ makes all sixteen "covered." Case 4 at least had a dedicated function.

---

## §2 SCOPE

**In scope:** all 146 case ids in `PLAN_CASES`. Every one gets a verdict and a citation.

**Also in scope, and report them as separate sections:**

- **The 34 `EXCLUDED_CASES`.** You are not re-litigating the exclusions, but each carries a stated
  reason — flag any whose reason is **factually wrong** (as distinct from a judgment you'd have made
  differently). A wrong exclusion hides a case entirely, which is worse than a weak binding.
- **The 4 `ALIASES`.** Confirm each alias expands to members that are themselves live and audited.
- **The gate itself.** If you find a third binding path, or a way the two known conventions can bind a
  case to a test in a *different module* than the one that means to cover it, say so.

**OUT of scope — do not do these, however obvious:**

- **Any change to `swing/`, to any migration, or to any test.** Not even a comment. Not even case 4.
- Re-running or re-designing the closure gate.
- Adjudicating the seven round-15 findings, or the entry-block re-disposition. Those are dispatched
  separately and are already ruled.
- Judging whether a case's **specification** is *correct*. You judge fidelity of test to spec, not the
  wisdom of the spec. If a spec is internally contradictory, that is an `UNVERIFIABLE` verdict with the
  contradiction quoted — not a ruling.
- Running the full suite. You may run individual tests to observe behaviour; you do not need a green
  suite and you are not producing one.

---

## §3 BINDING CONVENTIONS

- **Worktree:** `.worktrees/22-a-audit`, branched **off `22-a-exec`, NOT off main** — the tests and the
  plan exist only on the arc branch. Create it with:
  `git worktree add .worktrees/22-a-audit -b 22-a-audit 22-a-exec`
- **Never commit to `22-a-exec` or to `main`.** Your commits land on `22-a-audit` only.
- **Commits:** conventional. **No `Co-Authored-By` footer. No `--no-verify`. No amending.** This project
  is at 4,574 consecutive trailer-free commits; do not be the break.
- Subject form: `docs(22-A): case-binding audit -- <what>`.
- **ASCII in the JSON artifact and in every commit message** — those flow through Windows PowerShell
  stdout, which is cp1252, where a non-ASCII glyph raises `UnicodeEncodeError`. Prose in the markdown
  findings doc may use the same typography as the rest of `docs/` (this brief does). The rule is about
  what crosses stdout, not about markdown.
- **A verdict you did not verify is not a verdict.** Every row states how it was established: `READ`
  (you read spec and test), or `EXECUTED` (you ran the test and observed). If you could not establish
  it, the verdict is `UNVERIFIABLE` and you say why. **Never infer a verdict from a test's name, its
  docstring, or its neighbours** — that is the exact failure you are auditing.

---

## §4 THE TASK

### 4.1 Per-case verdict

For each of the 146 live cases, produce one row:

| field | content |
|---|---|
| `case_id` | as in `PLAN_CASES` |
| `owning_task` | as in `PLAN_CASES` |
| `spec_location` | plan file path + line number of the text that specifies the outcome |
| `specified_outcome` | ONE sentence, in your own words, of what the plan requires. Write this BEFORE opening the test. |
| `binding_shape` | `named_function` / `case_ids_list` / `both` |
| `test_node_id` | full pytest node id (`path::function`), or the list site for a list-only binding |
| `asserted_outcome` | ONE sentence of what the test actually asserts |
| `verdict` | one of the five below |
| `method` | `READ` or `EXECUTED` |
| `note` | required for any verdict other than `FAITHFUL` |

**The five verdicts — use these exactly:**

- **`FAITHFUL`** — the test asserts the specified outcome. Nothing further needed.
- **`WEAKER`** — the test asserts a strict *subset* of what the spec requires. The known exemplar is
  case `4b`: it asserts only that the lookup returns empty, never the end-to-end persisted outcome
  S3.4 requires. A `WEAKER` binding is not a false claim, but it does not establish the case.
- **`CONTRADICTS`** — the test asserts something the spec **excludes**. Case 4 is the exemplar. This is
  the severe class: it means the number was not merely unearned, it was wrong.
- **`ABSENT`** — the case is bound (by name or by list) but no assertion in the bound test relates to
  the case's specified outcome at all. Expect this mostly among the 42 list-only bindings.
- **`UNVERIFIABLE`** — the plan's text does not determine an outcome, or determines two. Quote both.
  This is a routing outcome, not a failure; it goes to the operator with the directors.

### 4.2 Order of work

1. **The 42 list-only bindings first.** For each `*_CASE_IDS` site, read the parametrized test that
   consumes the list, then read **each** member case's specification separately, and ask whether the
   single generic assertion actually establishes *that* case. Do not batch-verdict a family.
2. **Case 4 and case 4b** next — confirm or correct the two findings above from the sources. If you
   disagree with either, say so plainly with your evidence; you are not required to ratify them.
3. **The remaining named-function bindings.**
4. **The 34 exclusions and the 4 aliases.**

### 4.3 Deliverables

Two files, both committed on `22-a-audit`:

1. **`docs/22-a-case-binding-audit-findings.md`** — the report. It MUST open with:
   - the **method**, stated in a short paragraph: spec-first reading, what `READ` and `EXECUTED` mean,
     and what the audit can and cannot establish. Both directors have said the result must be reported
     *with* its method; this paragraph is that requirement.
   - the **counts** by verdict, and
   - **every `CONTRADICTS` and `ABSENT` row promoted to the top**, in full, before the complete table.
2. **`docs/22-a-case-binding-audit.json`** — the same rows, machine-readable, one object per case, keys
   exactly as the field names in §4.1. This exists so the orchestrator can re-derive a sample
   mechanically rather than by re-reading your prose.

### 4.4 State the honest bound on your own instrument

Your report closes with a short section naming what **your** audit could miss. You are one reader
applying judgment 146 times; a fatigue-driven `FAITHFUL` is exactly the failure mode that produced the
thing you are auditing. If your confidence differs across the run, say where. **Declaring a heuristic
with its blindness named is honest; widening one and calling it closed is not** — that is a standing
ruling on this arc, and it applies to you.

---

## §5 DONE CRITERIA

- All 146 live cases carry a verdict, a citation, and a method. No blanks, no "see above."
- Every non-`FAITHFUL` verdict carries a note that a reader can act on without re-deriving your work.
- The 34 exclusions and 4 aliases are checked and reported.
- Both deliverables committed on `22-a-audit`; `git log` shows zero `Co-Authored-By` trailers.
- **You changed no code, no test, and no migration.** `git diff 22-a-exec..22-a-audit --stat` shows
  `docs/` only.

## §6 RETURN REPORT

As your **final chat message** (do NOT post to any mailbox — the orchestrator owns all director
comms, and posting from an implementer bypasses the QA gate):

1. **Counts by verdict**, and the number of cases whose binding is list-only.
2. **Every `CONTRADICTS` and `ABSENT` case**, one line each: case id, what the spec requires, what the
   test asserts.
3. **Every `UNVERIFIABLE` case** with the ambiguity quoted — these need a director ruling.
4. **The `WEAKER` set**, summarized by pattern rather than enumerated, unless the patterns differ.
5. **Exclusion / alias findings**, if any.
6. **Anything you found about the gate itself** — a third binding path, cross-module binding, or any way
   the 146 number could be wrong in the other direction (a case implemented but not counted).
7. **Your §4.4 honest bound.**
8. The commit shas and the two file paths.

## §7 IF YOU GET STUCK

- **A spec you cannot locate:** the registry's docstring documents six reasons the plan's case ids
  resist a static walk, including ids introduced in bullets that never use the word "case." Read the
  docstring before concluding a case is unspecified. If it is genuinely unspecified, that is
  `UNVERIFIABLE` and a real finding — report it, do not invent the spec.
- **A test you cannot run:** run is optional. `READ` is a full-strength method here; say which you used.
- **Scope pressure:** if you find a defect you badly want to fix, write it down and keep auditing.
  The fix leg is already scoped and will consume your report. An audit that starts repairing stops
  being a measurement.
- **If the work is larger than one session:** commit what is complete, with the remaining case ids
  explicitly listed as NOT YET AUDITED. **A partial audit honestly bounded is useful; a complete one
  that quietly thinned out at the end is the failure this whole dispatch exists to correct.**
