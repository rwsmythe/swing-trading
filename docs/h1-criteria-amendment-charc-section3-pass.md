# CHARC §3 architecture pass — H1 decision-criteria amendment

**Gate:** §3 tripwire CROSSED (new schema). Pre-dispatch architecture pass, per `tool-director-context.md` §3 / `harness-architecture.md` §5.
**Subject brief (RD's, operator-authorized):** [`h1-criteria-amendment-commissioning-brief.md`](h1-criteria-amendment-commissioning-brief.md) — that brief owns the CRITERION TEXT and the research rationale; this document owns the MECHANISM and the binding implementation constraints.
**Verdict:** **GO**, with one binding mechanism change and the conditions below.
**Date:** 2026-07-29. **CHARC generation:** bootstrapped 2026-07-29.

---

## §1 The mechanism ruling — RD's proposal is REJECTED, substitute below

RD's brief §3.1 makes the preservation mechanism CHARC's call and names `status_change_reason` as the cheapest path. **Rejected on three counts, all verified on disk:**

1. **It is destroyed by the next status transition.** `swing/trades/hypothesis.py:268-274` (Step 7) runs `UPDATE hypothesis_registry SET status = ?, status_changed_at = ?, status_change_reason = ? WHERE id = ?` on **every** transition. H1's criterion exists precisely to drive a transition at n=20 (`closed-target-met` / `closed-escaped`) — so the preserved original would be overwritten by the very event it exists to inform, at the moment a reader most needs it.
2. **It fabricates a status change that never happened.** `swing/cli.py:4212-4214` gates on `if h.status_changed_at:` then prints `Status changed:` / `Status reason:`. `swing/web/view_models/metrics/hypothesis_progress_card.py:399-400` renders the same pair. H1's status is and remains `active`.
3. **It breaks audit coherence.** Those columns are the *denormalized current-row view* of `hypothesis_status_history` (the comment at `hypothesis.py:268`; per-row seeds at `0017` and `0026:41-47`). A reason with no corresponding history row makes the denorm disagree with the audit table.

### THE SUBSTITUTE (binding)

**One additive nullable TEXT column on `hypothesis_registry`: `preregistered_decision_criteria`.**

- Populated **for the `A+ baseline` row only**, with the `0008:52` text **verbatim**: `Mean R-multiple > 0; lower-bound Wilson CI on win rate > 30%`
- **NULL semantics are DEFINED and must be documented in the migration header:** NULL means *this row has never been amended; its `decision_criteria` IS the pre-registered text.* NULL does **not** mean "unknown."
- **Rows 2–5 are NOT populated** — this respects RD's §5.3 acceptance bound (`ids 2–5 untouched`). The defined NULL semantic is what makes that safe rather than ambiguous.
- Nothing writes this column at runtime, so it survives every status transition. Pre-registration is a fixed historical fact with exactly one original; no history mechanism is required, and the full amendment chain remains in migration history.

**Operator decision, 2026-07-29: row-level durability is the requirement** — this satisfies RD's §5.2 (*the ORIGINAL text is recoverable verbatim from the row*).

### Considered and rejected

- **`notes`** — documented as operator free-text annotations, already carrying substrate commentary at `0026:27-35`, and mutable. An overload of a field with a different stated purpose.
- **A `hypothesis_criteria_history` child table** mirroring `hypothesis_status_history` — architecturally the most correct, but disproportionate for a governance event that has occurred zero times in three months. Revisit only if amendments recur.

## §2 Scope correction to the brief

**RD's §3.3 ("Data-only, additive. No table/column changes") no longer holds.** This is an additive `ALTER TABLE ... ADD COLUMN` — still additive and low-risk, but it is a schema change, and it carries a mandatory same-commit consequence (§3.1 below).

## §3 Binding implementation constraints

### §3.1 One commit (gotcha #11)
The migration, the model field, and the schema-shape test land **together**:
- `swing/data/migrations/00NN_*.sql` — the `ADD COLUMN` + the two UPDATEs.
- `swing/data/models.py` — `HypothesisRegistry` gains the field (see `:576-577` for the existing nullable pattern).
- **`tests/data/test_db_v8.py:22-27` asserts the `hypothesis_registry` column set with EXACT set equality (`names == {...}`) and WILL FAIL on any added column.** It changes in the same commit. Grep for any other column-set assertion before authoring.

### §3.2 Migration number — take the next free number AT AUTHORING TIME
Do **not** hard-code. `0032` is taken (21-A). As of 2026-07-29 `0033` is free in `main` **and** in both worktrees (`phase21-b-prepared-order`, `phase21-g-provenance`) — but **21-B carries a migration of its own and is still in writing-plans**, so first-to-author takes it. Re-list `swing/data/migrations/` across main and both worktrees immediately before naming the file. (Second collision hazard this phase; the D25 taxonomy rider already had to be renamed off "0032".)

### §3.3 Migration mechanics
- **Wrap in explicit `BEGIN;` … `COMMIT;`** — gotcha #9: `executescript` runs in autocommit and `_apply_migration` does not open its own transaction. `0026:8` + `:50` is the pattern to copy.
- **Target by `name`, not `id`** — `name` is UNIQUE, `0026` targets by name, and `swing/metrics/tier.py:448-472` keys cohorts on name. Use `WHERE name = 'A+ baseline'`.
- **`UPDATE schema_version SET version = NN;`** inside the transaction, per `0026:49`.
- The standard backup gate applies: **strict equality** `pre_version == (target - 1)`, never `<=`.

### §3.4 What is explicitly NOT in this arc
- **D29 — the `entry_intent` reader divergence.** `swing/metrics/cohort.py:103-118` already accepts `entry_intent`; `swing/metrics/tier.py:616` and `swing/web/view_models/metrics/hypothesis_progress_card.py:317` both omit it, so the live surface counts **3** where the amended criterion counts **2** (the third is the pre-epoch `hypothesis_test_by_design` YOU trade). **This is a MEASUREMENT-PATH change — RD's lane, RD's gate. It does NOT ride this migration.** The outgoing RD folded D29 into the H1 gate row: the successor's QA either closes the gap or explicitly carries it; silence is not a third option.
- No change to R computation, the shadow engine, or any measurement path.
- `statement`, `target_sample_size` (stays 20), `status` — unchanged.

## §4 Verified in the brief's favour (do not re-litigate)

- **Nothing gates on the Wilson threshold.** `tier.py:448-472` reads `decision_criteria` and `:756` renders it verbatim as `decision_criterion_evaluation_text`; the shipped answer to "parse or render" was render-only, no automated pass/fail. **`30%` exists in exactly one place — the criterion text at `0008:52`.** There is no Python mirror to keep in sync and no computed outcome can shift. RD's §4 scope bounds hold.
- **`0008`'s own header (lines 7-12) already prescribes this route:** *"A formal amendment requires a NEW migration with an explicit version bump … not an in-place UPDATE."* The governance path was specified in advance.
- **The original is already unconditionally preserved at the RECORD level** — `0008:52`, immutable, git-tracked, unclobberable by any runtime path. The new column adds ROW-level recoverability on top of an already-durable record; it is not the only thing standing between the project and a lost pre-registration.

## §5 RESOLVED — the criterion is stored SINGLE-LINE, pinned by hash

**RD ruled 2026-07-29 (incoming generation): the line wrapping in the brief's §1 block is markdown presentation, NOT criterion content.** RD performed the normalization himself, per PRESERVE-THE-QUOTE — the text is operator-signed and RD-authored, so a downstream editor never normalizes it. Derivation was **mechanical, not retyped**: read the fenced block, strip each line, join on a single space, assert no double space.

**Canonical stored value — length 577, sha256 `6bdd723ce8a8ea1d00b8dbcfa7b50ec056a6282ee3a5110990b2f0894b7b3e73`.**

**CHARC independently reproduced it** from the brief's fenced block by the same mechanical derivation: 8 lines in, **577 characters, sha256 identical**. The constant is verified, not relayed — it is about to become a binding acceptance assertion, and a figure a plan builds on gets traced at the moment it is stated.

**The real fix to what this section originally flagged:** RD's §5 item 1 demanded byte-for-byte equality against a referent that *did not exist as bytes*. **The acceptance test asserts the sha256 (or exact-string equality against the canonical value), never "matches brief §1".** That is what makes it falsifiable.

**Grounds for the ruling (RD, traced on disk):** `0008:52` — the value being replaced — is a single SQL string literal with no embedded newline; `0026:13-25` (the governance precedent this amendment follows) assembles a single-line value via `||` with trailing spaces per fragment; and a grep for `char(10)`/`x'0a'` across every migration returns NONE. A wrapped form would make this the ONLY multi-line criterion in the registry and would differ in SHAPE from the exact text it replaces — corrupting the original-vs-amendment comparison the preservation exists to enable.

**CHARC correction of record:** the HTML-collapse rationale offered in the original version of this section is **NOT load-bearing and was not verified**. RD declined to rest the ruling on a downstream renderer's behaviour — renderers change, the migration record does not. The ruling stands on the registry's own convention. (The original text also said "7-line block"; it is 8 — which is precisely why a line count was never a safe referent.)

## §6 Acceptance additions to RD's §5

RD's five acceptance items stand **with two REPLACED by his own correction (2026-07-29)**: item 1's "matches §1" referent is replaced by the **sha256/exact-string assertion** in §5 above, and item 4 ("migration is data-only; schema tables/columns unchanged") is **FALSE under this pass** — it is an acceptance criterion the correct implementation fails, and RD is correcting it in the brief by replacement. Add:

6. `preregistered_decision_criteria` on the `A+ baseline` row reads the `0008:52` original **verbatim**.
7. The column is **NULL** on ids 2–5, and the migration header documents the NULL semantic.
8. `tests/data/test_db_v8.py` column-set assertion updated in the SAME commit; fast suite green on the merged head.
9. A migrate-twice no-op test (the migration is re-runnable without a second amendment).
