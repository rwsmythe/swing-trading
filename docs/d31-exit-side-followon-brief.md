# D31 exit-side follow-on — the same defect's other half

**Audience:** a fresh Claude Code implementer, no prior conversation context.
**Phase:** **executing** (single dispatch). The design surface is small but real — §4 poses it; decide it in-flight and report the reasoning.
**Base:** `main` @ `83c76ec4` (schema **v35**, suite **10762 / 7 / 0**, ruff clean, pushed).
**Worktree:** `.worktrees/d31-exit` — repo-contained. Never a sibling dir, never `.claude/worktrees/`.

> **This is a FIX-ONLY arc. There is no data to correct and no operator witness on a ledger write.** That is verified below, not assumed — and it is the single most important thing distinguishing this from item 5.

---

## §0 Read first

1. `docs/implementer-dispatch-recipe.md` — the protocol. **§3 changed three times in the last two days**: the scratch-relocation default, the anchored `^tokens used` footer, and count-with-method. Read it; do not run Codex from memory.
2. `CLAUDE.md` — project gotchas.
3. `swing/trades/entry_auto_fill.py` around `:438` and the item-5 arc that fixed it — **this is the same defect and the entry-side fix is your reference**, not your template (see §3).
4. `docs/harness-architecture.md` §5.1 — the discharged-deferral rules; you will be editing claim-bearing comments.

---

## §1 The defect — identical to the entry side, at two sites

**`swing/trades/exit_auto_fill.py:695`:**
```python
date = _extract_iso_date(getattr(o, "enter_time", ""))
```
The **order-entered** time, not the execution time. Character-for-character the entry-side defect that item 5 fixed at `entry_auto_fill.py:438`.

**`swing/trades/exit_auto_fill.py:547`** — the dedupe key carries the same wrong date:
```python
d = _extract_iso_date(getattr(o, "enter_time", ""))
...
return (d, round(float(p), 2), int(q))
```

**It only bites when order-entry and execution straddle a session boundary.** Most exits fill same-day; a resting stop does not. **That case is becoming routine** — the operator now places resting stop-limits at the pivot per the mandate, and three are resting as of this dispatch. The incidence rises as the framework's own discipline becomes habit, which is why this is timely rather than tidy.

---

## §2 Premises verified against the live DB — re-verify anyway

**The live instance, fill 40 (trade 19, FTRE, `action='stop'`):**

| | |
|---|---|
| stored `fill_datetime` | `2026-08-04T16:00:00` |
| `schwab_source_value_json` candidate date | **`2026-08-03`** ← the `enter_time`-derived date |
| `operator_corrected_value_json` | `{"exit_date": "2026-08-04", ...}` |

**The framework proposed the wrong date and the operator caught it by hand.** That is the defect firing in production, already paid for once.

**AND THERE IS NOTHING TO CORRECT.** I enumerated **all 21 non-entry fills** and compared each stored date against its Schwab-sourced date. **Fill 40 is the ONLY one that differs, and it is already operator-corrected.** Every other exit fill either predates the Schwab integration (`schwab_src=None`) or matches exactly.

**So: no correction surface, no ledger write, no migration expected, no data-correction witness.** If your work suggests otherwise, that is a premise break — **STOP and report** rather than building one.

---

## §3 What does NOT transplant from item 5 — read this before reusing anything

Item 5 established a three-row coupled invariant: `trades.entry_date`, the authoritative entry fill's `fills.fill_datetime` date-prefix, and the `reason='entered'` `watchlist_archive.removed_date`.

**That shape does not exist on the exit side. `trades` HAS NO `exit_date` COLUMN.** Verified: the only exit/close-ish columns are `exit_grade` and `last_fill_at`. The exit date lives in `fills.fill_datetime` on the exit fill and derives into `trades.last_fill_at`.

**So the exit-side coupled set is a question you must answer, not a pattern you may copy.** Reusing item 5's invariant by analogy would invent a coupling the schema does not have — and inventing an invariant is worse than lacking one, because the next reader will believe it.

---

## §4 The three decisions this arc must make, and report

1. **What IS the exit-side invariant?** Given no `trades.exit_date`, state the set of rows that must agree, or state plainly that the exit date is single-homed in `fills.fill_datetime` and only *derives* into `last_fill_at`. **Either answer is fine; an unexamined one is not.** State it where the code enforces it, as item 5 did.

2. **The `_compute_signature_hash` perturbation — the real unknown.** The hash consumes **both** `date` and `enter_time` (`exit_auto_fill.py:715-740`) and its docstring says it is *"used downstream for operator-selection round-trip + idempotency."* Changing what `date` means changes every candidate's hash. **Determine whether any signature is PERSISTED and compared across runs.** If a stored signature would be invalidated, that is a data-compatibility question, not a refactor — **STOP and report before proceeding.** If the hash is computed fresh per run and consumed within it, say so with the evidence.

3. **The dedupe key at `:547`.** Correcting the date changes which candidates collapse together. Two orders entered on different days but executing the same day currently dedupe apart and would newly dedupe together — or the reverse. **Work out the direction, and whether it can merge two genuinely distinct fills.** A dedupe that over-merges on the fill path is the silent-false-negative shape RD ruled on for `mappers.py`: the instrument goes quiet rather than alarming.

---

## §5 Scope

**In:** `swing/trades/exit_auto_fill.py` and its tests. **This is a `swing/trades/` carve-out** — the wave's established posture for these arcs; enumerate every file you touch and justify each.

**Out — flag, never fix:**
- The entry side is done; do not re-touch `entry_auto_fill.py`.
- No schema, no migration. If the work seems to need one, **STOP and route back.**
- `audit_service.link_reconciliation_run`'s non-atomicity and the auto-fill envelope's client-editable `schwab_order_id` are both banked from item 5. Not yours.

---

## §6 Conventions

Conventional commits; **no `Co-Authored-By`, no `--no-verify`, no amending**. **Quoted heredoc (`<<'EOF'`) for multi-line commit messages** — an unquoted one ate a word on this wave, and a `Word:` final paragraph parses as a git trailer, so **keep the last paragraph plain prose** (that one cost a history rewrite).

**Frozen-clock convention** for any new date-touching test — this arc is entirely about dates, so a live-clock test here is a false green waiting for a session boundary.

**Verify every claim against the code, including this brief's.** Its numbers are from today and the code governs. **Report every count with the method that produced it.**

**If you discharge a recorded deferral, delete the note as part of the fix — and re-verify every claim it makes, including the ones you intend to keep.** The keeper is the dangerous half; that has cost this project six instances in one week.

---

## §7 Gates

1. Full fast suite **BEFORE** the Codex loop.
2. Codex §3 at the **`strong`** tier to `NO_NEW_CRITICAL_MAJOR` — production code, never tiered down. All four per-round assertions, including the **anchored** `grep -c '^tokens used'`.
3. **Relocate `.codex-*` and `.copowers-findings.md` to the session scratchpad for the loop, restore to the worktree root at the end** — the recipe default; the orchestrator's QA reads them there.
4. `codex-auto-review` via the **cold-audit form**; switch forms if it fails, never skip. Report which ran.
5. **Convergence attaches to the tree that ships.** Changed code after a verdict means re-run.
6. Full fast suite **AFTER** convergence, plus the trailer audit filtered on the trailer **KEY**.

---

## §8 Return report

Final chat message, per recipe §4. **Do NOT run `scripts/role_mail.py`, do not post to any director inbox, never `--from orchestrator`.**

Include: per-task commits; test counts off the FINAL head; Codex rounds with per-round assertions and the findings path; which auto-review form ran; **your three §4 decisions with the evidence and the alternative you rejected**; every constraint stated as honored-on-disk with file:line; the trailer-audit result; and everything flagged-not-fixed.
