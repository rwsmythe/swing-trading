# Orchestrator handoff — 2026-09-08 — 22-A4 B-READY, and B has not run

**Supersedes** `orchestrator-handoff-2026-09-08-22a4-fork-ruled.md` (same UTC date, earlier generation).
**From:** the generation that took 22-A4 from the fork-fix dispatch through the R3-03 structural leg
and the round-4 residuals leg, with four counted Codex rounds behind it and none converged.
**Rolled at 322,093** (measured, `python scripts/cell_depth.py --sessions --live 1`), deliberately
BELOW the 400K trigger, at an operator-named boundary: nothing in flight, no ruling outstanding, the
next action defined and undispatched. **Both directors rolled ahead of me for the same reason** — the
merge gate deserves a full budget, not a remainder.
**Bootstrap:** `scripts/orchestrator_bootstrap.md` → `docs/orchestrator-context.md` → this file.

**Every fact here was re-derived from disk at write time, method stated. Do the same.**

---

## 1. YOUR FIRST ACTION — run B. It has not run, and the arc cannot merge without it.

**B is `codex-auto-review`, the STANDING required second eye. It is NOT the orchestrator reading the
diff.** Charter §2.9 defines it; `harness-architecture.md` §5.1 makes CHARC's merge gate REQUIRE its
transcript. **Read those two, do not take this paragraph as the definition** — the previous handoff
said *"reviewer B (your own second eye)"* and I read "your own" as licensing a hand review, claimed
B COMPLETE, and was corrected by CHARC, who checked the durable directory and the ledger rather than
taking my word. **A handoff can carry a NAME forward intact while its DEFINITION stays behind in the
charter.** That is why this section points instead of paraphrasing.

**What satisfies the precondition (CHARC, 2026-09-08, verbatim-in-substance — his message is in
`comms/orchestrator/read/`, which is gitignored, so the operative requirements are transcribed here):**

- ONE `codex-auto-review` pass with repo access, at **matched-high effort**, over **`84e90bab`** or
  whatever head the trailer reword produces.
- **From a worktree, use the COLD-AUDIT form per recipe §3** — `codex exec review` refuses a worktree.
- Transcript copied to `~/swing-data/review-transcripts/22-a4-exec/`, carrying **the same five
  mechanical assertions the A rounds carry** (model, effort, `^ERROR`, `tokens used` footer, anchored
  verdict token).
- Every finding **dispositioned under introduced-vs-banked**.
- **A ledger section naming it.**

**"B is NOT required to return clean; it is required to have RUN on the merge tree."** That sentence
is CHARC's and it is here because a successor under budget pressure is exactly who would read a dirty
B as a failure and hesitate.

**My hand review — composition read, one mutant applied, one finding against my own brief — stands and
should be CITED BESIDE B, never instead of it.**

**Verified at write time:** `ls ~/swing-data/review-transcripts/22-a4-exec/` holds the r1–r4 **A**
transcripts and **no B**; the committed ledger has zero mentions of `codex-auto-review`.

## 2. STATE, re-derived at write time

- **`main` @ `7a9d14ad`** (RD's state commit; my last was `07bd904e`), tree clean, **27 commits ahead
  of origin, UNPUSHED** (counted, not remembered).
- **Branch `22-a4-exec` @ `84e90bab`**, worktree `.worktrees/22-a4-exec`, **clean**, **25 commits
  above `2d9e4a34`**.
- **Trailer sweep over the whole arc** (`%(trailers)`, filtered on non-empty): exactly ONE —
  `b3b518f9`'s `Tests:` paragraph. **`Co-Authored-By` key count = 0.** The streak is not at risk.
- **No cell in flight.** Two finished cells on the gauge (296,406 and 249,809), both returned and QA'd.
- **Live schema v37; migration 0038 UNAPPLIED — inherited, NOT re-measured by me. RE-VERIFY AT THE
  GATE**, before the witnessed migration.
- `.worktrees/22-a4-plan` @ `f5e03921` still on disk, unused this generation.

## 3. THE LADDER FROM HERE

**B** (§1) → **the `b3b518f9` trailer reword** (recipe §2 assigns it to the orchestrator; amend, the
branch is unpushed so no force is needed; keep the final `-m` paragraph plain prose and re-run the
sweep after) → **the merged-head `-n auto` suite run IN THE OPERATOR'S SHELL** → **the merge request**
→ **both director gates** → **S9 step 0, a BLOCKING live pipeline run** → **the operator-witnessed
0038 migration**.

**On the suite run: `-n auto` is killed for memory IN THIS SEAT.** The operator has agreed to run it
in his. **Every 22-A4 number from Task 4 to the R3-03 leg was an `-n 4` number**; the last two cells
ran `-n auto` at 16 workers successfully in THEIR seats, so the flake class has been probed on the
branch head — but **the binding merged-head run is still owed** and it is not a number you may carry
forward from a cell.

**RD's successor's gate has seven checks, three merge-blocking on measurement integrity:** the locked
functions by AST, the tier-3 zero-write assertion across all seven spellings, and the `(id, ticker)`
contract. All three are already measured on this branch — the gate will be re-checking work that
exists, not asking for it late.

## 4. AUTHORITIES I GRANTED — the record, because a cell message is not one

- **THE FOURTH COUNTED ROUND: authorized in writing**, named on the task-bearing finding
  **`A4X-R3-03`**, written after reading the outgoing cell's depth (320,695). **It is committed as §1
  of `docs/22-a4-r3-03-structural-leg-dispatch-brief.md`, not passed in a cell message** — a grant is
  STATE. It ran; it did not converge.
- **NO FIFTH counted round was authorized, and none is outstanding.** Round 4 cleared production (zero
  critical, zero major against `swing/`); its four majors were tests, comments and docstrings. CHARC
  concurred on the RULE, not the budget: the scope-of-the-change rule says suite-verified fix, not a
  round. RD's settling-shape endorsement applies. **If B returns task-bearing production work, a fifth
  counted round needs YOUR fresh written authorization naming it.**
- **Scope grants:** the fork-fix leg, the R3-03 structural leg, and the residuals leg, each as its OWN
  cell. All three returned, all three QA'd against disk, all three posted to both directors.
- **One inline fix by me, not a grant:** `A4X-R4-03` at `84e90bab` — comment-only, proven by diffing
  out every comment line, 195 tests green on the two touching files.
- **NO envelope widening. NO mid-round fix authorization. Nothing outstanding from me.**
- **Cells used:** fork-fix `implementer-opus-high`; R3-03 structural `implementer-opus-high` (the
  must-converge-Codex exception); residuals `implementer-sonnet-high` (the 2026-09-07 default, no
  notch moved). Review tier `strong` throughout.

**Landed rulings this generation, all transcribed into git because `comms/` is gitignored:**
RD — the item-1 withdrawal (the "rendered into the degraded warning" clause is FALSE about the code;
the log record is the channel; no code change; requirement met as it stands). CHARC — `A4X-R3-03` is
**INTRODUCED**, the fix is structural, byte-exact-first on every corrector path, the normalizer
DELETED; `A4X-R3-04` in-leg; no fifth round; the backup-gate formula ruled from the TEXT end.
CHARC — the B precondition (§1). **CHARC's correction of his own severity finding is appended BENEATH
his block quote at `28ec7950`, at his direction — his words unedited, the correction attributed
underneath.** That form is now the convention: see `orchestrator-context.md` posting rule 4.

## 5. WHAT WILL BITE YOU

- **`git diff --stat` ON `entry.py` READS LIKE A LOCK BREACH AND IS NOT.** Across the arc it shows
  ~123 insertions — the fork-fix leg's legitimate `_settle_by_attempt_identity` work. **Measure the
  three locked functions (`_entry_transaction`, `_durability_probe`, `record_entry`) by AST SOURCE
  SEGMENT sha256 against `a32ea9d5`.** All three are IDENTICAL at `84e90bab`; I verified this three
  separate times. This trap has already caught one reader.
- **`git … | grep -c` returns exit 1 on zero matches** and silently skips the rest of an `&&` chain.
  Use `;`.
- **`role_mail.py` resolves comms root from the SCRIPT's repo.** The Bash tool's cwd drifts into the
  worktree constantly in this arc. **`cd` to the main repo in the SAME invocation and verify delivery
  on disk** — the `posted ->` line reads identical on a misdelivery. Subject cap 80 chars; use
  `--body-file` always.
- **Write long message bodies with the Write tool, not a heredoc** — apostrophes in prose broke a post
  for a previous generation.
- **Plan/brief line anchors have drifted hard across this arc.** Ground on symbols, re-locate at read
  time. My own R3-03 brief's line numbers were correct-but-incomplete (see §6).

## 6. WHAT I GOT WRONG — three, and two share a class

1. **"REVIEWER B COMPLETE" and "the arc is merge-ready."** Both false, both retracted. I filled a term
   of art with its ordinary-language meaning without reading the definition. §1 exists so you do not
   repeat it.
2. **My R3-03 brief stated a BOUND as a TOTAL.** It said *"at BOTH corrector call sites"* and listed
   two; measured at `df231195`, `_refuse_immutable_journal_fields` had **THREE** — and the one I
   omitted, `:1791`, was the tier-3 head, **precisely the path whose pre-fix writes persisted**. No
   defect shipped: the cell established the sites *"by reading all five public defs and every caller —
   not by grep"*, and my brief told it not to trust my numbers.
3. **That bounded-search-as-total is this arc's most-repeated class — three instances in three days,
   from three different seats:** Codex's tier-3 ordering claim (flagged unverified, later CONFIRMED by
   execution), CHARC's severity assessment (read two barriers, generalised to the path, self-corrected
   on the record), and my seam. **I do not think another rule fixes it. The cell's method did:
   enumerate the callers; do not grep the guard.** Offered to CHARC as register material, not proposed
   as a rule — this arc has enough rules and one working method.

## 7. WHAT THIS GENERATION IS WORTH REMEMBERING FOR

**The instruments kept catching things, and kept catching them from the inside.** Round 3 caught the
fork-fix leg's own false declaration sentence — *the exact alarm text RD's ruling required be removed,
surviving one statement further along*. Round 4's closure test **settled Codex's tier-3 write-ordering
claim by execution and found it stronger than anyone's estimate**: three spellings each persisted a
correction row, advanced the ledger head's supersession pointer, and updated an unrelated `trades`
column — which **falsified CHARC's own "not a write" assessment**, in a ruling of record, and he owned
it within the hour.

**Two cells stopped short rather than dress a loop as converged, and both were right.** Four counted
rounds, none converged; the arc reaches its gate honestly labelled.

**And the QA earned its keep by performing rather than reading:** I applied the `:2745` mutant myself
and got exactly the promised discrimination — 7 failed, 24 passed, every failure an `(m8g)` row.

## 8. QUEUE BEHIND 22-A4

In `docs/phase3e-todo.md`: the version-mirror rename rider (**trigger: AFTER the merge**), the
round-4 out-of-scope catches, and the backup-gate formula class — the last now **discharged from the
text end**: the CLAUDE.md gotcha asserted two different rules in one sentence and was corrected at
`25870c42`, then compressed to trigger+fix with its forensic split to `docs/CLAUDE.md-archive.md`
§"Appended 2026-09-08" at `07bd904e` when it tripped the ~700-char cap. The 19 `swing/data/db.py`
docstrings now cite a rule that is true and **need no repaint** — CHARC's ruling, and the reason that
end was chosen.

Then D46, D45, D44/D47, the D39 sweep, D42's export failure, and `ReservedJournalFieldError`'s
bare-`Exception` base (D34's third instance).

**The admitting gate stays open: 131 post-barrier candidates, zero A+. Open trades: 23 CADL
(partial_exited), 24 RHI, 25 OII, 26 NRIX, 28 PBF. Real money.**
