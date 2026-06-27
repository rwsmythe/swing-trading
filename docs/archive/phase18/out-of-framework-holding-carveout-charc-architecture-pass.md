# CHARC architecture pass — out-of-framework holding carve-out (path B)

**Author:** CHARC. **Date:** 2026-06-17. **Responds to:** RD commissioning brief `docs/out-of-framework-holding-carveout-commissioning-brief.md` (`78d6d5e6`). **Operator-confirmed:** 2026-06-17 (all rulings). **RD merge-blocking** on locks L1–L4 (RD brief §3).

The CHARC pre-dispatch §3 architecture pass RD requested. Tripwire triggers: a new standing concept (the out-of-framework holdings registry) + a `swing/trades` phase-isolation carve-out (the reconciliation service) + possible new schema. The verdict + rulings carry into writing-plans.

## Verdict: GO — the tripwires resolve to a config-registry + a scoped carve-out, **NO schema**.

## Ruling 1 — Registry: config-list, NOT a table
A declared `out_of_framework_tickers` list in `user-config.toml` (a dedicated key — `[reconciliation]` reads cleaner than overloading `[integrations.schwab]`; the implementer/RD finalize the exact key). The path-B carve-out only needs the ticker SET to skip the orphan emit; qty/MV come from the broker pull, not the registry. A table buys per-entry provenance (qty/declared-date/note) the path-B logic never uses, at the cost of a v31→v32 migration + the #11 discipline. **L3 auditability without a table:** the toml IS the operator's explicit declaration, and the recon surfaces what it excluded each run (the #27 summary line). **Config, no schema.** A thin CLI to add/remove is optional polish, not required.

## Ruling 2 — §2.4 coherence refinement: DEFER (operator-confirmed)
Minimal B (items 1–3) already prevents the false `equity_delta` — the bleeding is stopped. §2.4 (swing-NLV = NLV − Σ declared MV, redefined broker-flatness) is the "purest B," but it is **L2-delicate**: a wrong swing-NLV redefinition produces a FALSE coherence — a "flat + coherent" green that hides a real swing drift — strictly worse than the check being suppressed. That false-green risk + its narrow-window value (swing-flat-while-holding) warrant a focused arc, not a bundle. **§2.4 = a registered fast-follow** (commissioned focused if the operator wants the swing-flat coherence check restored while holding declared positions). **Tradeoff on record:** deferring keeps the equity-coherence check suppressed for as long as SPCX is held.

## Ruling 3 — Existing SPCX orphan rows: resolve (concur with RD)
Resolve the existing declared-ticker (SPCX) `unresolved`/`pending_ambiguity` orphan rows to `acknowledged_immaterial` at landing — SCOPED to declared tickers only, with an audited `resolution_reason` (the out-of-framework declaration). Clears the banner immediately; the carve-out prevents future ones. Mechanism (a scoped landing step vs the existing 18-H.6.1 web resolver) is the implementer's call; the landing step is cleaner.

## Module placement — no new module
- **Registry:** a config field (`swing/config` + `user-config.toml`).
- **Carve-out:** `swing/trades/schwab_reconciliation.py` — the orphan pass reads the declared set + skips declared tickers + emits the #27 exclusion line in the recon summary.
- **Optional thin CLI:** `cli_config.py`.
- The read-only `swing/trades` default returns after the arc.

## Binding conditions (carry into writing-plans)
- **C1** — declared holdings NEVER create a `trades`/`fills` row (RD L1, the structural property path B rests on — verified by construction: the carve-out skips the orphan emit; it never journals).
- **C2** — an UNDECLARED untracked broker position STILL banners; the carve-out is surfaced in the recon output (the #27 silent-skip-without-audit discipline); NEVER a blanket "ignore unknowns" (RD L3).
- **C3** — existing declared-ticker orphans resolved scoped + audited (Ruling 3).
- **C4** — §2.4 DEFERRED (Ruling 2); minimal B (items 1–3) only.
- **C5** — config-registry, NO new schema, NO new module/standing-process (the "new standing concept" is realized as a config list).
- **Carve-out scope:** `swing/trades/schwab_reconciliation.py` + the `swing/config` key (+ the scoped existing-row resolve). Default read-only returns after.

## Locks preserved (RD merge-blocking)
RD's L1–L4 (zero contamination by construction / no false equity signal / explicit-auditable-operator-declared / measurement chain untouched) are RD's to QA at the executing return; this pass does not weaken them.

## Tripwire disposition
- **New standing concept** → realized as a CONFIG list (no new table/daemon/process). PASS.
- **`swing/trades` carve-out** → AUTHORIZED, scoped to `schwab_reconciliation.py` (+ the config key). Default read-only returns after.
- **New schema** → AVOIDED (config, not a table). No migration.
