# Entry-form rider (D47 companion + D97 + D98) -- ledger note

**Brief:** `docs/phase22-rider-entry-form-dispatch-brief.md` @ `2f185264` (CHARC dispatch `20261115T023210Z`, on the operator's words).
**Merged:** `git merge --no-ff 49219b63` -> `8aa72d1d` (tree `86a93b7c`). Merged-head suite 16284 passed / 13 skipped / 0 failed, EXIT=0.
**Commits:** `04c2d6a8` D97 · `e3926c10` D47 companion · `641b372e` D98 · `49219b63` Codex R1 minor 1 (overflowing geometry is unsized, never a 500).
**Review:** Reviewer A round 1 `NO_NEW_CRITICAL_MAJOR` (R1-3, pre-existing, banked on D47 by CHARC). Reviewer B attempt 1 VOID (the final message said the review was not completed); attempt 2 clean, final message read.
**CHARC acceptance:** `20261115T040523Z` (msg-id `cdd94adbf46450de`). Courier's summary, not a quote: the deviations were accepted as reported, R1-3 banked on D47, and the void-token rule ruled.
**Evidence:** `~/swing-data/review-transcripts/entry-form-rider/`.

## Operator browser witness (brief section 5) -- PASSED 2026-11-14

Unseeded live default state; `swing web` restarted 18:15 HST on the merged code (merge 17:48), port 8080 verified free before the start. Pre-witness read (`mode=ro`): schema 42, `trades` = 29. One step per message.

1. **PASSED.** Entry form for watchlist ticker **GO**: its risk figure agrees with the card on the floored budget. The form's classification line read `risk_feasibility: pass - 18 sh, $36.27 risk (>= 1 share fits in 0.5% of equity ($37.50))`.
2. **PASSED.** Pre-trade answers filled, rationale blank, submit: an error returned and every other answer stayed as entered (operator's words: "I submitted with the blank rationale and received an error, all other entries remained unchanged.").
3. **PASSED.** On the returned form: entry 12.65, stop 11.73, `Suggested max: 40 sh (~$36.80 risk = 0.49%)`. Check: 0.92 per share; floor(37.50 / 0.92) = 40; 40 x 0.92 = 36.80; 36.80 / 7500 = 0.49%. Sized on the prices it shows.
4. **PASSED.** Cancel clicked; `trades` = 29 read `mode=ro` afterwards. Nothing written.

The 18 sh / $36.27 line in step 1 is the nightly criterion's geometry (its own pivot and stop), not the form's; both size on the same floored $37.50.
