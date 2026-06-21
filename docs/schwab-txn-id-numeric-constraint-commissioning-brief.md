# Commissioning Brief — Schwab `transaction_id` numeric constraint (`^[0-9]+$`)

**Commissioned by:** CHARC (Tool Development Director)
**Date:** 2026-06-21
**Arc:** register **D20** — Phase-18-close hardening. A SINGLE `^[0-9]+$` constraint on `SchwabTransactionResponse.transaction_id` closes BOTH the `oof:` AND the `void:` step-7 self-source collision proofs at one site.
**Status:** COMMISSIONED — CHARC §3 architecture pass = **no tripwire crossed** (self-certified below). Awaiting operator dispatch.
**Tripwires crossed:** **NONE.** Edits an existing dataclass validator (`swing/integrations/schwab/models.py:__post_init__`) + a handful of non-numeric test fixtures + comment hygiene at the two proof sites. NOT crossed: new schema/migration, new module/package, new external dependency, new standing process, `swing/trades`|`swing/data` phase-isolation carve-out.
**QA routing:** **CHARC-lane** (an ingestion-robustness hardening that changes NO measurement value — it only rejects out-of-spec input). **RD: fyi, NOT merge-blocking** (both directors already concurred D20 is a Phase-18-close hardening candidate; equity/recon values are untouched). **Operator §5.10 live-witness NOT required** (no user-visible or measurement-value behavior change; the sole observable is test-level — a spec-violating id now raises at construction). The operator may escalate to RD-gating or add a witness if he wishes; absent that, this routes CHARC-lane.

---

## §0 — Decision of record (why now, why this shape)

Surfaced at the cash-void executing return (2026-06-21, review-strong R1 MAJOR-1) and adjudicated by BOTH directors as OUT-OF-SCOPE for the void arc but a worthy close hardening. The void arc correctly did NOT touch `integrations/schwab` (the fix is a 3rd carve-out the void brief forbade — the implementer STOPPED + flagged UP; the §3 swimlane discipline working as designed). Phase-18-close picks it up as its own small arc.

The `oof:`-buy and `void:` arcs BOTH proved their ref-sentinels disjoint from real Schwab `transaction_id`s by ASSUMING tx-ids are numeric (`^[0-9]+$`, so they can never carry an `oof:`/`void:` prefix). The model does NOT enforce that — so the proof rests on an un-enforced boundary. This arc makes the proof SELF-ENFORCING at the construction barrier.

---

## §1 — Problem (the un-enforced assumption)

PASS-1 reconciliation matches a Schwab transaction to a journal `cash_movement` by the transaction id equalling the row's `ref`:
- `swing/trades/schwab_reconciliation.py:1244-1246` — `tx_id = str(tx.transaction_id)` then `if find_by_ref(conn, ref=tx_id) is not None: ...`
- `:1950` — `if str(tx.transaction_id) == cm.ref: ...`

The `oof:`/`void:` self-source branches skip rows whose `ref` matches the tight `_OOF_REF_RE` / `_VOID_REF_RE` sentinels. Their disjointness proof (comments at `:220-225`, `:245`, `:329-330`, `:370-374`, `:1998-2000`, `:2031-2032`) is: "a numeric Schwab `transaction_id` vs the `oof:`/`void:` prefix are mutually exclusive." But `SchwabTransactionResponse.transaction_id` is constrained only to a **non-empty string** (`models.py:363-367`), NOT `^[0-9]+$`. A Schwab payload returning a literal `"void:6"` (or `"oof:SPCX:2026-06-15"`) id would `find_by_ref`-match the void/oof sentinel row → a real broker transaction mis-recognized as a self-sourced reversal, corrupting reconciliation.

**Real-world reachability: LOW** (pre-existing + `oof:`-symmetric; real Schwab ids are numeric per spec — see §2). This is a trust-the-broker-boundary hardening, not a live defect. Its value is making the disjointness proof enforced rather than assumed, cheaply, at one site.

---

## §2 — Verified grounding (CHARC, on disk — do NOT re-derive)

- **Current constraint:** `swing/integrations/schwab/models.py:363-367` — `__post_init__` raises only `if not isinstance(self.transaction_id, str) or not self.transaction_id` ("must be non-empty str"). **No numeric enforcement.**
- **The Schwab spec types the id as an INTEGER** — `reference/schwab-api/account-specification.md:1506`: `transactionId | path | integer ($int64)`; `:1824-1826` (Appendix D, the transaction object schema): `activityId (integer)`. So real, spec-conformant Schwab ids are numeric. A `^[0-9]+$` constraint enforces exactly what the spec already guarantees; fail-loud-on-violation is therefore the CORRECT posture (a non-numeric id is a spec violation worth surfacing — it is precisely what silently breaks the collision proof).
- **Single production construction site, numeric by construction:** `swing/integrations/schwab/mappers.py:571` reads `tx_id_raw = _opt(raw, "transactionId") or _opt(raw, "activityId")` (raises if None), then `:606` builds `transaction_id=str(tx_id_raw)`. For an integer payload `str(int)` is always `^[0-9]+$`. **No production caller constructs a non-numeric id**, so the constraint will NOT reject valid live data. (The mapper needs NO change — the `__post_init__` is the single chokepoint, per the F6 "enforce at the `__post_init__` construction barrier" gotcha.)
- **Blast radius (non-numeric TEST fixtures only):** `tests/integrations/test_schwab_pipeline_steps.py:1426` (`transaction_id="T100"`), `:1477` (`"T200"`), `:1521` (`"T201"`). The shared helpers are already numeric: `tests/trades/conftest.py:71` (`f"95000{idx}"` / `str(spec[3])`) and `tests/trades/test_schwab_cash_ingestion.py:18-19` (`str(tid)` — numeric as long as callers pass numeric). The implementer MUST grep the whole `tests/` tree for every `SchwabTransactionResponse` construction + helper caller and convert any non-numeric `transaction_id` to numeric (mechanical).

---

## §3 — CHARC architecture pass (no tripwire)

| Tripwire | Crossed? | Disposition |
|---|---|---|
| New schema / migration | **NO** | A dataclass `__post_init__` validator; no DB change. |
| New module / package | **NO** | Edits existing `models.py`. |
| New external dependency | **NO** | — |
| New standing process | **NO** | — |
| `swing/trades` \| `swing/data` carve-out | **NO** | The change is in `swing/integrations/schwab/`; the matcher in `swing/trades` is touched ONLY for comment hygiene (no logic change). |

Self-certify "no tripwire crossed" in the plan. Measurement value is untouched (validation-only); CHARC-lane QA, RD fyi.

---

## §4 — Design contract

- **Add a `^[0-9]+$` check to `SchwabTransactionResponse.__post_init__`** (after the existing non-empty check; the non-empty check is subsumed but keep a clear message). Use a module-level compiled regex (e.g. `_TXN_ID_RE = re.compile(r"^[0-9]+$")`). Message ASCII-only (cp1252 gotcha), e.g.: `"SchwabTransactionResponse.transaction_id must match ^[0-9]+$ (Schwab transaction ids are integer per spec); got {!r}"`.
- **Single chokepoint:** the `__post_init__` only. Do NOT add a parallel check at the mapper or path-param — every construction (mapper, tests, any future caller) passes through `__post_init__`.
- **Update the 3 non-numeric fixtures** to numeric (`"T100"`→`"100"`, etc., or any numeric value the assertions tolerate) + grep-sweep for any others (§2).
- **Comment hygiene at the two proof sites** (`swing/trades/schwab_reconciliation.py`): the disjointness comments currently say the proof rests on tx-ids being numeric — append a one-line note that this is **now ENFORCED at `SchwabTransactionResponse.__post_init__` (D20)**, so the proof is self-enforcing, not assumed. No logic change in `schwab_reconciliation.py`.

---

## §5 — Test obligations

- **Discriminating construction tests (the binding artifact):** `SchwabTransactionResponse(transaction_id="void:6", ...)` RAISES `ValueError`; same for `"oof:SPCX:2026-06-15"`, `"T100"`, `"abc"`, `"12.0"` (the dot fails `^[0-9]+$`). A numeric id (`"123"`, and the edge `"0"`) constructs fine. Empty string still rejected. **Regression-distinguishing (memory `feedback_regression_test_arithmetic`):** each raise-test must FAIL pre-fix (today the non-numeric value constructs cleanly — no raise) and PASS post-fix; the brief author confirms the test distinguishes by reasoning both paths.
- **Proof-closure assertion:** the `"void:6"` id can no longer be constructed → the PASS-1 `find_by_ref(ref="void:6")` collision against a `void:` sentinel row is unreachable BY CONSTRUCTION. A focused test asserting the construction barrier is sufficient; a recon-boundary test is optional (the input constraint alone closes it).
- **No-regression on valid data:** the mapper still maps a real (numeric) payload unchanged; the updated fixtures keep their suites green.
- **ASCII-only** user-facing string; **before-review full-suite run** + **`ruff check swing/`** clean.

---

## §6 — Gates (all binding)

- **Codex review-strong** (gpt-5.5/high, repo-access) to CONVERGENCE + **codex-auto-review** (matched).
- **CHARC QA** — architecture/tripwire (no-tripwire self-cert holds) + on-disk: the constraint lands at the single chokepoint, `integrations/schwab` is the only production touch, `schwab_reconciliation.py` logic byte-unchanged (comment-only), fixtures converted, streaks intact (ZERO `Co-Authored-By`, schema v31 unchanged).
- **RD — fyi** (not merge-blocking; see routing). 
- **NO operator §5.10 live-witness required** (validation-only; no user-visible/measurement-value change). 
- **Before-review full-suite + `ruff check swing/` clean.**

---

## §7 — Out of scope / follow-ups

- **A parallel check at the mapper / path-param** — unnecessary; the `__post_init__` is the single construction chokepoint.
- **The pre-existing `transactionId or activityId` falsy-`0` quirk** (`mappers.py:571` — an id of integer `0` falls through the `or`) — orthogonal to D20 and NOT a regression from this change (`str(0)="0"` passes `^[0-9]+$` regardless). Leave it; note only.
- **Any change to the reconciliation MATCHING logic** — the proof is closed by the input constraint alone; `schwab_reconciliation.py` gets comment hygiene only.

---

## §8 — Return report

The **ORCHESTRATOR** posts the return report to `charc` (+`rd` as fyi) **AFTER its own QA gate**. The implementer reports to its orchestrator in chat; it NEVER posts to a director inbox (memory `feedback_implementer_never_posts_to_directors`; CHARC §5.6).

---

## §9 — Dispatch model + effort recommendation

The design is fully settled in this brief (small, single-site, no ambiguity) — a lean writing-plans pass suffices.
- **writing-plans → `implementer-opus-high`** — settled design, small surface; the plan mainly nails the fixture sweep + the discriminating-test arithmetic.
- **executing → `implementer-opus-high`** — an input-validation hardening at the Schwab ingestion boundary: careful (measurement-adjacent) but NOT a measurement-value mutation, so `-high` (not `-max`). Select + announce per `docs/implementer-dispatch-recipe.md`.
