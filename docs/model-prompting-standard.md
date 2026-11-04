# Model prompting standard -- harness-wide operating economy

> **Adopted in this instance 2026-11-03** (CHARC, operator-concurred; the harness-template merge, `docs/harness-template-merge-2026-11-03-brief.md` item 6) from `rwsmythe/harness-template` `master` @ `4335ff6`, where it was operator-approved 2026-08-02. Instance edits are marked `[swing]`. **Rollover is of record in `docs/harness-architecture.md` section 6** (the 400K floor of 2026-10-26, the window-arithmetic exception of 2026-11-03, the three acts); section 9's rollover bullet below defers to it.

**Audience:** every role (directors, orchestrator generations, implementer cells). Adopted
2026-08-02, operator-approved, from Anthropic's model-specific prompting guidance (the
`claude-prompting-best-practices` family). **Reason it exists:** the current model generation
self-verifies, self-corrects, and follows short general instructions well. Doctrine written for
earlier models -- ambient verification mandates, enumerated rule lists, narrated self-correction --
now *compounds* with built-in behavior: it produced a week-long review spiral whose findings were
mostly about the review apparatus itself. This standard replaces that layer. Role docs point here
instead of restating it.

## 1. Verification is a GATE property, not an ambient one

Verify -- independently, at your own seat, evidence over self-report -- at exactly these points:
**accepts, pre-registrations, gate rulings, irreversible or outward actions.** Everywhere else,
do not instruct or perform ritual re-verification of routine claims; current models already
self-check, and instructed re-checks add cost without adding correctness. A claim that feeds no
gate needs no independent derivation.

## 2. Corrections: fix and move on

Correct an earlier statement only when the error would change someone's code, conclusions, or
decisions -- plainly, in a sentence, then continue. For slips that change nothing downstream,
make the fix without noting it. Do not narrate the anatomy of your own mistakes or tally past
errors across messages.

## 3. Checkpoints: three reasons to pause, no others

Pause for a human only when the work genuinely requires them: **a destructive or irreversible
action, a real scope change, or input only they can provide.** Otherwise act. Do not end a turn
on a promise of work ("I'll now...") -- do the work.

## 4. Progress claims: audit against tool results

Before reporting progress, check each claim against a tool result from this session. Report
outcomes faithfully: failing tests reported with output, skipped steps named, done-and-verified
stated plainly. This replaces enumerated honest-reporting rules; it is three lines because the
models now hold up their end.

## 5. Subagents: delegate work, not doubt

Delegate genuinely independent, sizeable tracks. Do not delegate what you can finish in a
handful of tool calls, and do not spawn agents to verify or double-check your own work -- that
is item 1's job, at gates only.

## 6. Message economy

Subject lines: one line, under ~15 words. Lead with the outcome -- the first sentence answers
"what happened." Content appears once (never subject-and-body duplication). Omit unchanged
standing state, ritual reassurances, pattern-tallies, and credit exchanges. Every token spends
the operator's allotment; there is no free channel.

## 7. Reviewers: coverage at the finding stage, filtering downstream

A reviewer reports **every** finding, including uncertain and low-severity ones, with a severity
tag -- classification and adjudication filter afterwards. Never instruct a reviewer to "only
report serious issues" or "be conservative": current models follow that literally and silently
drop real findings. **The round policy (pre-set cap vs run-to-convergence) belongs to
`docs/implementer-dispatch-recipe.md` section 3 `[swing]` -- briefs take it from there, never improvised.** Where a cap applies,
capped non-convergence is a permitted, reportable outcome.

## 8. Doctrine style: short principles, not enumerations

State the general rule; trust the model to instantiate it. Do not enumerate every pattern the
rule covers -- prescriptive lists degrade current-model output and go stale. When a rule
supersedes a figure, do not print the superseded figure beside it (a number is quotable; a
method is not). Never instruct a model to echo or transcribe its internal reasoning into output
(a refusal hazard on current top-tier models). **A standing decision exists only where it is
written: the seat that receives an operator ruling writes it to the governing doc in the same
turn it is received** -- a decision that lives only in a conversation will be overridden by
whatever the docs say, by the next seat doing its job properly.

## 9. Cost is architecture

Effort level is the primary cost lever -- drop it for mechanical passes; raise it only for
capability-sensitive work. Cost accounting counts **context consumed, not artifacts kept**: a
stopped or discarded agent spent its tokens regardless of what it committed. Every commission states what it costs (arcs, rounds, roughly lines
or agent-turns) and what it buys, before it starts. Proportionality is tested at the RUNG
level, not only per-gate: ask of the whole commission *what does this protect or produce, and
is that worth the spend?*

**Context depth is spend (adopted 2026-09-06, operator-directed; PROVISIONAL until the first
capped arc's subscription usage is compared against the transcript-derived figure).** Every turn
re-reads the whole context, so a turn at 900K costs about 2.25x a turn at 400K for the same work;
on this harness's record 68% of all read tokens landed on turns above 400K. Rules:
- **Rollover `[swing]`: see `docs/harness-architecture.md` section 6** -- a generation rolls AFTER its depth has REACHED 400K (the FLOOR, operator-directed 2026-10-26: never below it on its own judgment; below 400K it TAKES the next unit even when that carries it past 400K), at the next clean boundary, with nothing it started still running; the ONE exception is a unit that would not fit inside the 1M WINDOW (operator-ruled 2026-11-03), rolled before, with the arithmetic in the post. At or past 400K no new dispatch happens: that dispatch is the successor's. The prompt hook prints the session's depth every turn (`[ctx] NNNK of 1000K (NN%)`) and names the cap when it is reached; the seat's own read is `python scripts/cell_depth.py --sessions --live 1`.
- **Cells too.** A cell past ~400K is re-dispatched from a fresh context with its round ledger, the
  same way a director rolls; the ledger's REOPENED column is the oscillation detector. **A cell's
  depth is a DISPATCHER-READ figure** (amended 2026-09-07): the prompt hook never fires for a
  subagent, so the dispatcher reads the cell's transcript
  (`~/.claude/projects/<project>/<session>/subagents/agent-a<name>-*.jsonl`; depth on a request =
  input + cache_read + cache_creation tokens; peak = high-water) with `scripts/cell_depth.py`,
  before assigning work and at every round gate. Any sum over a project's transcripts MUST
  include the `subagents/` subdirectory -- a naive glob undercounted one arc by 43%.
- **Cells do not hold what disk holds:** a runner or reviewer log stays on disk and only its
  summary lines enter context; a doc already read is not re-read (the brief quotes what the cell
  needs); the round LEDGER, not the reviewer's output, is what a round adds to context.
- **The round-5 gate reads depth as well as findings** (the fill's ledger carries a context-depth
  column): a round at 800K costs four rounds at 200K.
- **Mechanical instruments run as cells.** A director's instruments (metrics scripts, sweeps),
  once committed and validated, are RUN by a cell that reports results; the director tier is for
  the reading and the ruling. Cells run instruments; they do not author or modify them.
- **Subjects are one line under 120 characters** (enforced in `scripts/role_mail.py`; 120 operator-directed here 2026-11-03, was 80 `[swing]`); the body
  is evidence + disposition. Comms is not where the tokens go, but subjects are read by every role
  at every prompt.
- The five-minute cache TTL for cells is DEFERRED until the v17 arc closes (a >5-minute gap at
  depth re-writes the whole context; measure on one arc first).

## 10. Per-role model/effort defaults (seam 4)

| role | tier (as of 2026-08) | rationale |
|---|---|---|
| directors (CHARC, RD) `[swing]` | Fable 5.1 / `medium` | judgment, ambiguity, long-horizon oversight; `medium` (operator-directed 2026-09-13, down from `high`) -- higher effort over-deliberates on routine judgment, and the director lanes are mostly routing and rulings |
| orchestrator | Opus (the `opus` alias; Opus 5.5 as of 2026-09-22) / `high` | agentic coordination, review precision at accepts, multi-agent management; drop effort for mechanical passes. The alias floats with the CLI; the launcher passes `high` EXPLICITLY because Opus 5.5's own default is `medium` and a saved effort level does not apply to it |
| implementer cells | Opus (`opus` alias; 5.5 as of 2026-09-22) / `high`+ for reasoning-dense; Sonnet 5 / `high` for well-specified builds; Sonnet 5 / `medium` for mechanical work | per-cell frontmatter; Sonnet follows briefs literally -- state scope explicitly in the brief |

The concrete launcher defaults live in `scripts/start_directors.ps1` (`$RoleLaunch`) `[swing]`. The
"top capability" requirement for the architect role tracks whatever tier is current -- the tier
NAME in the charter is intent, not a frozen model string.
