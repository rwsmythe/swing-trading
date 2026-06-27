# Commissioning Brief — Cash-Movement Void Command (`swing journal cash-void`)

**Commissioned by:** CHARC (Tool Development Director)
**Date:** 2026-06-21
**Arc:** the cash-ledger correction affordance (register **D19**), NO-SCHEMA scope (operator-chosen 2026-06-21).
**Status:** COMMISSIONED — CHARC §3 architecture pass = **GO** (two additive carve-outs; **NO schema**). Awaiting operator writing-plans dispatch.
**Tripwires crossed:** phase-isolation carve-out into `swing/trades/` (the step-7 matcher `void:` self-source branch) + `swing/data/` (a `find_by_id` read helper on the cash repo) — both **additive/guard-only**. **NOT crossed:** new schema/migration, new module/package, new dependency, new standing process. **Measurement-core** (the cash ledger feeds `current_equity`) → **RD measurement-integrity QA is MERGE-BLOCKING.**

---

## §0 — Decision of record (the cash-ledger affordances scope, operator 2026-06-21)

From RD's cash-ledger-correction-gap flag (+ the live $372.48 SPCX double-debit), the operator chose **Option A: the NO-SCHEMA void** over Option B (a bundled `origin`-column schema arc).
- **D19 (the void affordance) → THIS ARC** — a `void:<id>` ref-sentinel + an additive matcher branch, mirroring the just-witnessed OOF arc. No migration.
- **D17 (the `origin`/`source` provenance column) → DEFERRED + PREMISE-CORRECTED.** CHARC had registered D17 as "closeable by a schema `origin` column" — **that is wrong**: a raw out-of-band INSERT forges an `origin` column exactly as easily as an `oof:`/`void:` ref, so the column does NOT close the raw-write vector (a trust-the-repo-boundary limitation, not column-closeable). The column's real value is **provenance/legibility**, NOT measurement-integrity, and the void needs nothing from it. D17 is re-scoped as a legibility candidate (Phase-18-close or later); it is OUT of this arc.

---

## §1 — Problem (the gap + the live instance)

`cash_movements` is append-only, insert-only — `swing/data/repos/cash.py` is `insert_cash`/`list_cash`/`find_by_ref` only; there is NO void/delete/correct path. An erroneous/duplicate/superseded `cash_movement` (a fat-finger amount, a re-record) is fixable ONLY by a raw out-of-band DB DELETE. **Live instance 2026-06-21:** re-recording SPCX via `oof-buy` (to get the self-reconciling `oof:` ref) ADDED a row atop the un-deletable manual id 5 → a **$372.48 double-debit** of the swing ledger; RD corrected it via a backed-up scoped raw delete. **Measurement-relevant:** an uncorrectable cash error corrupts `current_equity`, which §2.4 coherence + position-sizing read — the double-debit would fire a real `equity_delta` every recon until raw-deleted.

---

## §2 — Verified grounding (CHARC, on disk — do NOT re-derive)

- **Equity composition (CHARC-verified myself):** `swing/trades/equity.py:25-45` — `net_cash_movements` sums by kind (`deposit`/`interest`/`dividend` ADD; `withdraw`/`fee` SUBTRACT; unknown RAISES; **NO origin/ref/kind filter**); `current_equity = starting + realized + net_cash_movements`. So a REVERSING entry — a `deposit` of $X voiding a `withdraw` of $X (or the symmetric cases) — nets to **exactly 0** and restores `current_equity`. The void needs nothing but a real reversing row.
- **The self-source template:** `swing/trades/schwab_reconciliation.py:1931-1934` — the step-7 `oof:` self-source branch (`kind=='withdraw'` AND `_oof_ref_ticker(cm.ref)` in `out_of_framework_set` → skip the `cash_movement_mismatch` emit). Predicate `_is_oof_sentinel_ref` (`:324-334`), regex `_OOF_REF_RE` (`:257`), `_OOF_REF_PREFIX` (`:225`). The `void:` branch mirrors this shape.
- **The cash repo:** `swing/data/repos/cash.py` — `insert_cash` / `list_cash` / `find_by_ref` only; **no `find_by_id`, no delete/void**.
- **Schema:** `cash_movements` (migration 0029) = `(id, date [ISO-GLOB], kind [5-enum: deposit/withdraw/interest/dividend/fee], amount REAL ≥0, ref TEXT nullable, note TEXT)`; unique partial index `ux_cash_ref ON ref WHERE ref IS NOT NULL`. `ref` is free-form (no format CHECK) → a `void:` sentinel is schema-legal AND gives idempotency.
- **No existing affordance:** grep-confirmed (RD + CHARC) — NO cash void/delete/correct anywhere in `swing/` (repo, CLI, web).

---

## §3 — CHARC architecture pass (GO)

| Tripwire | Crossed? | Disposition |
|---|---|---|
| New schema | **NO** | The `void:` ref-sentinel reuses the free-form `ref` column; NO migration. |
| New module/package | **NO** | A new CLI subcommand + a matcher branch + a repo read-helper, all in existing modules. |
| New external dependency | **NO** | — |
| New standing process | **NO** | An operator CLI command. |
| Phase-isolation carve-out | **YES → AUTHORIZED (two, both additive/guard-only)** | (1) `swing/trades/schwab_reconciliation.py` — the step-7 `void:` self-source branch (additive; non-void rows byte-unchanged). (2) `swing/data/repos/cash.py` — a `find_by_id` READ helper (additive; the void WRITE reuses the existing `insert_cash`, no new write function). Mirrors the OOF arc's carve-out posture. |

**Measurement-core:** the cash ledger feeds `current_equity` → **RD measurement-integrity L-checklist is MERGE-BLOCKING**; the §5 composition test (void restores `current_equity`) is the binding artifact.

---

## §4 — Design contract

**The command** — a sibling under the `journal` group (exact name a writing-plans detail; `journal cash-void` or `journal void`):
```
swing journal cash-void <cash_movement_id> --reason <text> [--date YYYY-MM-DD]
```
- **Fetch + validate** the original via a new `find_by_id` cash-repo helper. REJECT (clear `ClickException`) if: id not found; the target is ALREADY voided (a `void:<id>` row exists — fail-loud, the idempotency); or the target is ITSELF a void entry (`ref` starts with `void:` — no void-of-a-void in V1).
- **Records a REVERSING `cash_movement`:** `kind` = the equity NEGATION of the original — **`deposit`** if the original SUBTRACTS (`withdraw`/`fee`), **`withdraw`** if the original ADDS (`deposit`/`interest`/`dividend`); `amount` = original.amount; `ref` = `void:<original_id>`; `note` = `VOID #<id>: <reason>`. This nets the original to 0 on the ledger (§2-verified). The WRITE reuses the existing `insert_cash`.
- **Self-source (the carve-out):** step-7 matcher ADDS a `void:` branch — a `_is_void_sentinel_ref(cm.ref)` → SKIP the `cash_movement_mismatch` emit (a void row has no Schwab counterpart). Mirrors the `oof:` branch; additive/guard-only (non-void rows byte-unchanged).
- **Idempotency FAIL-LOUD (the RD course-correction lesson from the OOF arc — bake it in from the start):** a `void:<id>` collision (already voided) → REJECT with an actionable `ClickException` (name the existing void row), NEVER a silent no-op. The `ux_cash_ref` unique index is the belt.
- **Namespace reservation:** reserve the `void:` ref-prefix at the other free-form-ref writers — `journal cash` `--ref` rejects a `void:` value; TOS import neutralizes a `void:` REF# to ref-less — so a NON-void row can never carry a `void:` ref (the self-source Lock-1 hole; mirrors the OOF arc's `oof:` reservation).
- **Sandbox gating:** `cash_movements` is a DOMAIN row → under `environment != "production"` the void insert short-circuits (audit-only echo, no row). Mirror the OOF arc.
- **`--reason` REQUIRED** (non-empty; the audit trail lives in the `note`).

---

## §5 — Test obligations

- **Composition test (BINDING, RD):** void an erroneous `withdraw` of $X → `current_equity` is RESTORED (the reversing `deposit` nets the pair to 0). PRE-fix (no void) the ledger is −$X. Real-derived inputs, never values built to satisfy the premise (memory `feedback_verify_premise_arithmetic_vs_live`). Cover the symmetric case (void a `deposit` → a `withdraw`).
- **Self-reconcile test:** the void row does NOT fire `cash_movement_mismatch` across a reconciliation run — and the test FAILS if the `void:` matcher branch is absent (assert the void row is skipped AS self-sourced, not merely that some row matched).
- **Idempotency fail-loud:** voiding the same id twice → `ClickException` + no double-record (distinguishes silent-no-op from fail-loud — the I1 shape from the OOF arc).
- **Reject tests:** non-existent id → error; already-voided id → error (names the void row); a void-of-a-void → error.
- **Reversing-kind table:** each original `kind` → the correct negating `kind` (withdraw/fee→deposit; deposit/interest/dividend→withdraw).
- **Namespace reservation:** `journal cash --ref void:...` → rejected; TOS import neutralizes a `void:` REF#.
- **Sandbox:** no domain row written under sandbox (audit-only); a parallel production case writes one.
- **Live-DB-shape discipline** (§5.10) + **ASCII-only** user-facing strings (the Windows cp1252 gotcha).

---

## §6 — Gates (all binding)

- **Codex review-strong** (gpt-5.5/high, repo-access) to CONVERGENCE + **codex-auto-review** (matched-high).
- **RD measurement-integrity L-checklist — MERGE-BLOCKING** (the cash ledger is measurement-core).
- **Operator §5.10 live-witness — BINDING (CLI):** seed an erroneous cash row → `cash-void` it → witness (a) `current_equity` restored, (b) a recon does NOT fire a `cash_movement_mismatch` for the void row, (c) re-voiding the same id fails loud, (d) voiding a non-existent/already-voided id is rejected. (Use a throwaway seed + clean up — the ZZTEST/ZZWIT pattern.)
- **Before-review full-suite run + `ruff check swing/` clean.**

---

## §7 — Out of scope / follow-ups

- **The `origin`/`source` provenance column (D17)** — DEFERRED + re-scoped as legibility (NOT a raw-write closure); a Phase-18-close candidate. NOT this arc.
- **"Correct/amend" an amount** — V1 = `void <id>` + a fresh `journal cash` entry (two steps); a combined `correct` command is a future nicety.
- **Void-of-a-void** — rejected in V1 (keeps the chain flat).

---

## §8 — Return report

The **ORCHESTRATOR** posts the return report to `charc` (+`rd`) **AFTER its own QA gate**. The implementer reports to its orchestrator in chat; it NEVER posts to a director inbox (memory `feedback_implementer_never_posts_to_directors`; CHARC §5.6).

---

## §9 — Dispatch model + effort recommendation

- **writing-plans → `implementer-opus-xhigh`** — measurement-core design + the composition/distinguishing-test arithmetic + driving Codex.
- **executing → `implementer-opus-max`** — measurement-core ledger mutation + the self-source matcher carve-out. (Mirrors the OOF arc; select + announce per `docs/implementer-dispatch-recipe.md`.)
