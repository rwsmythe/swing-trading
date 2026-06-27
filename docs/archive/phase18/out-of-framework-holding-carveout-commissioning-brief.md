# Commissioning brief — out-of-framework holding carve-out (path B)

**Author:** Research Director (RD), measurement-chain lane.
**Date:** 2026-06-17.
**Operator decision:** path B (ignore-entirely) — 2026-06-17, in response to the SPCX categorization question CHARC routed to the RD (`comms/rd/...charc-spcx-untracked-broker-position-categoriz.md`).
**Routes through CHARC:** YES — crosses the new-standing-concept tripwire (an operator-declared out-of-framework holdings registry) and a `swing/trades/` phase-isolation carve-out (the reconciliation service); likely a new schema object if the registry is a table. Architecture pass requested before dispatch.
**RD posture:** merge-blocking on the measurement locks (§3). This is instrument-integrity engineering, NOT research — commissioned against the standing stop-engineering default because it protects the measurement substrate from a recurring contamination trap (see §1).

---

## 1. Problem statement

The operator bought 2 SPCX IPO shares **outside the swing framework** on 2026-06-15 (~$412 market value), to **hold as a long-term investment** (operator-confirmed 2026-06-17). Phase 18 arcs 18-H.6 / 18-H.6.1 turned that untracked broker holding into a first-class `untracked_broker_position` reconciliation discrepancy. Live state: several SPCX orphan rows exist; the recon emits a **new orphan every run** while the position is untracked.

**Verified in code (not from memory):**
- **The orphan only stops re-emitting when the ticker has a journal OPEN trade.** The Schwab-driven orphan pass builds `journal_open_tickers = {t.ticker for t in open_trades}` and emits `untracked_broker_position` for every broker position whose ticker is NOT in that set (`swing/trades/schwab_reconciliation.py:1304-1367`). There is **no separate holdings registry** and **no cross-run suppression belt** for this discrepancy type — so each run emits a fresh orphan, and acknowledging one (the 18-H.6.1 `acknowledged_immaterial` resolver) does NOT stop the next. The classify/dispatch pivot deliberately leaves it `unresolved` (`:578-591`).
- **Strategy stats have no exclusion lever.** `compute_stats` (the expectancy / win-rate / total-R headline) sweeps ALL `closed`/`reviewed` trades and does **not** filter on `entry_intent` (`swing/journal/stats.py:179-204`). `entry_intent` is a classification facet only; its enum is `standard` / `hypothesis_test_by_design` / NULL (`swing/data/migrations/0027_entry_intent.sql`), all of which **presume a framework trade**. None means "out-of-framework, exclude from measurement."
- **The equity-coherence check is currently suppressed by the held position, not firing falsely.** The `equity_delta` check fires at full strength ONLY when `journal_flat AND broker_flat` (`schwab_reconciliation.py:1714-1722`); the ledger (`current_equity`, realized-only: `starting_equity + realized exits + cash_movements`) always diverges from broker NLV by the unrealized value of any open position, which is why the check is both-flat-gated. Because SPCX makes `broker_flat = False`, there is **no false `equity_delta` today** — the position surfaces only as the per-run orphan, plus a latent (un-checked) ledger≠NLV gap.

**Why the alternatives were rejected (decision record):**
- **Journal-as-normal-trade** — the one move that actively corrupts measurement: it fabricates an `initial_stop`/R-basis SPCX does not have, shows it as a swing position on the dashboard now, and folds its P&L into the headline the moment it is ever closed. REJECTED.
- **Acknowledge-nightly** — cry-wolf: a standing red banner that re-accrues every run erodes the recon's signal value (the same alarm-fatigue principle behind the 18-D monitor calibrations). REJECTED.
- **Path A (track-but-exclude)** — journal SPCX as an out-of-framework position the ledger includes but every stat surface excludes; would make this tool a total-account mirror. Considered; the operator chose B.
- **Path B (ignore-entirely)** — CHOSEN. An out-of-framework buy-and-hold is not swing capital; the purest separation keeps it out of the swing system entirely. Zero measurement contamination **by construction** (it never enters the `trades` table), and the operator tracks SPCX's investment performance in Schwab, where it belongs.

---

## 2. Scope — path B (ignore-entirely)

Carve declared out-of-framework holdings out of the swing system **at the reconciliation boundary**. SPCX (and any future declared holding) is never journaled as a trade.

**Required:**
1. **An operator-declared out-of-framework holdings registry** — the new standing concept. A list of tickers the operator explicitly declares out-of-framework (SPCX is the first). Mechanism (config vs table vs CLI-managed) is CHARC's call (§4).
2. **Orphan-pass carve-out** (`schwab_reconciliation.py:1304-1367`): do NOT emit `untracked_broker_position` for a ticker on the declared registry.
3. **Explicit, auditable visibility** (§3 L3): the carve-out surfaces in the recon output (e.g. a `#27`-style summary line "out-of-framework holdings excluded: SPCX 2sh @ $412") — never a silent suppression. An **undeclared** new untracked broker position MUST still banner.

**Design option (desirable, CHARC scopes — not required to stop the bleeding):**
4. **Swing-NLV coherence refinement:** redefine broker-flatness and NLV for the coherence check to exclude declared out-of-framework holdings — `broker_flat := (positions minus declared) is empty`, compare `ledger_equity` vs `source_nlv − Σ(declared MV)`. This lets the operator regain a TRUE both-flat swing-coherence confirmation even while holding SPCX (which today masks the flat state). Minimal B (items 1-3) already prevents a false `equity_delta`; this refinement is the "purest" B.

**Disposition of existing rows (§4):** the several existing SPCX `unresolved` orphan rows — resolve to `acknowledged_immaterial` on landing (clears the banner) vs leave to age. RD lean: resolve them (they are real-but-now-categorized); the carve-out prevents future ones.

---

## 3. Measurement LOCKS (RD merge-blocking)

- **L1 — Zero contamination by construction.** Declared out-of-framework holdings NEVER create a `trades` row, so they cannot touch `compute_stats`, `swing/metrics/cohort.py`, hypothesis-progress, process-grade, or any strategy surface. This is B's core property — the design must not create a trade/fill row for them anywhere.
- **L2 — No false equity signal, either direction.** The carve-out must NOT introduce a false `equity_delta` (minimal B already satisfies this — broker is non-flat while held). If the §2.4 coherence refinement is taken, it reconciles swing-ledger vs swing-NLV (NLV minus declared MV) and must not create a false coherence (hiding a real swing drift) nor a false drift.
- **L3 — Explicit, auditable, operator-declared — never silent/blanket.** Only tickers the operator explicitly declares are carved out. An undeclared new untracked broker position MUST still banner. The carve-out is surfaced in the recon output (the `#27` silent-skip-without-audit discipline). No "ignore all unknowns" blanket.
- **L4 — Measurement chain untouched.** The temporal log, candidates, shadow engine, and detector pipeline are not touched (SPCX is not a candidate; this is purely the reconciliation/equity boundary). `validate_bars` / the finiteness predicates / the research-health monitor are out of scope.

---

## 4. Open questions for CHARC / design

1. **Registry mechanism + location** — `user-config.toml` `[integrations.schwab]` (config, no schema) vs a small new table (schema tripwire) vs a CLI-managed list. Trade-offs: config is lightest; a table gives qty/declared-date/note provenance. CHARC's call.
2. **Equity-coherence refinement (§2.4)** — take it now or defer? Exact adjustment mechanics (subtract declared MV from NLV + redefine broker-flatness-for-swing) are CHARC's equity-machinery lane.
3. **Existing SPCX orphan rows** — resolve to `acknowledged_immaterial` on landing vs age. (RD lean: resolve.)
4. **Optional read-only display** — a "non-swing holdings" line on the account surface so the operator can see what's carved out (B-flavored visibility; optional).

---

## 5. CHARC architecture-pass triggers (why this routes through CHARC)

- **New standing concept** — the operator-declared out-of-framework holdings registry.
- **Phase-isolation carve-out** into `swing/trades/` (the reconciliation service) — default posture is read-only.
- **Possible new schema** — if the registry is a table (CHECK-enum or otherwise).

Per `docs/harness-architecture.md` §5, any one of these routes the brief through CHARC for a pre-dispatch architecture pass. RD requests: confirm the registry mechanism, scope the equity refinement (now vs defer), and rule on the existing-row disposition + module placement.

---

## 6. Verification mandates

- **Discriminating tests** (implementer): (a) a declared out-of-framework ticker held at the broker produces ZERO `untracked_broker_position` orphans across runs; (b) an **undeclared** untracked broker position STILL banners (proves the carve-out is not a blanket suppression — the L3 discriminator); (c) the carve-out is surfaced in the recon summary/warnings; (d) if §2.4 is taken: flat-on-swing-while-holding-declared → coherence check runs against swing-NLV and does not emit a false `equity_delta`; (e) declared out-of-framework holdings never appear in `compute_stats` / cohort / hypothesis surfaces (the L1 structural assertion).
- **Operator live gate** (binding): on the live DB, after declaring SPCX out-of-framework, a real reconciliation run emits no SPCX orphan, the banner clears, and a genuinely-new untracked position would still fire. Mirrors the 18-H.6 live-witness discipline.
- **RD merge-blocking sign-off** at the executing return, verified against the shipped diff for L1-L4.

---

## 7. Explicitly OUT of scope

- Path A (total-account mirror) — not chosen.
- Any change to strategy-stat computation surfaces (B needs none — L1 holds by construction).
- Any measurement-chain / shadow-engine / monitor change (L4).
- A general cross-run suppression belt for `untracked_broker_position` beyond the declared-registry carve-out (if CHARC wants one for undeclared orphans, that is a separate arc).
