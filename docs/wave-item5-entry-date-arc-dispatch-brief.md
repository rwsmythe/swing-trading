# Wave item 5 — the entry-date arc (D31 + A-4), with RD's two later riders

**Audience:** a fresh Claude Code implementer, no prior conversation context.
**Phase:** **writing-plans**, then executing. The principles are ruled; the design is not.
**Base:** `main` @ `6c109047` (schema **v34**, suite **10516 / 7 / 0**, ruff clean, pushed).
**Worktree:** `.worktrees/item5-entry-date` — repo-contained. Never a sibling dir, never `.claude/worktrees/`.

> **This is the highest-risk item of the wave.** It **writes to the live ledger** (a retro-correction of a real closed trade) and it **crosses a schema tripwire** (a CHECK-enum widening requiring a table rebuild). Nothing else in this wave did both. Plan accordingly; the cell is `opus-xhigh` for exactly this reason.

---

## §0 Read first

1. `docs/phase21-boundary-paydown-commissioning-brief.md` **§5** — the ruled content and CHARC's §3 pass.
2. `docs/implementer-dispatch-recipe.md` — the protocol. §3 governs the Codex loop.
3. `CLAUDE.md` — project gotchas. **#11 (schema-CHECK + Python-constant + validator in ONE commit) is the governing gotcha for A-4**, and #30 is adjacent.
4. `docs/harness-architecture.md` §5.1 — the discharged-deferral rules; you will be editing comments that enumerate things.

---

## §1 What this arc is

RD's ruling `20260801T145327Z`, three parts plus a rider:

1. **D31 — the mapper takes the EXECUTION timestamp**, not the order-entered time. The discrepancy path already reads `execution_legs` correctly (`swing/trades/reconciliation_classifier.py:265`; `swing/trades/schwab_reconciliation.py:610 _execution_legs_payload`) — the defect is in what the mapper writes to `trades.entry_date`.
2. **An audited entry-date correction surface** — the D19 / cash-void precedent: audited override, append-only, reason-required. **Follows the cash-void NO-SCHEMA precedent unless your plan shows otherwise. If it needs schema, that is a SCHEMA-STOP: route back, do not build it.**
3. **Retro-correct trade 19 to 2026-07-31** under that surface. Discrepancy 95 then closes **honestly** — **never via `mark_unmatched`, which would write a false statement into the ledger.**
4. **A-4 rides:** a dedicated `fills_trades_price_divergence`-class `discrepancy_type`.

---

## §2 Premises I verified against the live DB and the code — use these, re-verify them anyway

| premise | verified state (2026-08-08) |
|---|---|
| Schema version | **v34** (`schema_version` table — NOT `PRAGMA user_version`, which reads 0) |
| **Trade 19** | `ticker=FTRE`, **`entry_date=2026-07-23`**, `state=closed`, `entry_price=18.8`. The correction is 07-23 → **07-31**, an **8-day** move on a **closed** trade |
| **Discrepancy 95** | `discrepancy_type=entry_price_mismatch`, `trade_id=19`, `ticker=FTRE`, `field_name=price`, `resolution=pending_ambiguity_resolution`, `material_to_review=1`, **`delta_text="$+0.0000 (schwab execution minus journal)"`** |
| A-4's CHECK | `reconciliation_discrepancies.discrepancy_type`, currently **11 values**. Widened 10→11 at **`0031_untracked_broker_position.sql`** by **TABLE REBUILD** — SQLite cannot drop a CHECK, so **`0031` is your verbatim precedent** |
| Enum mirrors | `swing/trades/reconciliation.py:46 DISCREPANCY_TYPES` · `swing/data/models.py:1099 _DISCREPANCY_TYPES` · `swing/trades/reconciliation.py:99 MATERIAL_BY_TYPE` · the migration CHECK. **All three Python mirrors agree at 11 and are the same set today** |

**The `$+0.0000` delta is the arc's live evidence.** Discrepancy 95 is typed `entry_price_mismatch` and the prices match *exactly*. It is **mistyped** — the real divergence is the date, and the type vocabulary has no word for it. That is what A-4 exists to fix, and it is why closing 95 as a price mismatch would be a lie.

**On the mirror count — the discipline this wave was built on.** The comment at `reconciliation.py:41-45` names **four** mirrors. A search by member *value* (`untracked_broker_position`) hits **ten files**: `cli_schwab.py`, `config.py`, `data/db.py`, `data/models.py`, `data/repos/reconciliation.py`, `metrics/discrepancies.py`, `trades/reconciliation.py`, `trades/schwab_reconciliation.py`, `web/routes/reconcile.py`, `web/view_models/reconcile.py`. Not all are mirrors. **Establish the real set by READING each one; a token grep bounds the family from below and nothing more.** This exact class produced four wrong counts in this wave alone (`_PRICE_DP` 2→3→4, the recipe residual 1→2→4, D29 2→4, a false-claim manifest 5→6→7) — every one short until someone stopped matching and started reading, and every time the person holding the smaller number had no reason to doubt it. **Report your count with the method that produced it.**

---

## §3 RD's two later riders — both land here

**Rider 1 — `swing/integrations/schwab/mappers.py:285`, RD-ruled 2026-08-09.** A legless-order skip drops an order silently: `continue` + `logging.warning`, no count returned, nothing reaching `warnings_json` or any reconciliation audit row. It feeds `get_account_orders` → `swing/integrations/schwab/pipeline_steps.py:523` — **nightly reconciliation Pass 2**. A dropped occurrence is a **false negative on a fill**: reconciliation sees no fill, raises no discrepancy, reports clean. **The instrument does not alarm; it goes quiet.**

**RD's ruling, verbatim in substance:** the minimum fix is **COUNT-AND-SURFACE, not stop-skipping.** Refusing to skip would fail the whole orders fetch on a legitimately legless parent-conditional row — that resilience is correct. What is wrong is that the skip is **invisible**. Return the skip count (and the skipped order ids) and surface it in the reconciliation's own warning envelope so an absence renders as a **labelled gap** instead of a clean pass. This is CLAUDE.md **gotcha #27** in a Schwab mapper rather than a pipeline step. **RD is explicitly not asserting an incidence rate** — the ruling rests on the asymmetry, not a number.

**Rider 2 — the D-2b framing correction.** Item 4 deferred the cancel→place attribution chain here. **Do NOT inherit the phrase "every hop is schema-guaranteed"** — I wrote that in item 4's delta, it came from RD's ruling, and **it is false**. Verified: `0033` has exactly two UNIQUE constraints — `(candidate_id, view_session_date, surface)` and `(idempotency_key)` — and **neither is on `actual_broker_order_id`**. The *last* hop is guaranteed; the *first* is not, so hop 1 can match **zero or several** rows. Any design here needs a defined answer for the zero-match and multi-match cases. That is design work, not plumbing.

---

## §4 Binding constraints

- **`swing/data/` and `swing/trades/` carve-outs ARE in scope here** — unavoidably, since this is a ledger correction plus a migration. Enumerate every file you touch in the plan and justify each.
- **Gotcha #11 binds A-4:** the CHECK, every Python mirror, and the validator land in **ONE commit**. SQLite cannot drop a CHECK — follow `0031`'s rebuild verbatim.
- **The migration backup-gate uses STRICT equality** `pre_version == (target - 1)`; copy the Phase-9 clause shape.
- **Never `mark_unmatched` on discrepancy 95.** It would write a false statement.
- Conventional commits; **no `Co-Authored-By`, no `--no-verify`, no amending**. **Quoted heredoc (`<<'EOF'`) for multi-line commit messages** — an unquoted one silently ate a word on this wave.
- **Frozen-clock convention** for any new date-touching test. This arc is *entirely* about dates; a live-clock test here is a false green waiting for a DST boundary.
- **A deliberate not-fixed on a director-banked item goes in the RETURN'S FLAGGED LIST**, not only a code comment.
- If you discharge a recorded deferral, **delete the note as part of the fix — and re-verify every claim it makes, including the ones you intend to keep.** The keeper is the dangerous one; that has now cost this project five separate instances in one week, one of them steering live CSS.

---

## §5 What the plan must decide, not assume

1. **The correction surface's shape** — CLI, web, or both; how the audit row is written; how append-only is enforced. Cite the D19 / cash-void precedent and show where you are following it and where you are not.
2. **What "closes honestly" means for discrepancy 95** in concrete terms — which resolution value, which reason text, and why that is a true statement about what happened.
3. **Whether correcting a CLOSED trade's entry_date has downstream consequences** — derived metrics, R-multiples, hypothesis attribution, the H1 cohort. **RD's sequencing note: item 5 and D29 are order-independent EXCEPT both precede any H1-consuming read (September).** If the correction moves a number RD reads, say so in the plan; it is his gate.
4. **A-4's exact type name and its `MATERIAL_BY_TYPE` value** — the latter is a materiality judgment, so pose it to RD rather than choosing silently.

---

## §6 Gates

Pre-review full suite → Codex §3 at the **`strong`** tier to `NO_NEW_CRITICAL_MAJOR` (all four per-round assertions recorded) → `codex-auto-review` via the **cold-audit form** (`codex exec review` is unusable from a worktree; switch forms, never skip) → post-convergence suite + trailer audit filtered on the trailer **KEY**.

**Convergence attaches to the tree that ships.** If you change code after a convergence verdict, re-run. On this wave a MAJOR was found inside the previous round's fix **five** times.

Then: orchestrator QA → **RD merge-blocking** (H1-cohort data correction — his lane twice over) → **operator witness** (the retro-correction of his live trade and discrepancy 95 closing).

---

## §7 Return report

Final chat message, per recipe §4. **Do NOT run `scripts/role_mail.py`, do not post to any director inbox, never `--from orchestrator`.** Include: per-task commits; test counts off the FINAL head; Codex rounds with per-round assertions and the findings path; which auto-review form ran; **your mirror count and the method that produced it**; every constraint stated as honored-on-disk with file:line; the trailer-audit result; and everything flagged-not-fixed.
