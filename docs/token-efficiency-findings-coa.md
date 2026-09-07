> Delivered to swing-trading by the operator, 2026-09-06, as the reciprocal of `token-efficiency-findings-swing.md`. Untracked here by the same convention. Source of record: coa-chess `docs/proofs/2026-09-06-token-efficiency-findings-coa.md` at commit 68e15b7e. The two measuring scripts (per-session usage sums; depth bands + tool fillers) are short read-only passes over the session transcripts and port to any project directory under ~/.claude/projects.

# Token-efficiency findings from the coa-chess harness -- the comparison against swing-trading's

**From:** coa-chess CHARC, 2026-09-06 (session 3c2de8d8). **Purpose:** the operator commissioned the
same spend review swing-trading CHARC ran (`token-efficiency-findings-swing.md`); this is coa-chess's
own record measured with the same lens, and where the two harnesses' headlines differ, why.
**Evidence base:** every session transcript still on disk for this project (17 director/orchestrator
sessions + their subagent transcripts, 2026-07-31 to 2026-09-07, 43,860 metered messages), the comms
archive (2,791 delivered copies), the git log, and the role docs. All numbers were computed at my seat
by two read-only scripts; the dollar figures are LIST-PRICE WEIGHTS used only to rank levers -- the live
path is subscription tokens, and how the subscription weights cache reads is not known to me.

## The headline finding: CONTEXT DEPTH is the dominant spend, not output and not model choice

| evidence (coa-chess, all sessions on disk) | number |
|---|---|
| Output tokens, all roles, all models | 30.8M -- **~6% of weighted spend** |
| Cache READ tokens (context re-sent per turn) | 16.29B -- ~45% |
| Cache CREATE tokens (new context written, at the 1h 2x rate) | 759M -- ~48% |
| Mean context per metered turn | ~371K tokens |
| Turns above 400K context | 18,612 of 43,872 (42%) -- carrying **68% of all read tokens** |
| Turns above 600K | 9,605 (22%) -- carrying 42% |
| Sessions reaching >900K context | 12 of the 22 largest (main and subagent alike; max 999,881) |
| Weighted spend by lane | orchestrator lane (main + cells) ~64%; OpsDir ~25%; CHARC ~11% |
| Peak day (2026-09-03: cache rung + step 4 + baseline pass) | orchestrator lane read 1.25B tokens in one day |

**Interpretation:** every turn re-reads the whole context at the cache-read rate, so a turn at 900K
costs ~2.25x a turn at 400K for the same work. The harness rolls generations at ~98% of the window
(CHARC 09-02; swing's CHARC reached 94%). The handoff itself is cheap -- a fresh generation reads
~110 KB (~28K tokens) of role docs -- which is **0.03% of one deep session's reads**. The depth tax,
not the handoff, is the cost. Swing's headline was the review loops; ours is that the review loops
(and everything else) run inside contexts that have already been paid for hundreds of times.

**Where the depth comes from (tool-result bytes into context, all sessions):** Read 24.5 MB (55%),
Bash 17.0 MB (38%); of that, the orchestrator's CELL sessions carry 29 MB of the 44 MB total (Read 16,
Bash 12) -- cells re-read the large docs (the 30 KB review-gate fill, briefs, proofs) and pull runner
and reviewer output into their own context, round after round. Assistant output (30.8M tokens across
the record) sits in context thereafter as well.

## What I recommend, compared item by item with swing's list

1. **A DEPTH CAP replaces the 98% rollover -- the single largest lever, and it is free.** Roll a
   director or orchestrator generation at ~400K context (the harness already has the OVERWRITTEN
   state pointer and rulings-not-to-re-derive that make a handoff cheap). Arithmetic on the record:
   the 11.1B read tokens spent above 400K would have been ~5.6B at a 400K cap, ~34% of all reads,
   roughly **a quarter to a third of total spend**, with no change to what any role does. Swing's item 7
   ("context is spend") is the same observation; the coa-chess record quantifies it and makes it the
   headline rather than a footnote.
2. **Cells are the deepest sessions and the heaviest fillers.** Subagent transcripts reach 932K.
   The dispatch recipe already says "route runner output to a scratch file"; the record says 12 MB of
   Bash output still entered cell context. Norms with teeth: a cell never cats a runner log (grep the
   summary lines; the file stays on disk), never re-reads a doc it has already read (the brief quotes
   what the cell needs), and the round ledger -- not the reviewer's output -- is what enters context
   per round. A cell past ~400K is re-dispatched from a fresh context with its ledger, the same way a
   director rolls. Swing's items 3-5 (stop planning earlier, drop per-leg loops, fire the cascade
   remedy at the first residual round) all reduce ROUNDS; here the same rounds are paid at whatever
   depth the cell has reached, so round count and depth multiply.
3. **The round-5 gate asks about depth as well as findings.** The fill's five-round gate continues
   only on new in-envelope blocking findings. Add the cell's context depth to the ledger the
   dispatcher reads: a round at 800K costs four rounds at 200K. Coa-chess round counts (cache-read
   rung 10, probe 7, amendment-12 6, v15 6) sit inside swing's 5-11 band; the no-hard-cap ruling stands.
4. **OpsDir at director tier and 1M depth.** OpsDir's single largest session ran 1,589 messages to
   998K; two OpsDir sessions are the two largest producers of output in the record. The instruments
   (metrics scripts, sweeps over 240 directions) are mechanical once written -- run them as sonnet
   cells reporting results, keep the director tier for the reading. Same shape as swing's item 1
   (dispatch by phase), applied to a director rather than an implementer.
5. **Tier compliance holds here** (swing's item 2 did not hold there). Launcher: CHARC fable/high,
   orchestrator opus/high, OpsDir fable/high, matching `docs/model-prompting-standard.md`; cells
   opus-high / sonnet-high / sonnet-medium by frontmatter, and sonnet carried more cell messages
   (18,962) than opus (9,443). Two stale long-running sessions were found on the box at opus/max and
   opus/xhigh from before the standard; not a current-launch problem.
6. **Comms is NOT a spend problem here, but subjects are a hygiene problem.** 161,851 body words were
   delivered since 09-01 (~0.2M tokens, three orders of magnitude below the depth tax). Subjects,
   however, average 390-540 characters by sender and reach 5,415; swing capped subjects in code at 80.
   Adopt the code cap (custodian-of-form; role_mail.py), keep bodies as evidence + disposition. Director
   bodies average 520-660 words -- swing's ~700; comparable, and not where the tokens go.
7. **The 1-hour cache TTL is the write multiplier for the harness's own sessions too.** 759M create
   tokens at 2x is ~48% of weighted spend. A 5-minute TTL (1.25x) would cut it by ~37% for sessions
   whose turns arrive under five minutes apart -- true of cells in a loop, not of a director awaiting the
   operator, and a >5-minute gap at 900K depth re-writes the whole context. Second-order; consider only
   for cells, only after the depth cap, and measured on one arc first.
8. **State pointers must stay pointers.** `docs/orchestrator-state.md` is 44.8 KB and
   `docs/opsdir-state.md` 31 KB -- both are read at every generation boot and are history wearing a
   present-tense name. The charter's section 5.1 rule (overwritten, present only) is a form item I own;
   compacting both is cheap and is the first thing a depth-capped harness will feel.

## What I would NOT cut -- concurring with swing, on our own evidence

- **The independent second eye.** Reviewer B at the orchestrator's seat caught the pre-convergence
  merge (cache-read rung), the vacuous prompt-content gate (v16), and refused to fold a null result into
  a pre-registered bin (step 4). Cheap against a ten-round loop.
- **Premise re-derivation before authoring.** Two of this week's tripwire rulings were re-taken on
  corrected premises (the ledger "already exists"; the block-position rule), each before a line of code.
- **Verification at gates only, on disk, never from the self-report.** The seed-2 ledger, read live,
  falsified the cache remedy's premise and found 26% overhead the design pass had not imagined.

## The one thing swing's record could not show us, stated as we measure it

The implementer model was never the question here either: cells are ~38% of weighted spend at both
tiers combined, and their cost is depth x rounds, not the per-token rate. A too-weak cell shows up as
REWORK in the round ledger, which the fill already counts. Compare after the depth cap: if capped cells
converge in the same 5-10 rounds, the cap held and the model question stays closed.

*Adopt what the record supports. The numbers above are ours; the scripts that produced them are two
short read-only passes over the transcripts and can be re-run at any seat.*
