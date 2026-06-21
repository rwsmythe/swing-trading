# Implementation plan — `swing journal cash-void` cash-ledger correction command (Phase-18, register D19)

**Status:** writing-plans deliverable (PLAN-ONLY — NO production code, NO tests committed). **Spec / settled design:** `docs/cash-void-commissioning-brief.md` (commit `7c1a5809`; the CHARC-verified §2 grounding + the CHARC §3 architecture pass [GO; TWO additive carve-outs; NO schema] + the §4 settled design contract + the §5 test obligations + the §6 gates). **Lane:** CHARC — TWO additive/guard-only carve-outs: a `swing/trades` step-7 matcher `void:` self-source branch + a `swing/data/repos/cash.py` `find_by_id` READ helper; plus a new `swing/cli.py` subcommand + a `void:` namespace reservation at the two free-form-ref writers. **Author:** writing-plans implementer (`implementer-opus-xhigh`). **Date:** 2026-06-21.

The design is SETTLED by the brief — this plan grounds it on disk (worktree base `main` HEAD `6032a3d8`, which includes the just-merged OOF arc + the cash-void commissioning), lays out the TDD task breakdown + the discriminating tests with pre/post arithmetic, and nails the OOF-vs-VOID differences. It does NOT re-open the design.

---

## 0. BLOCKING OPEN QUESTIONS for CHARC

**NONE.** Every brief §2 grounding fact + §4 design clause re-grounded clean on disk against the merged OOF arc. The authorized scope (the CLI subcommand + the `void:` matcher branch + the `find_by_id` read helper; NO schema, NO new module, NO new dependency, NO THIRD carve-out) is sufficient to implement the full settled design. Grounding turned up benign drift / strengthening OBSERVATIONS (Appendix A) that make the tests STRONGER (notably: the live OOF matcher branch already gates on `cm.kind == "withdraw"` AND on the ticker being currently-declared — the void branch MUST do NEITHER, gating on the canonical `void:` ref shape ALONE, regardless of kind — O1; and the sandbox gate's env read MUST go through `apply_overrides`, not bare config — O2). None crosses a binding gate or the authorized scope, so none is a §0 blocker.

---

## 1. Overview + the settled design (restated)

**Problem (brief §1).** `cash_movements` is append-only, insert-only — `swing/data/repos/cash.py` is `insert_cash`/`list_cash`/`find_by_ref` only; there is NO void/delete/correct path. An erroneous/duplicate/superseded `cash_movement` (a fat-finger amount, a re-record) is fixable ONLY by a raw out-of-band DB DELETE. **Live instance 2026-06-21:** re-recording SPCX via `oof-buy` ADDED a row atop the un-deletable manual id 5 → a $372.48 double-debit of the swing ledger; RD corrected it via a backed-up scoped raw delete. **Measurement-relevant:** an uncorrectable cash error corrupts `current_equity`, which §2.4 coherence + position-sizing read — the double-debit would fire a real `equity_delta` every recon until raw-deleted.

**Settled design (brief §4).** A new CLI subcommand, a sibling of `journal cash` / `journal oof-buy`:

```
swing journal cash-void <cash_movement_id> --reason <text> [--date YYYY-MM-DD]
```

It does exactly two things, both reusing existing public surfaces (no new write function):

1. **Fetch + validate** the original `cash_movement` by id via a NEW `find_by_id(conn, id)` READ helper on `swing/data/repos/cash.py` (additive carve-out #2). REJECT (clear `click.ClickException`) on: id not found; the target is ALREADY voided (a `void:<id>` row exists — fail-loud idempotency, §3); the target is ITSELF a void entry (`ref` starts with `void:` — no void-of-a-void in V1); empty/missing `--reason`.
2. **Records a REVERSING `cash_movement`** that nets the original to 0 on the ledger: `kind` = the equity NEGATION of the original; `amount` = `original.amount`; `ref` = `void:<original_id>`; `note` = `VOID #<id>: <reason>`. The WRITE reuses the EXISTING `insert_cash` (NOT a new write function). The original row is NOT deleted (append-only ledger) — the void is a REVERSING entry.

Plus three guards the brief mandates:

- **Self-source (carve-out #1):** the step-7 matcher ADDS a `void:` branch — a `_is_void_sentinel_ref(cm.ref)` → SKIP the `cash_movement_mismatch` emit (a void row has no Schwab counterpart). Mirrors the `oof:` branch's SHAPE but gates on the REF ALONE (NOT kind, NOT a ticker registry — §3, O1).
- **Sandbox gating:** under `environment != "production"` the void insert short-circuits (audit-only echo, no row); validation/rejects ALL run BEFORE the write-scoped sandbox short-circuit.
- **Idempotency FAIL-LOUD, FLAT, NO escape hatch:** a `void:<id>` collision (already voided) → REJECT with an actionable `ClickException` naming the existing void row, NEVER a silent no-op. Unlike the OOF arc there is NO legitimate double-void → NO `--force` (the fail-loud is unconditional). `ux_cash_ref` is the belt (the `IntegrityError` belt ALSO fails loud).

**The reversing-kind negation table (the §2-verified core).** `swing/trades/equity.py:21-22` partitions kinds into ADD (`deposit`/`interest`/`dividend`) and SUB (`withdraw`/`fee`); `net_cash_movements` (`:25-36`) applies them with NO ref/origin/kind filter, so a reversing entry of the opposite-sign kind, same amount, nets the pair to exactly 0. The negation maps the original kind to the kind whose sign is opposite:

| original `kind` | original sign on the ledger | reversing `kind` | reversing sign | net of the pair |
| --- | --- | --- | --- | --- |
| `withdraw` | SUBTRACT | `deposit` | ADD | 0 |
| `fee` | SUBTRACT | `deposit` | ADD | 0 |
| `deposit` | ADD | `withdraw` | SUBTRACT | 0 |
| `interest` | ADD | `withdraw` | SUBTRACT | 0 |
| `dividend` | ADD | `withdraw` | SUBTRACT | 0 |

So the negating kind is **`deposit`** when the original SUBTRACTS (`withdraw`/`fee`) and **`withdraw`** when the original ADDS (`deposit`/`interest`/`dividend`). V1 uses ONLY `deposit`/`withdraw` as the reversing kinds (the cleanest semantic — a "reverse this charge" deposit / a "reverse this credit" withdraw); the `interest`/`dividend`/`fee` originals reverse via their sign-class, NOT a same-kind entry (a same-kind reversal would be ambiguous and is not needed — `net_cash_movements` only sees the sign-class). Each row of the table gets a per-kind test (§4 V-KIND).

**Command control-flow ORDER (mirror the OOF §1 order; the sandbox short-circuit is WRITE-SCOPED — validation ALWAYS runs first).** The CLI MUST execute its steps in this exact order so the sandbox gate never swallows validation:

1. `cfg = apply_overrides(ctx.obj["config"])` (materialize the env for the sandbox gate — O2).
2. `--reason` non-empty validation (reject empty/whitespace → `ClickException`) — ALWAYS.
3. Optional `--date` ISO validation (reject → `ClickException`) — ALWAYS (mirror `journal_cash_cmd:1749-1758`). The void row's `date` defaults to the ORIGINAL row's date when `--date` is omitted (§3); if `--date` is supplied it is ISO-validated + used.
4. Open the connection; **fetch the original** via `find_by_id(conn, cash_movement_id)`:
   - not found → `ClickException` (names the id).
   - the original's `ref` starts with `void:` → `ClickException` (no void-of-a-void in V1).
5. **SELECT-first idempotency** — `find_by_ref(conn, "void:<id>")` → already present → `ClickException` naming the existing void row (FAIL LOUD; NO no-op, NO `--force`).
6. The **write-scoped sandbox gate** — `if environment != "production": echo advisory + return` (NO write). This is the LAST gate BEFORE the write; it scopes the WRITE ONLY.
7. `insert_cash(conn, CashMovement(date=<resolved>, kind=<negation>, amount=original.amount, ref="void:<id>", note="VOID #<id>: <reason>"))` (production only) + the success echo. The `IntegrityError` belt re-fetches the colliding void row + raises the SAME fail-loud collision error (consistency with the SELECT-first path; never a silent no-op).

This ordering guarantees a not-found / void-of-a-void / empty-reason / already-voided id is REJECTED even under sandbox (validation precedes the write short-circuit) — the property SB-V's validation arm pins (§4).

**V1 scope:** void a SINGLE existing cash_movement by id; a combined "correct/amend" command is V2 (the operator does `cash-void <id>` then a fresh `journal cash` entry); void-of-a-void is rejected (keeps the chain flat).

---

## 2. Grounded code facts (re-grounded on disk 2026-06-21, worktree base `main` HEAD `6032a3d8`)

All line numbers are from the worktree base. The executing implementer re-grounds before editing (line numbers drift). The OOF arc is MERGED on this base, so the OOF surfaces below are the live exemplar.

### 2.1 Equity composition — the reversing-entry-nets-to-0 proof — `swing/trades/equity.py:21-45`

- `_CASH_ADD_KINDS = frozenset({"deposit", "interest", "dividend"})` (`:21`); `_CASH_SUB_KINDS = frozenset({"withdraw", "fee"})` (`:22`).
- `net_cash_movements(cash_movements)` (`:25-36`): `+= c.amount` for ADD kinds, `-= c.amount` for SUB kinds, ELSE RAISES. **NO ref / origin / kind filter** — every cash_movement row contributes by its kind's sign-class.
- `current_equity(*, starting_equity, exits, cash_movements)` (`:39-45`): `starting + realized + net_cash_movements(...)`.

**Consequence (the §2-verified core):** an original `withdraw` of $X contributes `-X`; a reversing `deposit` of $X contributes `+X` → the pair nets to exactly 0 → `current_equity` is RESTORED to its pre-error value. Symmetric for a `deposit`→`withdraw` reversal. The void needs nothing but a real reversing row of the opposite sign-class.

### 2.2 The step-7 cash-movement matcher (carve-out #1 edit site) — `swing/trades/schwab_reconciliation.py`

Step 7 is a two-pass matcher over `journal_cash_in_period` (the journal cash_movements whose `date` is within the recon period):

- **PASS 1 (`:1869-1900`) — exact `transactionId`-in-`ref` reservation.** For each ref-bearing `cm`, it scans `schwab_transactions` for `str(tx.transaction_id) == cm.ref` (`:1875`). A `void:<id>` ref is ref-BEARING (truthy), but a Schwab `transaction_id` is a numeric string (`[0-9]+`) and `void:<id>` carries the literal `void:` prefix at position 0 → `str(tx.transaction_id) == "void:5"` is ALWAYS False → a void row never ref-matches in PASS 1, never enters `_ref_matched_cm_ids` / `_ref_mismatch_cm_ids` (the §3 collision proof, same as OOF).
- **PASS 2 (`:1901-2007`) — heuristic for rows not matched by exact ref.** Skips `_ref_matched_cm_ids` (`:1903`). The live OOF self-source branch sits at the TOP of the PASS-2 loop body (`:1931-1934`):

```python
_oof_ticker = _oof_ref_ticker(cm.ref) if cm.kind == "withdraw" else None
if _oof_ticker is not None and _oof_ticker in out_of_framework_set:
    cash_counters["cash_oof_self_sourced_count"] += 1
    continue
```

A void row is not ref-matched, not ref-mismatch → it runs the PASS-2 heuristic. A void DEPOSIT (reversing a withdraw) or a void WITHDRAW (reversing a deposit) has NO Schwab counterpart (the original error was a manual/auto cash row; the void is a pure ledger correction with no broker transaction) → `match_idx is None` → it would **emit `cash_movement_mismatch` every run** without the carve-out (the recurring false discrepancy the brief flags).

**The carve-out (ONE additive branch, mirroring the OOF branch's SHAPE but with the KEY OOF-vs-VOID difference).** Add a SECOND branch at the PASS-2-loop top, AFTER the `_ref_matched_cm_ids` skip and the existing OOF branch:

```python
# Phase-18 D19 (`swing journal cash-void`) — self-sourced VOID reversing-entry
# skip. A cash-void records a REVERSING cash_movement (a deposit reversing a
# withdraw/fee, or a withdraw reversing a deposit/interest/dividend) carrying a
# CANONICAL VOID sentinel `ref` (void:<original_id>). A void row has NO Schwab
# counterpart -- it is a pure ledger correction -- so it is self-sourced.
# Excluded from the cash_movement_mismatch emit (treated as matched).
#
# KEY DIFFERENCE FROM THE OOF BRANCH ABOVE (O1): the gate is the canonical
# VOID ref SHAPE ALONE -- NOT `cm.kind` and NOT a ticker registry. A void row
# is a deposit OR a withdraw (the negation of the original's sign-class), so a
# kind=='withdraw' gate (like OOF's) would FAIL to skip a void-of-a-deposit
# (a void WITHDRAW) and FAIL to skip a void-of-a-withdraw (a void DEPOSIT) ->
# spurious cash_movement_mismatch. And there is no ticker in a void ref to gate
# on. The canonical-shape predicate (R1 canonical-shape lesson) + the reserved
# `void:` namespace at every free-form-ref writer make `journal cash-void` the
# SOLE producer of a void:<id> ref -> every non-void row runs the byte-unchanged
# existing code below (C3 lock).
if cm.ref and _is_void_sentinel_ref(cm.ref):
    cash_counters["cash_void_self_sourced_count"] += 1
    continue
```

This `continue`s past BOTH the heuristic match loop AND the `_emit(...)` — the void row never emits `cash_movement_mismatch`. Non-void rows (`_is_void_sentinel_ref` returns False) fall through to the byte-unchanged existing code. It does NOT touch PASS 1 (a void ref never ref-matches there). **The branch is kind-AGNOSTIC by design — this is THE load-bearing OOF-vs-VOID difference; the self-reconcile test (§4 S-V) MUST cover BOTH a void-deposit and a void-withdraw row being skipped.**

> **The counter (`cash_void_self_sourced_count`) — REQUIRED for shape-stability if added; OPTIONAL otherwise.** A `cash_counters[...]` increment makes the skip auditable, consistent with the existing `cash_oof_self_sourced_count` audit (`:1102`) and `cash_pending_suppressed_count`. The self-reconcile TEST asserts the skip via the ABSENCE of an emit for the void `cm.id` (counter-independent), so the counter is a documented option, NOT a requirement. **IF the executing implementer adds the counter, it MUST be initialized to 0 in the cash-counters initializer** (the `cc` dict at `~:1090-1103`, alongside `cash_oof_self_sourced_count` at `:1102`) so the `_append_cash_ingest_summary` envelope (`:2012`) stays shape-stable. EITHER choice is additive/guard-only and byte-unchanged for non-void rows. The plan does NOT require the counter; it is a documented option, not a second matcher feature.

### 2.3 The collision proof — `void:<id>` vs a numeric `transaction_id` — `swing/trades/schwab_reconciliation.py:1875` + the OOF precedent `:218-224`

The OOF arc's collision proof (`:218-224`) applies verbatim to the `void:` prefix: a Schwab `transaction_id` is a NUMERIC string (`SchwabTransactionResponse.transaction_id: str`, `models.py`; the live/migration example `"115520131470"`); `str(tx.transaction_id)` of a numeric id is `[0-9]+`. The void sentinel ALWAYS contains the literal substring `"void:"` (lowercase letters + a colon) at position 0, which `[0-9]+` can never contain. Therefore:
- The step-7 PASS-1 ref-exact match `str(tx.transaction_id) == cm.ref` can NEVER be True for a `void:` ref → a void row never reserves a tx, never force-emits.
- The §2.2 void-skip branch `_is_void_sentinel_ref(cm.ref)` can NEVER be True for a real `transaction_id` (a numeric string lacks the `void:` prefix) → a genuine ref-backed manual cash_movement is NEVER skipped as a void.

These are MUTUALLY EXCLUSIVE by construction (numeric vs `void:`-prefixed), AND distinct from the `oof:` prefix (a void row is never oof-matched, and vice versa — three disjoint ref-prefix domains: `[0-9]+`, `oof:...`, `void:...`). §4 test C2-V is the discriminating test (both directions).

### 2.4 `cash_movements` schema (migration 0029) — `swing/data/migrations/0029_cash_reconciliation.sql`

- `cash_movements (id INTEGER PK, date TEXT [ISO-GLOB CHECK], kind TEXT CHECK IN ('deposit','withdraw','interest','dividend','fee'), amount REAL CHECK >= 0, ref TEXT, note TEXT)` (`:14-21`). `kind="deposit"`/`"withdraw"` and a free-form `ref` are both schema-legal.
- `CREATE UNIQUE INDEX ux_cash_ref ON cash_movements(ref) WHERE ref IS NOT NULL` (`:56`) — the partial unique index that gives the `void:<id>` sentinel its idempotency (a second `void:<id>` insert raises `sqlite3.IntegrityError`).
- `ref` has NO format CHECK → a `void:`-prefixed sentinel is schema-legal. **NO migration; schema stays v31.**

### 2.5 The model + the repo (the surfaces the command reuses) — `swing/data/models.py:380-414` + `swing/data/repos/cash.py`

- `CashMovement(id, date, kind, amount, ref, note)` (`models.py:383-390`). `__post_init__` (`:392-414`) validates `kind` against `_CASH_MOVEMENT_KINDS` + the ISO date shape; it does NOT validate `amount >= 0` (DB CHECK only) and does NOT validate `ref` shape → a `void:` sentinel ref passes the model. The original's `amount` (already a non-negative REAL from the persisted row) reused for the reversing row passes the `amount >= 0` CHECK by construction.
- `insert_cash(conn, m)` (`cash.py:9-17`): `INSERT INTO cash_movements (...)`; returns `lastrowid`; "Caller wraps in `with conn:`" — does NOT open its own tx and does NOT catch `IntegrityError`. So a duplicate `void:<id>` ref raises `sqlite3.IntegrityError` out of `insert_cash` → the CLI catches it for the fail-loud belt (§3, §4 test I1-V).
- `find_by_ref(conn, ref)` (`cash.py:30-37`): the ref-exact lookup; returns the existing `CashMovement` or `None`. The SELECT-first idempotency uses this on `"void:<id>"`. `ux_cash_ref` guarantees at most one row per ref, so `fetchone()` is correct.
- **`find_by_id` does NOT exist** (grep-confirmed — `cash.py` is `insert_cash`/`list_cash`/`find_by_ref` only). **This is carve-out #2: an ADDITIVE READ helper** — `find_by_id(conn, id) -> CashMovement | None` mirroring `find_by_ref`'s shape (a parameterized `SELECT ... WHERE id = ?` + the `_row_to` mapping). NO write function added; the void WRITE reuses `insert_cash`.

### 2.6 The OOF ref-sentinel exemplar (the SHAPE to mirror, NOT blind-copy) — `swing/trades/schwab_reconciliation.py:225-353`

- `_OOF_REF_PREFIX = "oof:"` (`:225`); `_OOF_REF_RE = re.compile(r"^oof:[^:]+:\d{4}-\d{2}-\d{2}(?:#(?:[2-9]|[1-9]\d+))?$")` (`:257`); `_build_oof_ref` (`:260-280`); `_is_oof_sentinel_ref(ref)` (`:324-334`, `bool(ref) and _OOF_REF_RE.match(ref) is not None`); `_oof_ref_ticker` (`:337-353`). The OOF predicate keys on the canonical SHAPE (NOT a bare prefix) — the R1-MAJOR-1 lesson: a manual `journal cash --ref "oof:..."` value must NOT be skipped unless it is canonical-shaped.
- **The VOID sentinel + predicate (the canonical-shape lesson applied):**
  - `_VOID_REF_PREFIX = "void:"` (used by the two namespace-reservation writers — §3).
  - `_VOID_REF_RE = re.compile(r"^void:\d+$")` — the canonical shape is `void:<original_id>` where `<original_id>` is the INTEGER cash_movements id. The predicate matches `^void:\d+$` (one-or-more digits after the prefix), NOT a bare `void:` prefix (mirror the OOF R1 canonical-shape lesson — a manual `journal cash --ref "void:..."` malformed value must not be skipped; reserved at the writers anyway, §3, but the predicate is shape-tight as defense-in-depth). NO `#<seq>` complexity (the void key is the original id, which is itself unique — no legitimate second void of the same id, §3).
  - `_build_void_ref(original_id: int) -> str`: `f"{_VOID_REF_PREFIX}{int(original_id)}"`. (Validate `original_id >= 1`; raise `ValueError` on a non-positive id, wrapped to a clean `ClickException` at the CLI boundary per the service-ValueError discipline — though a click-typed `<cash_movement_id>` int argument is already constrained.)
  - `_is_void_sentinel_ref(ref: str | None) -> bool`: `bool(ref) and _VOID_REF_RE.match(ref) is not None`. None/empty → False (the matcher guards `cm.ref and _is_void_sentinel_ref(...)`).
  - A SINGLE source-of-truth helper set (`_VOID_REF_PREFIX` + `_VOID_REF_RE` + `_build_void_ref` + `_is_void_sentinel_ref`) defined ONCE in `swing/trades/schwab_reconciliation.py` (next to the matcher + the OOF helpers) and imported lazily by `swing/cli.py` (to build the ref) + by `swing/journal/tos_import.py` (for the prefix reservation) — never hand-duplicated string literals (the Arc-6 shared-predicate lesson). NO new module/package (brief §3 tripwire).
- **Collision-proof:** `void:<id>` (a numeric tail with the `void:` prefix) can never numerically equal a Schwab `transaction_id` ([0-9]+, no prefix), and never matches the `oof:` predicate (different prefix) — three disjoint domains (§2.3).

### 2.7 The CLI to mirror — `swing/cli.py` `journal cash` (`:1700-1769`) + `journal oof-buy` (`:1772-1991`) + `@journal_group` (`:1602`)

- `journal_cash_cmd` (`:1710`) is the ISO-date-validation + `insert_cash` + echo mirror.
- `journal_oof_buy_cmd` (`:1784`) is the closest structural mirror — the control-flow order (`apply_overrides` → validation → SELECT-first idempotency → write-scoped sandbox gate → `insert_cash` + `IntegrityError` belt), the fail-loud collision helper (`_collision_error`, `:1882`), the sandbox advisory (`:1941-1947`), the `ClickException`-wrapping of a builder `ValueError` (`:1876-1879`). **The new `cash-void` command registers as `@journal_group.command("cash-void")`.** There is NO existing `cash-void` command (grep-confirmed) — purely additive.
- **The OOF-vs-VOID CLI differences to NOT blind-copy (O1):**
  - The OOF command reads `apply_overrides` for the REGISTRY (`out_of_framework_tickers`, `:1836-1841`) AND the env. The void command has NO ticker registry — it reads `apply_overrides` ONLY for the sandbox env (O2). NO registry guard.
  - The OOF command has a `--force` escape hatch + `_next_free_ref` + the `#<seq>` disambiguator (because a legitimate second same-day OOF buy exists). The void command has NO `--force` — there is NO legitimate double-void of the same id → the fail-loud is FLAT + unconditional. The `_collision_error` mirror names the existing void row + does NOT point to any escape hatch.
  - The OOF command's positional/named inputs are `--ticker`/`--cost`; the void command's are a positional `<cash_movement_id>` (click `type=int`) + `--reason` (required, non-empty) + `--date` (optional).

> **O2 — the sandbox env read MUST go through `apply_overrides(ctx.obj["config"])`, NOT the bare `ctx.obj["config"]` the `journal cash` mirror uses.** `integrations.schwab.environment` is materialized by `apply_overrides` (`config_overrides.py:121-123`); a bare-config read returns the base default (`production`), so a sandbox override on the live system would be IGNORED → the sandbox gate would write a domain row under sandbox (the same 18-E default-arg-diverges family as the OOF arc's O1). The void command reads `cfg = apply_overrides(ctx.obj["config"])` then `cfg.integrations.schwab.environment`. The SB-V test seeds `environment="sandbox"` via the OVERRIDES path (the production read shape).

### 2.8 The `void:` namespace reservation — `swing/cli.py:1738-1744` (the `oof:` precedent) + `swing/journal/tos_import.py:360-386`

The OOF arc reserved the `oof:` prefix at the two free-form-ref writers so a NON-OOF row can never carry an `oof:` ref (the self-source Lock-1 hole). Mirror BOTH for `void:`:
- **`journal cash --ref`** (`cli.py:1738-1744`): the live code imports `_OOF_REF_PREFIX` and rejects a `--ref` value `startswith(_OOF_REF_PREFIX)`. ADD a parallel `_VOID_REF_PREFIX` rejection (same `startswith` shape — the reservation is a PREFIX check, distinct from the matcher's canonical-shape predicate; a prefix reservation is correct here because it must block ANY `void:`-prefixed value, malformed or not). The two reservations can share one combined check or be two sequential checks; the executing implementer picks the cleaner shape. Message: ASCII, names the reserved prefix + points to `swing journal cash-void`.
- **TOS import** (`tos_import.py:360-386`): the live code imports `_OOF_REF_PREFIX` and neutralizes an `oof:`-prefixed REF# to ref-less (`ref = None`). ADD a parallel `_VOID_REF_PREFIX` neutralization (a hand-edited CSV REF# starting `void:` → ref-less, so the row keeps its pre-arc heuristic disposition). A real broker REF# is never `void:`-prefixed; this closes the Lock-1 hole.

**Consequence:** `journal cash-void` becomes the SOLE producer of a `void:<id>` ref → a non-void row can never carry one → the §2.2 self-source branch is provably inert for every row the other writers can produce (the C3-V lock).

### 2.9 The sandbox-gate precedent — `swing/cli.py:1936-1947` (the OOF gate) + `swing/integrations/schwab/pipeline_steps.py` (the canonical domain-row gate)

The OOF command's write-scoped sandbox gate (`:1940-1947`): `environment = cfg.integrations.schwab.environment; if environment != "production": echo advisory + return`. For the void command there is NO Schwab API call — "audit-only" reduces to "write NO `cash_movements` row + echo an advisory" (there is no `schwab_api_calls`-style audit table for a manual cash entry). The gate is the LAST step before `insert_cash`; validation (reason / date / not-found / void-of-a-void / already-voided) ALL run BEFORE it (the §1 control-flow order). SB-V's validation arm pins this.

---

## 3. The VOID sentinel `ref` format (a writing-plans detail per brief §4) + the collision + idempotency proof

**Format (canonical):**

```
void:<original_id>
```

- `<original_id>` = the INTEGER `cash_movements.id` of the row being voided (e.g. `void:5`).
- `_VOID_REF_RE = ^void:\d+$` (one-or-more digits; NO `#<seq>`, NO ticker/date segments — the void key IS the original id).

**Why this shape (each property maps to a brief requirement):**

1. **Deterministic + recognizable (origin marker for the §2.2 matcher branch).** `_is_void_sentinel_ref(ref)` matches `^void:\d+$` — the canonical shape, NOT a bare `void:` prefix (mirror the OOF R1 canonical-shape lesson). `_build_void_ref(original_id)` is the single constructor. A SINGLE source-of-truth helper imported by the CLI + TOS reservation (§2.6).

2. **Idempotent via `ux_cash_ref` — FAIL LOUD, FLAT, NO escape hatch (the RD course-correction lesson; do NOT repeat the OOF silent-no-op).** The ref is a deterministic function of `original_id`, so a second `cash-void <id>` produces the IDENTICAL ref `void:<id>` → the partial unique index `ux_cash_ref` rejects the duplicate. The CLI's idempotency is SELECT-first (`find_by_ref("void:<id>")` before `insert_cash`) so the operator sees a clean fail-loud "already voided" `ClickException` naming the existing void row, NOT a silent no-op and NOT an `IntegrityError` traceback. **CRITICAL OOF-vs-VOID DIFFERENCE: there is NO legitimate double-void of the same id** (a row is voided once; a second distinct correction would target a DIFFERENT id, or be a fresh entry) → there is NO `--force` escape hatch → the fail-loud is FLAT + unconditional. The `IntegrityError` belt (a TOCTOU race past the SELECT) re-fetches the colliding `void:<id>` row + raises the SAME fail-loud collision error (defense in depth; never a silent no-op). The I1-V test asserts the bare re-void RAISES (non-zero exit + names the void row) + no double-record; PRE-fix-arithmetic a silent-no-op would exit 0 with one row unchanged → the test's non-zero-exit assertion distinguishes.

3. **Can NEVER collide with a real Schwab `transaction_id` NOR an `oof:` ref (§2.3).** Three disjoint prefix domains: `[0-9]+` (Schwab), `oof:...`, `void:...`. The `void:` prefix (lowercase letters + a colon at position 0) is never producible by `[0-9]+` and never matches `_OOF_REF_RE` (different prefix). §4 test C2-V pins both directions (a numeric id is not a void sentinel; a void ref is not ref-matched in PASS 1; a void ref is not oof-recognized).

4. **No void-of-a-void (V1, keeps the chain flat).** The CLI rejects voiding a row whose `ref` starts with `void:` (the target is itself a void entry). So a `void:` ref only ever points at a NON-void original; the chain is flat (no `void:void:...`). The matcher never needs to reason about chained voids.

> **The `date` of the void row.** When `--date` is omitted, the void row's `date` defaults to the ORIGINAL row's `date` (`original.date`) — so the reversing entry sits in the same period as the error, and a recon over that period sees the pair net to 0 (the both-in-period composition). When `--date` is supplied (ISO-validated), it is used (the operator may want the correction dated to the day it was discovered). Either way the void row self-reconciles (the matcher gates on the ref, not the date). The default-to-original-date is the cleaner V1 semantic (the correction belongs with the error); the test V-KIND uses an explicit `--date` for determinism, and a default-date test asserts the omitted-date row carries `original.date`.

---

## 4. Per-task breakdown (TDD-first)

**Task structure (executing phase).** Four production touches, each red→green→commit:
- **Task 1** — the VOID sentinel ref helpers (`_VOID_REF_PREFIX`, `_VOID_REF_RE`, `_build_void_ref`, `_is_void_sentinel_ref`) in `swing/trades/schwab_reconciliation.py` — a pure, self-contained unit (tested by C2-V's collision/canonical-shape discriminator + a round-trip).
- **Task 2** — the step-7 matcher self-reconcile `void:` branch (the `swing/trades` carve-out #1) — tested by S-V (self-reconcile, BOTH a void-deposit and a void-withdraw), C3-V (additive/guard-only byte-unchanged), and the COMP-V composition test's post-void arm.
- **Task 3** — the `find_by_id` READ helper on `swing/data/repos/cash.py` (carve-out #2) — tested by a repo unit test (round-trip + not-found → None) + exercised end-to-end by the CLI tests.
- **Task 4** — the `swing journal cash-void` CLI subcommand (reason/date validation + find_by_id fetch + reject ladder + SELECT-first fail-loud idempotency + write-scoped sandbox gate + the `insert_cash` reversing write + the `IntegrityError` belt) + the two `void:` namespace reservations (`journal cash --ref`, TOS import) — tested by V-KIND, REJ-V, I1-V, SB-V, NS-V, and the end-to-end leg of COMP-V.

(The executing implementer MAY reorder so the helper [Task 1] + the matcher branch [Task 2] + the repo helper [Task 3] land before the CLI [Task 4], since COMP-V exercises them together. The order above is the dependency order.)

Each test states its PRE/POST arithmetic so it provably DISTINGUISHES (a test green under both pre-fix and post-fix code is worthless — memory `feedback_regression_test_arithmetic`). Tests are built from the REAL emitter path (`run_schwab_reconciliation` end-to-end + the real `swing journal cash-void` CLI via `CliRunner`), NEVER values hand-built to satisfy the premise (memory `feedback_verify_premise_arithmetic_vs_live`). Fixtures mirror `tests/trades/test_oof_buy_cash_coherence.py` (the `_SchwabAccount` / `_Txn` / `_position` / `_seed_cash` / `_run` / `_cash_mismatch_ids` helpers) + `tests/cli/test_oof_buy_command.py` (the `_setup` / `_minimal_config` / `write_user_overrides` / `_cash_rows` / `CliRunner` patterns).

### Test COMP-V — the BINDING composition test (RD, MERGE-BLOCKING measurement artifact)

**Intent (brief §5):** void an erroneous `withdraw` of $X → `current_equity` is RESTORED (the reversing `deposit` nets the pair to 0); PRE-void `current_equity` is the un-restored value (off by X). AND the symmetric case (void a `deposit` of $X → a `withdraw` restores it). Real-derived inputs, tolerance/values COMPUTED from the resolved ledger, never built to satisfy the premise.

**Fixture (real-derived; §2.1 arithmetic):**
- `starting_equity = L0` (e.g. `1450.0`); no exits, no positions (`journal_flat=True`, `broker_flat_swing=True`); `out_of_framework_tickers=()`.
- The error: an erroneous `withdraw` of $X (e.g. `X = 372.48`, the live double-debit amount) inserted via the production path (`insert_cash`, or the `journal cash --withdraw X` CLI). PRE-void `current_equity = L0 - X`.
- The void: `cash-void <error_id> --reason "double-debit" --date <d>` (production env) → inserts a reversing `deposit` of $X with `ref=void:<error_id>`. POST-void `current_equity = (L0 - X) + X = L0` (RESTORED).

**Assertions + pre/post arithmetic (the binding distinguisher):**

There are two complementary measurement surfaces — assert BOTH (the brief's "current_equity restored" is the load-bearing one):

1. **The direct `current_equity` surface (the cleanest measurement assertion).** Compute `current_equity(starting_equity=L0, exits=[], cash_movements=list_cash(conn))` (the SAME function the dashboard + recon use, `equity.py:39`) at THREE points:
   - baseline (no error row): `== L0`.
   - PRE-void (error withdraw present, no void): `== L0 - X`.
   - POST-void (error + reversing deposit): `== L0` (RESTORED).
   Assert `current_equity_pre_void == L0 - X` AND `current_equity_post_void == L0` AND `current_equity_post_void - current_equity_pre_void == pytest.approx(X)` (the restoration delta is EXACTLY X). **This is the binding measurement artifact: PRE differs from POST by exactly X, restored to baseline.** Distinguishes: under a no-op void (no reversing row), `current_equity_post == L0 - X` (unchanged) → the `== L0` assertion FAILS; the reversing row makes it `L0` → PASSES.
2. **The recon `equity_delta` surface (the production fire/no-fire path).** Run `run_schwab_reconciliation(...)` with a broker NLV `N = L0` (the recon compares `finite_ledger_equity` vs `swing_nlv`; with no positions `swing_nlv = N = L0`):
   - PRE-void: `finite_ledger_equity = L0 - X`, `eval_delta = (L0 - X) - L0 = -X`; `tol = max(5, 0.005*L0)`. With `X (=372.48) > tol (=7.25)` → an `equity_delta` FIRES (exactly one row).
   - POST-void: `finite_ledger_equity = L0`, `eval_delta = 0` → NO `equity_delta` fires (the void RESTORES coherence).
   Assert the PRE run fires exactly one `equity_delta` (compute the tolerance from the resolved `swing_nlv`, assert `abs(eval_delta_pre) > tol`) and the POST run fires ZERO. Also assert the void row's `cm.id` does NOT fire `cash_movement_mismatch` in the POST run (self-sourced — ties COMP-V to S-V).

**The symmetric arm (void a `deposit`):** repeat with the error being an erroneous `deposit` of $X (PRE `current_equity = L0 + X`) → `cash-void <id>` inserts a reversing `withdraw` of $X → POST `current_equity = L0` (restored). Assert `current_equity_pre - current_equity_post == pytest.approx(X)` AND the recon's `eval_delta` flips from `+X` (fires) to `0` (no fire).

**Distinguishes:** PRE differs from POST by exactly X on BOTH the direct `current_equity` surface and the recon `equity_delta` surface, in BOTH directions (withdraw-error and deposit-error). Computed under both paths; the tolerance is computed from the resolved ledger, not assumed (memory `feedback_verify_premise_arithmetic_vs_live`). Built via the production path (`insert_cash` + the real CLI + the real `current_equity` / `run_schwab_reconciliation`).

### Test S-V — the self-reconcile test (the matcher carve-out distinguisher; BOTH directions — the kind-agnostic gate)

**Intent (brief §5):** across a reconciliation run a void-marked cash_movement does NOT fire `cash_movement_mismatch`, asserted as SKIPPED-AS-SELF-SOURCED — the test FAILS if the matcher branch is absent. **Covers BOTH a void-deposit (reversing a withdraw) AND a void-withdraw (reversing a deposit) — the load-bearing kind-agnostic gate (O1): the void branch gates on the REF, NOT the kind.**

**Fixture (real-derived; the OOF S1 isolation discipline applies):**
- TWO void rows, inserted via the production writer (`insert_cash`):
  - a void DEPOSIT: `kind="deposit"`, `amount=X1`, `ref="void:<id_a>"` (reversing an erroneous withdraw with id `<id_a>`), `date=d` within the period.
  - a void WITHDRAW: `kind="withdraw"`, `amount=X2`, `ref="void:<id_b>"` (reversing an erroneous deposit with id `<id_b>`), `date=d`.
  (The originals `<id_a>`/`<id_b>` may also be seeded so the ids are real; the matcher gates on the void rows' refs, so the originals' presence is not load-bearing for S-V — but seed them for realism. The originals are NON-void rows; ensure they don't accidentally fire — give the withdraw-original a numeric ref matching a planted withdraw-typed tx, or make them ref-less heuristic-matched, OR scope the assertion strictly to the void cm.ids.)
- `schwab_transactions`: the fixture MUST contain NO counterpart for either void row in the ±4-day window at the matching amount/sign (so a void row CANNOT heuristic-match even without the branch — the both-paths-pass guard, mirroring OOF S1). The void DEPOSIT (positive sign-class) would need a positive-sign counterpart to heuristic-match; the void WITHDRAW (negative) a negative one — provide NEITHER for the void rows. OPTIONALLY include an unrelated matched tx so the run isn't empty.
- `out_of_framework_tickers=()` (irrelevant — the void branch does NOT gate on a ticker registry; this is the OOF-vs-VOID difference, so the test runs with an EMPTY registry to PROVE the void skip does not depend on it).

**Assertions + pre/post arithmetic:**
- **Post-fix:** NEITHER void row's `cm.id` has a `cash_movement_mismatch` row (`SELECT ... WHERE discrepancy_type='cash_movement_mismatch' AND cash_movement_id IN (<void_deposit_id>, <void_withdraw_id>)` → empty). Scoped to the void cm.ids (not a generic "no mismatches").
- **The branch-disabled belt (the cleanest distinguisher — REQUIRED):** run the SAME fixture with the void branch FORCED INERT (monkeypatch `_is_void_sentinel_ref` to return `False`, mirroring the OOF S1 belt `test_self_reconcile_branch_disabled_belt_fires`) and assert BOTH void rows DO emit; then with the branch ACTIVE assert NEITHER emits. The emit FLIPPING on the single boolean proves the branch is load-bearing AND kind-agnostic.
- **Pre-fix arithmetic (proves the test fails without the branch):** without the §2.2 branch, each void row is not ref-matched (PASS 1: `void:...` != numeric txn_id), not ref-mismatch, runs the PASS-2 heuristic, finds `match_idx is None` (no counterpart in the fixture) → `_emit(cash_movement_mismatch, cash_movement_id=<void cm.id>)`. So pre-fix BOTH void rows emit; the assertion FAILS. Post-fix the branch `continue`s before the emit → no rows; PASSES.
- **The kind-agnostic discriminator (THE load-bearing OOF-vs-VOID difference):** the void WITHDRAW row is the one a kind=='withdraw'-gated branch (like OOF's) would ALSO skip — but the void DEPOSIT row is the one such a gate would MISS (a kind=='withdraw' gate sees a deposit and falls through to emit). So the void-DEPOSIT-skipped assertion is the discriminator that a kind=='withdraw' copy-paste of the OOF branch would FAIL. State this explicitly: the test would FAIL if the executing implementer blind-copied the OOF branch's `cm.kind == "withdraw"` gate.

### Test C3-V — the additive/guard-only proof (every non-void row byte-unchanged)

**Intent (brief §5):** a discriminating test that EVERY non-void cash_movement's match/emit path is byte-unchanged by the new branch.

**Fixture:** a run with a MIX of non-void cash_movements exercising each step-7 outcome class (mirror the OOF C3 `_c3_fixture`):
- (a) a ref-backed clean match (`ref = str(tx.transaction_id)`, value-valid) → `_ref_matched_cm_ids` → no emit.
- (b) a ref-backed value-drift (`ref = str(tx.transaction_id)`, wrong amount) → `_ref_mismatch_cm_ids` → force-emit.
- (c) a ref-less heuristic match → matched → no emit.
- (d) a ref-less no-counterpart row → emit.

**Assertions + pre/post arithmetic:** the set of `cash_movement_mismatch` discrepancies (and the matched/unmatched disposition of each cm.id) is IDENTICAL whether or not the §2.2 branch is present — `_is_void_sentinel_ref` returns False for every ref in (a)-(d) (none is `void:`-prefixed) → the branch's `continue` never fires → byte-unchanged. **Pre==post for non-void rows (the LOCK).** The discriminating value: the test seeds NO void row, so the new branch is provably inert; assert `emitted == {ids["b_drift"], ids["d_no_match"]}` (non-vacuity: (b)+(d) MUST emit; (a)+(c) MUST NOT). This locks SCOPE (the analog of the OOF C3 lock); the load-bearing FIX distinguisher is S-V.

### Test C2-V — the VOID-ref collision + canonical-shape discriminator (Task 1 unit + matcher boundary)

**Intent (§2.3 + §3 collision/canonical-shape proof):** a real Schwab `transaction_id` can NEVER be matched by the void-skip branch; a void ref can NEVER ref-match a `transaction_id` in PASS 1; a non-canonical `void:`-prefixed value is NOT recognized; a void ref is distinct from an oof ref.

**Assertions:**
- **Unit (Task 1):** `_build_void_ref(5) == "void:5"`; `_is_void_sentinel_ref("void:5") is True`; round-trip `_is_void_sentinel_ref(_build_void_ref(42)) is True`. Canonical-shape only: `_is_void_sentinel_ref("void:") is False` (no digits); `_is_void_sentinel_ref("void:abc") is False` (non-digit); `_is_void_sentinel_ref("void:5x") is False`; `_is_void_sentinel_ref("void: 5") is False`. Collision: `_is_void_sentinel_ref("115520131470") is False`; `_is_void_sentinel_ref("5") is False`. Cross-prefix disjointness: `_is_void_sentinel_ref("oof:SPCX:2026-06-18") is False` AND `_is_oof_sentinel_ref("void:5") is False` (the two predicates are mutually exclusive). Edge: `_is_void_sentinel_ref(None) / ("") is False`. `_build_void_ref` rejects a non-positive id (`ValueError`).
- **Matcher boundary (a discriminating fixture):** a run with (i) a void row `ref="void:5"` (a void deposit) AND (ii) a Schwab tx whose `transaction_id` is a numeric string. Assert the void row is skipped-as-self-sourced (S-V mechanism) AND the numeric tx is NOT consumed by the void row (PASS 1 never ref-matches `void:5` to a number). Conversely a NON-void ref-backed row with `ref = str(tx.transaction_id)` ref-matches in PASS 1 as today and is NOT caught by the void branch.
- **Distinguishes:** the predicate returns different booleans for the void / numeric / oof / non-canonical ref shapes; a buggy predicate (bare-prefix `startswith("void:")`, or a substring catch) would flip an assertion (e.g. recognize `void:abc` or fail to reject `5`).

### Test V-KIND — the reversing-kind negation table (per-kind)

**Intent (brief §5):** each original `kind` → the correct negating reversing `kind` (`withdraw`/`fee`→`deposit`; `deposit`/`interest`/`dividend`→`withdraw`).

**Fixture (CLI via `CliRunner`, the REAL command, production env):** for EACH of the five original kinds, seed an original `cash_movement` of that kind (via `journal cash --<kind> <amt> --date <d>`, or `insert_cash`), capture its id, then `cash-void <id> --reason "test" --date <d>` and assert the reversing row's `kind`, `amount`, `ref`, `note`:
- original `withdraw` $X → reversing row `kind="deposit"`, `amount=X`, `ref="void:<id>"`, `note` startswith `"VOID #<id>:"`.
- original `fee` $X → reversing `kind="deposit"`, `amount=X`.
- original `deposit` $X → reversing `kind="withdraw"`, `amount=X`.
- original `interest` $X → reversing `kind="withdraw"`, `amount=X`.
- original `dividend` $X → reversing `kind="withdraw"`, `amount=X`.

**Assertions + pre/post arithmetic:** parametrize over the five kinds; assert the reversing row's `kind` is the §1-table negation, `amount == original.amount`, `ref == "void:<id>"`, and `current_equity` after the void equals the pre-error baseline (the pair nets to 0). **Distinguishes:** a wrong negation (e.g. reversing a `fee` with a `withdraw` instead of a `deposit`) would DOUBLE the subtraction → `current_equity` off by `2X` not 0 → the restoration assertion FAILS.

### Test REJ-V — the reject ladder

**Intent (brief §5):** non-existent id → `ClickException`; already-voided id → `ClickException` naming the void row; void-of-a-void → `ClickException`; empty/missing `--reason` → `ClickException`. (Already-voided is also I1-V; included here for the full ladder.)

**Fixture (CLI via `CliRunner`):**
- **non-existent id:** `cash-void 99999 --reason x` on an empty DB → non-zero exit, message names the id, NO row written.
- **void-of-a-void:** seed an original, `cash-void <id> --reason x` (writes `void:<id>`), capture the void row's id `<vid>`, then `cash-void <vid> --reason x` → non-zero exit (the target's `ref` starts with `void:`), NO new row. Distinguishes: without the void-of-a-void reject the command would write `void:<vid>` (a chained void) → the "no new row" assertion FAILS.
- **empty `--reason`:** `cash-void <id> --reason ""` (and `--reason "   "` whitespace-only) → non-zero exit, NO row. (`--reason` is a required click option, so a MISSING `--reason` is a click usage error [non-zero] by construction; the empty/whitespace check is the added guard.)

**Assertions + pre/post arithmetic:** each reject path exits non-zero + writes nothing; the message is ASCII + actionable. Distinguishes: PRE the void-of-a-void guard, the command would write a chained `void:<vid>` row → the no-row assertion FAILS; PRE the empty-reason guard, an empty reason would write `note="VOID #<id>: "` (a useless audit trail) → the no-row assertion FAILS.

### Test I1-V — the fail-loud idempotency test (FLAT, NO --force — the RD course-correction)

**Intent (brief §5):** voiding the same id twice → `ClickException` naming the existing void row + no double-record. NO silent no-op, NO `--force` escape (unlike OOF).

**Fixture (CLI via `CliRunner`, production env):** seed an original, `cash-void <id> --reason x --date <d>` (writes ONE `void:<id>` row), then RE-RUN the identical `cash-void <id> --reason x --date <d>`.

**Assertions + pre/post arithmetic:**
- After the FIRST run: exactly ONE `void:<id>` row.
- After the SECOND run: STILL exactly ONE row (no double-record); the command exits NON-ZERO with an actionable message naming the existing void row (`"already voided"` / names `#<vid>` / names the ref `void:<id>`) — NOT exit 0, NOT a silent no-op, NOT an uncaught `IntegrityError` traceback. **There is NO `--force` arm** (the void command has no escape hatch — assert the help/usage does not offer `--force`, OR simply that no second row is ever writable for the same id).
- **The `IntegrityError` belt arm (the TOCTOU-race fallback):** monkeypatch `find_by_ref` to MISS once (the race window, mirroring the OOF `test_oof_buy_integrityerror_belt_fails_loud`), so the command reaches the `insert_cash` → `IntegrityError` → the belt re-fetches + raises the SAME fail-loud collision error (non-zero exit, names the row, one row only).
- **Distinguishes (PRE-fix-arithmetic):** a silent-no-op idempotency (the OOF arc's original sin) would exit 0 on the second run with one row unchanged → the test's `exit_code != 0` assertion FAILS against a silent-no-op impl; the fail-loud raises → PASSES. (memory `feedback_regression_test_arithmetic` — the assertion distinguishes the silent-no-op from the fail-loud.)

### Test SB-V — the sandbox test

**Intent (brief §5):** under `environment != "production"`, no domain row written (audit-only); a parallel production case writes one; validation still runs under sandbox.

**Fixture (CLI via `CliRunner`, env via the OVERRIDES path — O2):** seed an original (in production), set `environment="sandbox"` via `write_user_overrides({"integrations": {"schwab": {"environment": "sandbox"}}})`, run `cash-void <id> --reason x`.

**Assertions + pre/post arithmetic:**
- Under SANDBOX: NO new `cash_movements` row (the void row) written; the command echoes a clear sandbox advisory (ASCII) + exits 0.
- A PARALLEL production case (same args, `environment="production"`, the base default) writes exactly ONE void row — the gate is env-conditional, not "never writes."
- **The validation-still-runs arm (the write-scoped-gate proof):** under SANDBOX, a NON-EXISTENT id (`cash-void 99999 --reason x`) STILL raises the not-found `ClickException` (NOT a silent sandbox no-op). PRE-fix (if the CLI short-circuited to sandbox BEFORE the find_by_id fetch) this arm would NOT raise → FAILS. POST-fix (validation precedes the write-scoped sandbox gate) it raises → PASSES. Distinguishes the control-flow ordering.
- **The O2 discriminator:** the sandbox env is seeded via OVERRIDES; if the command read bare `ctx.obj["config"]` (the O2 bug), the sandbox override would be IGNORED (env stays `production`) → the sandbox run would WRITE a row → the "no row" assertion FAILS. So the test distinguishes the `apply_overrides` env read from the bare-config bug.

### Test NS-V — the `void:` namespace reservation

**Intent (brief §5):** `journal cash --ref void:...` rejected; TOS import neutralizes a `void:`-prefixed REF# to ref-less.

**Fixture + assertions:**
- **`journal cash --ref` reservation (CLI):** `journal cash --withdraw 123 --date <d> --ref void:5` → non-zero exit, the message names the reserved `void:` prefix + points to `swing journal cash-void`, NO row. A non-`void:` ref (`--ref DEP-X`) still works (the guard is scoped to the prefix). Mirror the OOF `test_journal_cash_rejects_oof_prefixed_ref`. Distinguishes: PRE the reservation, the `void:5` ref would write a non-void row that the matcher then skips as self-sourced (the Lock-1 hole) → the "no row" assertion FAILS.
- **TOS-import neutralization (unit, the `tos_import` parser):** a TOS cash row with a `void:`-prefixed REF# → the parsed `CashMovement.ref is None` (neutralized to ref-less). Mirror the OOF TOS-reservation test. Distinguishes: PRE the neutralization, the row keeps the `void:` ref → the matcher skips it as self-sourced.

### Test FBI-V — the `find_by_id` repo helper (Task 3 unit)

**Intent (carve-out #2):** the new `find_by_id(conn, id)` read helper round-trips + returns None on a missing id.

**Assertions:** insert a `cash_movement` via `insert_cash`, capture the id, `find_by_id(conn, id)` returns a `CashMovement` with the matching fields (the `_row_to` mapping); `find_by_id(conn, 99999)` returns `None`; a malformed-id (non-int) is the caller's concern (the click `type=int` constrains the CLI boundary). This is a pure additive read; no write-path change.

### Live-DB-shape discipline (brief §5.10) + encoding (Windows cp1252)

- **Read-path verification:** the sandbox env read (`apply_overrides(cfg).integrations.schwab.environment`) is verified against the live config shape (the SB-V overrides-seeding exercises the production read — the 18-E lesson, the O2 discriminator). The `find_by_id` read is verified against a real persisted row shape (FBI-V round-trips through `insert_cash`).
- **ASCII-only user-facing strings:** every `click.echo` / `ClickException` message added (the not-found / void-of-a-void / empty-reason / already-voided rejections, the sandbox advisory, the success confirmation, the namespace-reservation message, the `note` `"VOID #<id>: <reason>"`) is ASCII — no `§ → ↔ ✓ ✗`, no em-dash, no fractions (the Windows cp1252 `UnicodeEncodeError` gotcha; `capsys` hides it). The `--reason` text is operator-supplied; it is stored in the `note` and never re-emitted through a glyph-sensitive path beyond the echo (the CLI-entry UTF-8 `errors='replace'` safety net covers an operator-supplied non-ASCII reason).

### Acceptance (executing)

- Tests COMP-V, S-V, C3-V, C2-V, V-KIND, REJ-V, I1-V, SB-V, NS-V, FBI-V green; the FULL fast suite green (`python -m pytest -m "not slow" -q`) BEFORE the Codex review (recipe §2: the review converges on a green diff).
- `ruff check swing/` clean.
- The §5/§6 traceability table (§5) honored on disk; the tripwire self-certification (§6) holds (EXACTLY TWO additive carve-outs).

---

## 5. §5 / §6 traceability table (the CHARC + RD QA checklist)

| brief obligation | plan task | plan test | how it distinguishes / honored-on-disk |
| --- | --- | --- | --- |
| §5 composition test (BINDING, RD): void a withdraw of X → current_equity RESTORED; PRE off by X; AND the symmetric deposit case | Task 2 + 4 | COMP-V (both directions) | direct `current_equity` surface (PRE `L0-X`, POST `L0`, delta `==X`) + recon `equity_delta` surface (PRE fires `-X`, POST 0); tolerance COMPUTED from the resolved ledger; real-derived via `insert_cash` + the real CLI. |
| §5 self-reconcile test (void row NOT firing `cash_movement_mismatch`, SKIPPED-AS-SELF-SOURCED; FAILS if branch absent) + BOTH a void-deposit and a void-withdraw (kind-agnostic gate) | Task 2 | S-V | scoped to the void cm.ids; fixture has NO counterpart in window (pre-fix emits); the branch-disabled belt flips the emit on the single boolean; the void-DEPOSIT-skipped assertion is the discriminator a kind=='withdraw' copy-paste would FAIL. |
| §5 additive/guard-only proof (every non-void row byte-unchanged) | Task 2 | C3-V | the 4-outcome mix; `_is_void_sentinel_ref` False for all non-void refs → branch inert → `emitted == {b_drift, d_no_match}`. |
| §5 OOF-vs-VOID matcher difference: the branch gates on the REF SHAPE alone, NOT kind, NOT a registry | Task 2 | S-V (void-deposit arm) + §2.2 comment | the void DEPOSIT row is skipped — a kind=='withdraw' gate would miss it; the EMPTY out_of_framework_tickers in S-V proves no registry dependence. |
| §5 void sentinel canonical shape `^void:\d+$` + can NEVER collide with a `transaction_id` (and distinct from oof:) | Task 1 | C2-V | numeric vs `void:`-prefixed vs `oof:`-prefixed are three disjoint domains; canonical-shape-only (not bare prefix); both directions + cross-predicate disjointness pinned. |
| §5 reversing-kind table (withdraw/fee→deposit; deposit/interest/dividend→withdraw) | Task 4 | V-KIND | per-kind parametrize; `current_equity` restored to baseline (a wrong negation doubles the offset → fails). |
| §5 idempotency FAIL-LOUD (twice → ClickException naming the void row + no double-record; FLAT, no --force) | Task 4 | I1-V | SELECT-first fail-loud + the IntegrityError belt; `exit_code != 0` + one row + names the row; a silent-no-op would exit 0 (distinguishes); NO `--force` arm. |
| §5 reject tests (non-existent id; already-voided; void-of-a-void; empty/missing reason) | Task 4 | REJ-V (+ I1-V for already-voided) | each exits non-zero + writes nothing; void-of-a-void + empty-reason are the added guards (pre-fix would write a bad row). |
| §5 namespace reservation (`journal cash --ref void:...` rejected; TOS neutralizes a void: REF#) | Task 4 | NS-V | mirror the OOF reservations at the two free-form-ref writers; a non-void ref still works (scoped to the prefix). |
| §5 sandbox test (no domain row, audit-only; production writes one; validation still runs) | Task 4 | SB-V | WRITE-SCOPED `environment != "production"` gate (mirror the OOF gate); env read via `apply_overrides` (O2); a non-existent id under sandbox STILL rejects (validation precedes the write short-circuit). |
| §3 carve-out #2 (find_by_id READ helper, additive; write reuses insert_cash) | Task 3 | FBI-V | a parameterized `SELECT ... WHERE id=?` mirroring `find_by_ref`; round-trip + not-found → None; NO new write function. |
| §5.10 live-DB-shape discipline | Task 4 | SB-V (overrides-seeded) | env read-path verified vs the production overrides shape; find_by_id verified vs a real persisted row. |
| §5 ASCII encoding | Task 4 | (by construction) | all added user-facing strings ASCII (cp1252 gotcha). |
| §6 Codex review-strong (repo-access) to convergence + codex-auto-review (matched-high) | (executing) | — | §7 executing spec. |
| §6 RD measurement-integrity L-checklist MERGE-BLOCKING | (executing) | COMP-V | cash coherence is measurement-core; COMP-V is the binding artifact. |
| §6 operator §5.10 live-witness BINDING (CLI) | (executing) | — | §7: seed an erroneous row → cash-void → witness (a) current_equity restored, (b) recon does NOT fire cash_movement_mismatch for the void row, (c) re-voiding fails loud, (d) a non-existent/already-voided id rejected. |
| §6 before-review full-suite + `ruff check swing/` clean | (executing) | — | §4 acceptance + recipe §2. |

---

## 6. Tripwire self-certification

| tripwire | crossed? | disposition |
| --- | --- | --- |
| New schema / migration | **NO** | reuses the free-form `ref` column (0029) as the void origin marker + `ux_cash_ref` for idempotency. No migration. Schema stays v31. |
| New module / package under `swing/` | **NO** | a new CLI subcommand in `swing/cli.py` + a one-branch matcher rule + a ref-helper set in the EXISTING `swing/trades/schwab_reconciliation.py` + a `find_by_id` read function in the EXISTING `swing/data/repos/cash.py` + the two reservation edits in EXISTING `swing/cli.py` + `swing/journal/tos_import.py`. |
| New external dependency | **NO** | — |
| New standing process | **NO** | a CLI command is operator-invoked — not a pipeline step / daemon / scheduled job. |
| Phase-isolation carve-out #1 (`swing/trades`) | **YES → AUTHORIZED** (brief §3) | `swing/trades/schwab_reconciliation.py` step-7 matcher: **additive/guard-only** — ONE branch that ADDs a self-sourced skip for `void:`-marked rows (gating on the canonical ref SHAPE alone — kind-agnostic, registry-independent); it MUST NOT alter any existing match/emit path for non-void rows (byte-unchanged, proven by C3-V). The ref-helper set lives in the same module (pure predicate/constructor; no behavior change to existing functions). Precedent: the OOF `oof:` branch + the SPCX/§2.4 guard-scoped `swing/trades` carve-outs. |
| Phase-isolation carve-out #2 (`swing/data`) | **YES → AUTHORIZED** (brief §3) | `swing/data/repos/cash.py` — an ADDITIVE `find_by_id` READ helper (a parameterized SELECT mirroring `find_by_ref`); the void WRITE reuses the EXISTING public `insert_cash` (NO new write function). Precedent: the OOF arc reused `insert_cash`; the read-helper is the brief-authorized addition. |

**EXACTLY TWO authorized carve-outs** (the step-7 matcher `void:` branch + the co-located ref-helper set in `swing/trades`; the `find_by_id` READ helper in `swing/data`). **NO schema, NO new module/package, NO new dependency, NO new standing process, NO THIRD carve-out.** The optional `cash_void_self_sourced_count` counter (§2.2) is within the matcher's existing counter dict (additive, not a carve-out widening); the plan does NOT require it. The two `void:` namespace reservations (`journal cash --ref` in `swing/cli.py`, the TOS neutralization in `swing/journal/tos_import.py`) are guard-only edits in EXISTING web/CLI/journal modules (NOT `swing/data` / `swing/trades`), mirroring the OOF arc's reservation posture — NOT additional carve-outs. **No §0 BLOCKING question** — the two authorized carve-outs fully implement the settled design. If executing discovers the design needs schema, a third carve-out, or a new module, it STOPS and surfaces it to CHARC via the orchestrator (recipe §5) — it does NOT bake it in.

**File list (production, executing):**
- `swing/cli.py` — the new `@journal_group.command("cash-void")` subcommand (reason/date validation, find_by_id fetch, the reject ladder, SELECT-first fail-loud idempotency, the write-scoped sandbox gate via `apply_overrides`, the `insert_cash` reversing write, the `IntegrityError` belt) + the `void:` namespace reservation in `journal_cash_cmd`.
- `swing/trades/schwab_reconciliation.py` — the void ref-helper set (`_VOID_REF_PREFIX` + `_VOID_REF_RE` + `_build_void_ref` + `_is_void_sentinel_ref`) + the ONE PASS-2-top kind-agnostic self-reconcile branch (+ the optional `cash_void_self_sourced_count` counter, initialized in the `cc` dict if added).
- `swing/data/repos/cash.py` — the additive `find_by_id` READ helper.
- `swing/journal/tos_import.py` — the `void:` REF# neutralization (mirror the `oof:` neutralization).
- **Tests (executing):** new `tests/trades/test_cash_void.py` (COMP-V/S-V/C3-V/C2-V — the recon-path + ref-helper tests) + new `tests/cli/test_cash_void_command.py` (V-KIND/REJ-V/I1-V/SB-V/NS-V — the CLI tests) + the FBI-V repo unit (in `tests/data/` or alongside the existing cash-repo tests). The executing implementer picks the exact test-module split to match the repo's `tests/` layout; mirror `tests/trades/test_oof_buy_cash_coherence.py` + `tests/cli/test_oof_buy_command.py`.

Default `swing/trades` + `swing/data` read-only posture returns after this arc.

---

## 7. Executing-phase spec (baked in from brief §6 + §9)

- **Cell:** `implementer-opus-max` (measurement-core ledger mutation + the self-source matcher carve-out + the kind-agnostic gate that a blind OOF copy-paste would get wrong — brief §9).
- **Review (executing, BINDING gate):** `review-strong` (gpt-5.5/high) with **REPO ACCESS** — production-code: the matcher branch's correctness depends on the surrounding two-pass step-7 loop + the OOF branch above it + the §2.1 equity composition + the namespace reservations, all UN-changed or sibling neighbors, so the reviewer MUST read beyond the diff (recipe §3 18-H.4 repo-access note). Run to `NO_NEW_CRITICAL_MAJOR`; the 5-round cap is suspended; **NEVER tier down.** PLUS **`codex-auto-review`** (gating, repo-access, matched-HIGH effort — `codex exec review --commit <pre-review-sha> -c model_reasoning_effort=high`) as the complementary second eye on production code; a B `major`/`[P1]` is adjudicated + resolved-or-cited before merge.
- **RD:** measurement-integrity L-checklist is **MERGE-BLOCKING** (cash coherence is measurement-core; COMP-V is the binding artifact). The orchestrator routes to RD after its own QA; the implementer NEVER posts.
- **Operator §5.10 live-witness — BINDING (CLI):** seed an erroneous cash row (a throwaway ZZTEST/ZZWIT seed) → `cash-void` it → witness (a) `current_equity` restored, (b) a recon does NOT fire a `cash_movement_mismatch` for the void row, (c) re-voiding the same id fails loud, (d) voiding a non-existent/already-voided id is rejected. Clean up the seed.
- **Convergence transcript:** the executing Codex `NO_NEW_CRITICAL_MAJOR` transcript → a TRACKED `docs/reviews/cash-void-command-executing-codex-findings.md`.
- **Commit discipline:** BARE git from the worktree cwd (never `git -C`); ZERO `Co-Authored-By`; conventional commits carrying the task id; before-review full-suite + `ruff check swing/` clean (recipe §2).
- **Base:** then-current `main`; the orchestrator rebases your branch + runs the merged-head no-false-green suite (the cross-arc seeding-regression net — the 18-B.1×18-D lesson).

---

## 8. Explicitly OUT of scope

- **The D17 `origin`/`source` provenance column** — DEFERRED + premise-corrected (brief §0/§7): a raw out-of-band INSERT forges an `origin` column exactly as easily as a `void:` ref, so the column does NOT close the raw-write vector (a trust-the-repo-boundary limitation, not column-closeable). Re-scoped as a LEGIBILITY candidate (Phase-18-close or later), NOT a raw-write closure. NOT this arc.
- **A combined "correct/amend" command** — V1 = `cash-void <id>` + a fresh `journal cash` entry (two steps); a combined `correct` command that voids + re-records in one shot is a future nicety (brief §7).
- **Void-of-a-void** — rejected in V1 (keeps the chain flat; brief §7). A `void:` ref only ever points at a NON-void original.
- **Any measurement-chain touch** — the §2.4 coherence/emit logic, the `declared_oof_mv` derivation, the swing-NLV basis, the `equity_delta` columns, `net_cash_movements`/`current_equity` themselves. SHIPPED + correct; this arc only RECORDS the reversing entry + SKIPS the self-sourced void row in the matcher. The §2.1 equity composition is read-only-relied-upon, never edited.
- **OOF arc surfaces** — the `oof:` helpers, the OOF matcher branch, the OOF CLI. UNTOUCHED; the void helpers are PARALLEL additions (a void row is never oof-matched and vice versa).
- **The web orphan-acknowledge branch / any web surface** — a void is recorded via the CLI, not a web surface; no web change.

---

## Appendix A — grounding observations (benign drift / strengthening; do NOT re-open the settled design)

Every brief §2 grounding fact + §4 design clause re-grounded CLEAN on disk (`main` HEAD `6032a3d8`, OOF arc MERGED); all line anchors confirmed:
- `_OOF_REF_PREFIX` `:225`; `_OOF_REF_RE` `:257`; `_is_oof_sentinel_ref` `:324-334`; `_oof_ref_ticker` `:337-353` ✓ (the live OOF helpers are MORE elaborate than the OOF plan described — a `#<seq>` re-buy multiplicity feature — but the void arc does NOT need any of that complexity; see O3).
- the step-7 OOF branch `:1931-1934` (gates on `cm.kind == "withdraw"` AND `_oof_ticker in out_of_framework_set`) ✓; `cash_oof_self_sourced_count` initialized `:1102` ✓; the cash-counters `cc` dict `:1090-1103` ✓; the emit `:1986-2005` ✓; `_append_cash_ingest_summary` `:2012` ✓.
- `net_cash_movements` ADD/SUB partition `equity.py:21-22`, no ref/kind filter `:25-36` ✓; `current_equity` `:39-45` ✓.
- `cash_movements` schema + `ux_cash_ref` (migration 0029) `:14-21`, `:56` ✓; `insert_cash` `cash.py:9` + `find_by_ref` `:30`, NO `find_by_id` ✓; `CashMovement.__post_init__` `models.py:392-414` ✓.
- `journal cash` CLI `cli.py:1700-1769`, the `oof:` `--ref` reservation `:1738-1744` ✓; `journal oof-buy` CLI `:1772-1991` ✓; `@journal_group` `:1602` ✓; TOS-import `oof:` neutralization `tos_import.py:360-386` ✓; `import sqlite3` at module level `cli.py:6` ✓.
- `integrations.schwab.environment` materialized by `apply_overrides` `config_overrides.py:121-123` ✓.
- NO existing `cash-void` / `find_by_id` / `void:` anywhere in `swing/` (grep-confirmed) — the founding premise holds; purely additive ✓.

The OBSERVATIONS that STRENGTHEN the plan / nail the OOF-vs-VOID differences (none crosses a binding gate or the authorized scope; none re-opens the design):

1. **O1 (LOAD-BEARING — the key OOF-vs-VOID difference) — the void matcher branch MUST gate on the canonical `void:` ref SHAPE ALONE, NOT `cm.kind` and NOT a ticker registry.** The live OOF branch (`:1931-1934`) gates on `cm.kind == "withdraw"` (an oof: ref only ever rides a withdraw) AND `_oof_ticker in out_of_framework_set` (a ticker registry). A VOID row is a deposit OR a withdraw (the negation of the original's sign-class), and there is NO ticker in a void ref. So a blind copy of the OOF branch's `cm.kind == "withdraw"` gate would FAIL to skip a void-of-a-deposit (a void withdraw... or rather a void DEPOSIT — the deposit reversing a withdraw is the case the kind gate MISSES), firing a spurious `cash_movement_mismatch`. **Consequence:** §2.2 specifies a kind-agnostic, registry-independent `if cm.ref and _is_void_sentinel_ref(cm.ref): continue` branch; S-V covers BOTH a void-deposit and a void-withdraw with an EMPTY registry to prove neither dependence. (Makes S-V the discriminating test against a blind OOF copy-paste; does NOT change scope.)
2. **O2 — the sandbox env read MUST use `apply_overrides(ctx.obj["config"])`, NOT the bare `ctx.obj["config"]` the `journal cash` mirror uses.** `integrations.schwab.environment` lives in user-config.toml overrides (`config_overrides.py:121-123`); bare config returns the base `production` default → a sandbox override would be ignored → the sandbox gate would write under sandbox (the 18-E default-arg-diverges family, same as the OOF arc's O1). **Consequence:** §2.7 + §1 specify `apply_overrides` for the env read; SB-V seeds the env via overrides + asserts the sandbox run writes NOTHING (distinguishes the correct read from the bare-config bug). (Makes SB-V stronger; does NOT change scope.) Note: the void command's ONLY reason to call `apply_overrides` is the env read (unlike OOF, which also needs the registry) — but the call is still required.
3. **O3 — the void sentinel is SIMPLER than the OOF sentinel; do NOT carry the `#<seq>` / `--force` machinery over.** The OOF sentinel is keyed on (ticker, date) — NOT amount — so a legitimate second same-day OOF buy collides, hence the `--force` + `#<seq>` disambiguator. The VOID sentinel is keyed on the original id, which is itself unique, and there is NO legitimate second void of the same id → the fail-loud is FLAT, NO `--force`, NO `#<seq>`, NO `_next_free_ref`. `_VOID_REF_RE = ^void:\d+$` (no `#<seq>` group). **Consequence:** §3 specifies the FLAT fail-loud; I1-V asserts the bare re-void RAISES (no `--force` arm). (Avoids over-engineering; the simpler sentinel is the correct V1 design — the brief's explicit "no --force" instruction.)
4. **O4 — the `insert_cash` `IntegrityError` belt + the SELECT-first ladder are reused verbatim (minus `--force`).** `insert_cash` does not catch `IntegrityError` and does not open its own tx (`cash.py:9-17`); a duplicate `void:<id>` raises out of it. The CLI idempotency is SELECT-first (`find_by_ref`) with an `IntegrityError` belt that FAILS LOUD (re-fetch + raise the same collision error) — NOT a silent no-op (the OOF `test_oof_buy_integrityerror_belt_fails_loud` shape, simplified to remove the `--force` re-allocation branch). **Consequence:** §3 property 2 + I1-V's belt arm. (Makes I1-V stronger.)

**These observations make the plan's tests STRONGER (the kind-agnostic matcher gate proven against a blind OOF copy-paste, the sandbox env read pinned to the production path, the fail-loud simplified to FLAT, the IntegrityError belt fail-loud) — none is used to relax a binding condition or re-open the settled design.**
