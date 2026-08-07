# Wave item 4 — cancel-affordance decoupling + the declined surface + `_PRICE_DP` + the below-pivot refusal

**Audience:** a fresh Claude Code implementer with no prior conversation context.
**Phase:** brainstorming/design is NOT needed — the principles are ruled. This is **writing-plans → executing**.
**Base:** `main` @ `0e36394c` (schema **v34**, suite **10470 / 7 skipped / 0 failed**, ruff clean).
**Worktree:** `.worktrees/item4-cancel-decoupling` — repo-contained, never a sibling dir, never `.claude/worktrees/`.

---

## §0 Read first

1. `docs/phase21-boundary-paydown-commissioning-brief.md` **§4** — the ruled content for this item.
2. `docs/implementer-dispatch-recipe.md` — the protocol SPOF. **§3 is stricter than you may expect** (anchored `^ERROR`, the `tokens used` footer as a fourth assertion, the non-empty redirect check, `bash -lc` for the cold audit). Read it before running Codex, not from memory.
3. `CLAUDE.md` at repo root — project gotchas. You do not inherit any orchestrator context.
4. `docs/harness-architecture.md` §5.1 — the **discharged-deferral** rules and gotcha 31's sibling, both banked TODAY and both live in the files you are about to edit.

**Skill posture:** `superpowers:writing-plans`, then `superpowers:subagent-driven-development` for execution. Do NOT invoke `copowers:*` wrappers — hand-run Codex per recipe §3.

---

## §1 Mission

Four pieces, all in the latch surface. **They are one arc because they share a file family and a quantization**, not because they are one feature.

### Piece 1 — the cancel-affordance decoupling (the governing principle)

RD's ruling `20260803T110020Z` §3: **recording an operator action and alarming on a detected problem are different functions. The affordance to record must not be gated on the alarm that detects.**

- **Q1:** `PENDING_CANCEL` suppression is CORRECT for the alarm and BACKWARDS for the intent affordance. Verified anchors: the broker-state set at `swing/latches/constants.py:171`; the alarm-suppression rationale comment at `swing/web/view_models/latches.py:1765`.
- **Q2:** `ORDER_RESTING_LATCH_CLEARED` must NOT be the sole route to a cancel row. Verified anchors: the alarm kind at `constants.py:202`, emitted at `swing/latches/orders.py:789`.
- **Design the recording surface off the OPERATOR's state, not the alarm set.**

The live instance is on the panel today: LQDA renders `ORDER_RESTING_LATCH_CLEARED (warning)` with "this order matches no latch, so there is no mandate to log a cancel against." That is the erosion the principle exists to stop — the operator placed the order the framework told him to place.

### Piece 2 — the declined surface: render/route **and** flag B's write half

RD, verbatim: *"The render/route goes to item 4, which already owns the governing principle."* Both halves land here; **do not split a feature's read and write across arcs** — that is the interleaving mistake RD named.

- **Read half:** the DECLINE control is currently inside `{% if po.offered %}` at `swing/web/templates/partials/latch_prepared_order.html.j2:20`, so a withheld prepared-order form takes the decline affordance with it. Same defect class as piece 1: an affordance gated on something it should not depend on.
- **Write half (flag B), RD-ruled:** a decline's effective session is **CURRENT at POST, server-computed**. A stale anchor gets the beacon's reject-with-notice. **Backdating must be impossible BY CONSTRUCTION**, not by validation. Note `intent_kind` already carries `"place"`/`"decline"` (`swing/latches/order_intent.py:128`).
- 3a built this affordance, reverted it, and RD signed off routing it here. Item 3b **pinned the current shape** with a test naming what flips when you ship: `tests/web/test_view_models/test_latch_lapse_render.py:273`. **That test is expected to change — it is a cost marker, not a lock.** Plan test **T7.8** (decline survives a withheld form) is yours to satisfy.

### Piece 3 — `_PRICE_DP` to a single source

**Four definitions, count verified across all of `swing/`:**

| file | line | note |
|---|---|---|
| `swing/latches/orders.py` | 40 | as briefed |
| `swing/latches/order_intent.py` | 501 | as briefed |
| `swing/latches/service.py` | **56** | commissioning brief says 41 — **stale, 3a/3b shifted it** |
| `swing/web/view_models/latches.py` | **66** | commissioning brief says 63 — **stale** |

**Re-run the grep yourself before editing.** This exact count went 2→3→4 across three successive people who each grepped too narrowly (the existence-is-not-completeness class). ~30 *consumers* sit behind those four definitions; consolidating the definitions must not change any consumer's behaviour.

### Piece 4 — the below-pivot refusal, with the equality-preservation refinement

`swing/latches/orders.py:156` reads `if round(close, _PRICE_DP) < round(pivot, _PRICE_DP): return BREAKOUT` else `PULLBACK`. The comparison is **strict `<`**, so `close == pivot` currently yields **PULLBACK**.

**The refinement is binding: whatever the refusal becomes, the `close == pivot` disposition must be PRESERVED.** Pin it with a discriminating test that fails if the boundary flips in either direction.

---

## §2 THE INTERACTION TO WATCH — read this before planning

**Pieces 3 and 4 touch the same quantization.** The below-pivot boundary is decided by `round(..., _PRICE_DP)`; piece 3 moves where `_PRICE_DP` comes from. A consolidation that changes the value, the rounding site, or the import timing can flip breakout/pullback at exactly the equality boundary piece 4 is protecting. This is the quantization-divergence area — that is *why* the commissioning brief paired them.

**CHARC's artifact-scale watch is attached to this arc:** if your findings cluster as **INTERACTIONS BETWEEN the pieces** rather than defects **within** them, **say so and propose the split.** That is an available outcome and an expected one — not a failure, and not something to push through. Two honest non-convergence reports beat one claimed convergence; that has already happened twice on this wave and both times the reporter was right.

---

## §3 Scope

**In:** `swing/latches/*`, `swing/web/view_models/latches.py`, `swing/web/routes/latches.py`, `swing/web/templates/partials/latch_*`, and their tests.

**Out of scope — flag, never fix inline:**
- `swing/data/` and `swing/trades/` are **READ-ONLY**. No carve-out is granted. The known duplicate-bar collapse at `swing/data/ohlcv_archive.py:964` is a *flagged* item, not yours.
- No schema. **If the design grows a migration, STOP and route back** — that is a condition-4 tripwire, not a judgment call.
- No new dependency, no new module without saying so.
- Latch-on-acceptance for hyp-rec offers is **Phase-22**, not this arc, however tempting LQDA makes it.

---

## §4 Binding conventions

- Conventional commits. **No `Co-Authored-By` footer. No `--no-verify`. No amending.**
- **Use a QUOTED heredoc (`<<'EOF'`) for any multi-line commit message.** An unquoted one silently swallowed a word in `085b0c34` on this very wave.
- TDD: failing test → minimal implementation → pass → commit.
- **Frozen-clock convention** for any NEW date/session-touching test.
- **Verify every claim you make about the code against the code** — including the anchors in this brief. Two of its line numbers were already stale when I wrote it; assume more have drifted by the time you read it. Cite a content search (`git log -S'...'`), never a bare SHA, for anything that must survive a rebase.
- **A deliberate not-fixed on a director-banked item goes in the RETURN'S FLAGGED LIST**, not only a code comment. A comment is where reasoning lives; the flagged list is where the obligation lives.
- **If you discharge a recorded deferral, delete the deferral note as part of the fix** — and re-verify EVERY claim that note makes against the symbols it names, *including the claims you intend to keep*. Both files you are editing carried exactly this defect this week; the keeper is the dangerous one.

---

## §5 Gates

1. Full fast suite **BEFORE** the Codex loop (catches cross-cutting invariants per-task TDD misses).
2. Codex **§3 `strong` tier** to `NO_NEW_CRITICAL_MAJOR` — production code, never tiered down. All four per-round assertions, recorded in `.copowers-findings.md`.
3. `codex-auto-review` via the **cold-audit form** (`codex exec review` is unusable from a worktree — `Not inside a trusted directory`, no flag to bypass). If your first invocation fails, switch forms; **never skip**. Report which form ran.
4. **Convergence attaches to the tree that ships.** If you change code after a convergence verdict, re-run — a verdict on a diff that is no longer the diff proves nothing. That rule earned its place on 3b, where R8 found a MAJOR inside the R7 fix.
5. Full fast suite **AFTER** convergence, plus the trailer audit filtered on the trailer **KEY**.

Then: orchestrator QA on disk → **RD merge-blocking** (the classification consequences of new cancel rows) → **operator witness**.

---

## §6 Return report

Your final chat message, per recipe §4. Do **NOT** run `scripts/role_mail.py`; do NOT post to any director inbox; never use `--from orchestrator`. You report to the orchestrator in chat and nowhere else.

Include: per-task commits; test counts read off the FINAL head; Codex rounds with per-round model/effort/footer plus the findings path; which auto-review form ran; each binding constraint stated as honored-on-disk with file:line; the trailer-audit result; **and the artifact-scale judgment — did the findings cluster within pieces or between them?**
