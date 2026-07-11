# Broker↔Ledger Forensic Reconciliation — 2026-07-10

**Method:** operator transcribed the COMPLETE Schwab transaction history from account opening (first line 2026-01-19); CHARC verified every line against the ledger (fills + cash_movements) with a running cash reconstruction. **Result: the account reconstructs from $0 to the current swing cash $1,555.80 (NLV $2,010.70 − OOF MV $454.90) TO THE CENT, and the standing equity_delta residual (−$10.94 post-RKLB-recording) is FULLY attributed.** Operator confirmed NO other lines exist (no interest, no dividends, no separate fee lines).

## The residual decomposition (broker minus current_equity basis)

| Component | Amount | Cause |
|---|---|---|
| AMN 2026-07-07 trim fill mis-recorded | **+$10.77** | real fill 3 @ 35.65 = $106.95; the fills row carries 3 @ **32.06** = $96.18 — 32.06 is the 07-09 STOP leg's price |
| Net penny fill-drift across ~15 fills | +$0.20 | journal prices rounded vs true fills (largest: CVGI entry +0.11 [5.2244 vs 5.23], DHC exit +0.10, LION exit −0.09, PTEN exit +0.08) |
| SATL phantom test pair (trade 11) | −$0.01 | journal-only 1-share round trip 05-22 (10.31/10.32) — NEVER executed at the broker (operator: app-workflow test trades) |
| realized_pnl rounding residue | −$0.02 | per-trade rounding |
| **Total** | **+$10.94** | ✓ exact |

## FINDING 1 — THREE corrupted fill rows (a systematic class, register D25)

In each case the fills row carries a DIFFERENT LEG'S price of the same trade instead of the real fill:

| Trade | Leg | fills row says | REAL (broker statement) | Cash error | Note |
|---|---|---|---|---|---|
| PTEN (10) | ENTRY 15 sh | 12.3047 (−184.57) | **13.00** (−195.00) | −10.43 | the corrupt value ≈ the EXIT price (12.30/12.305); trades-row entry_price 13.00 was CORRECT |
| DFTX (16) | ENTRY 7 sh | 22.16 (−155.12) | **24.53** (−171.71) | −16.59 | the corrupt value = the EXIT price EXACTLY; trades-row 24.53 CORRECT |
| AMN (18) | TRIM 3 sh 07-07 | 32.06 (+96.18) | **35.65** (+106.95) | +10.77 | the corrupt value = the 07-09 STOP price EXACTLY; entry + stop legs verified correct |

PTEN −10.43 + DFTX −16.59 = −27.02 also EXACTLY closes the previously-unexplained internal gap between the fills-implied trading flow (−$53.52) and Σrealized_pnl (−$80.52): `realized` derives from the (correct) trades-row entry prices, the fills rows carry the corruption. **Mechanism unknown — three instances of one shape (another leg's price written into a fill row) says defect, not typo; candidate suspects: the exit/trim recording flow, auto-fill, or TOS-import matching. Investigation + correction = a Phase-20 arc.**

## MECHANISM PINNED (2026-07-11, from the system's own `reconciliation_corrections` audit rows)

**The reconciliation tier-1 auto-corrector CAUSED all three corruptions.** Corrections #28 (05-21: PTEN entry `13.00 -> 12.305` auto) and #30 (06-03: DFTX entry `24.53 -> 22.16` auto) overwrote CORRECT journal prices with the trade's OTHER LEG's execution price, resolving each as `auto_corrected_from_schwab`. Correction #33 (07-08) fixed the AMN trim correctly (`35.75 -> 35.65`), then #34 (07-10) RE-FIRED and overwrote the now-correct value with the 07-09 STOP leg's price (`35.65 -> 32.06`). **All three trades have same-ticker SAME-QUANTITY leg pairs (15/15, 7/7, 3/3): the fill->execution matcher, facing two same-qty candidates, picks the wrong leg — no side discrimination (SELL executions matched to BUY entry fills), no date-proximity guard — always corrupting on the run AFTER the other leg executes.** Prior: the operator manually OVERRODE the same matcher class on 05-17 (corrections #3/#4/#6, CVGI/LION limit-vs-execution) — tier-1 then removed the human from the loop.

**Safeguards absent (the Phase-20 arc's fix list):** (1) same-qty multi-candidate match = AMBIGUITY -> tier-2, never tier-1 auto; (2) plausibility guards (side must match; execution date near fill date; % band on overwrites); (3) a re-correction alarm (a second auto-correction of the same fill to a DIFFERENT value contradicts "canonical" by definition — #34 should have been loud or impossible); (4) a fills.price vs trades.entry_price consistency invariant (the corrector itself created the divergence and nothing watches it); (5) the self-seal: post-correction runs compare against the same mis-match -> silence forever. **The equity_delta monitor caught the AMN corruption within 24h ($10.94 > $10) — the one net that worked.**

## FINDING 2 — MEASUREMENT impact (RD lane; AMN is a standard-cohort epoch trade)

- **AMN's recorded outcome is materially WRONG:** recorded realized (32.06 both exits vs entry 33.66) = **−$9.60**; TRUE realized (trim 35.65 + stop 32.06) = **+$1.17**. The day-3 partial was recorded as a LOSS leg; it was actually a +5.9% WIN leg. AMN feeds H1 (standard cohort, closed 07-09) — must be corrected before the August monthly read.
- **SATL trade 11 never happened** — a phantom journal-only trade inside the (pre-epoch, tuition) cohort counts.
- PTEN/DFTX realized values are correct (they used the trades-row prices) — their FILLS are wrong, so any fills-derived analysis (journal stats, derived_metrics, VWAP-class computations) is contaminated for those trades.

## FINDING 3 — minor

- The 07-01 auto-ingested deposit (movement #7) is dated 06-30 on the statement (settlement-vs-transaction date drift in the ingest). Cosmetic.
- Sell-side SEC/TAF fees are baked into broker net amounts at sub-cent-to-few-cent scale; the ledger's fees=0 convention absorbs them into the price — part of the +$0.20 penny-drift, acceptable.

## Corrections queue (operator + RD semantics; commission as a Phase-20 arc)

1. Fix the 3 fill rows (PTEN entry −184.57→−195.00 @13.00; DFTX entry −155.12→−171.71 @24.53; AMN trim 96.18→106.95 @35.65) through a SUPPORTED audited path (`operator_corrected_value_json` / the correction service — design at commissioning; never raw UPDATE).
2. Disposition the phantom SATL trade 11 (remove/annotate — RD rules the cohort semantics).
3. Investigate the corruption mechanism (which flow wrote another leg's price into these fill rows) + add a write-time guard if pinned.
4. After corrections: current_equity rises ~$10.94 → the equity_delta goes to ~$0.00-0.17 → the badge clears WITHOUT any tolerance change (the $10 tolerance was right; the DATA was wrong — the D24 root-fix framing updates accordingly).
