# Disciplined Swing Trader — Take-profit + Trail Rules

**Source:** *Disciplined Swing Trader* — _________ (full citation pending operator transcription).
**Transcribed:** _________ by _________
**Status:** ⚠ SCAFFOLDING — operator transcription pending per phase3e-todo §3e.8 §4.G operator-action.

---

## Provenance + format

This file follows the `minervini-trend-template.md` precedent: source citation + verbatim or paraphrased transcription + operator interpretive notes. Each section below corresponds to a DST sell-side claim referenced in the [3e.8 sell-side advisories investigation](../../docs/3e8-sell-side-advisories-investigation.md) §6.4 `[UNVERIFIED]` triage matrix (rows 8-12).

For each rule the operator either:
- **CONFIRMED** — fills in source citation + verbatim text below; updates `Status` line accordingly
- **CORRECTED** — fills in actual rule from source; notes how the §3e.8 paraphrase differed
- **NOT-PRESENT** — explicitly notes the rule is absent from the surveyed chapters; updates `Status` to `NOT-PRESENT-IN-SOURCE`

Once all 5 rules are dispositioned, the `Status` line at the top flips from `⚠ SCAFFOLDING — operator transcription pending` to `✓ COMPLETE` (or `~ PARTIAL — N/5 rules dispositioned`). When `Status` flips to `✓ COMPLETE`, this file becomes a reference-grade source-of-truth per V2 Addendum Addition 2.

---

## D.1 — Initial stop placement (below swing low or breakout pivot's reaction low)

**Source citation:** _________ (chapter, page)
**Status:** ⚠ UNVERIFIED — pending operator transcription

**Transcription:**

```
[Operator drops verbatim text or paraphrase here]
```

**Operator notes:**

```
[Optional]
```

---

## D.2 — Take partial profit into strength (1/4 to 1/3 reduction)

**Source citation:** _________ (chapter, page)
**Status:** ⚠ UNVERIFIED — pending operator transcription

**Transcription:**

```
[Operator drops verbatim text or paraphrase here]
```

**Operator notes:**

```
[Optional]
```

**Cross-reference:** §3e.8 §4.B (trim/sell-into-strength advisory) commissioned in implementation bundle 2. Default trim percentage (25%) is operator-tunable; D.2's specific 1/4 to 1/3 range may re-anchor it.

---

## D.3 — 10-EMA fast movers vs 20-SMA steady names

**Source citation:** _________ (chapter, page)
**Status:** ⚠ UNVERIFIED — pending operator transcription

**Transcription:**

```
[Operator drops verbatim text or paraphrase here]
```

**Operator notes:**

```
[Optional]
```

**Cross-reference:** §3e.8 §4.A.bis (maturity-stage hint advisory) commissioned in implementation bundle 3. The Tier-3 #6 doctrine framing (default 20MA pre-+2R; upgrade to 10MA post-+2R) maps onto this rule. D.3's confirmation here strengthens the doctrinal basis for the maturity-stage gating.

---

## D.4 — Tighten stop after +2R

**Source citation:** _________ (chapter, page)
**Status:** ⚠ UNVERIFIED — pending operator transcription

**Transcription:**

```
[Operator drops verbatim text or paraphrase here]
```

**Operator notes:**

```
[Optional]
```

**Cross-reference:** §3e.8 §4.A (full classification-altering trail-MA gating) deferred. D.4's confirmation here is a precondition for V2.1 §VII.F routing of §4.A if/when commissioned.

---

## D.5 — 7-10 day vs 7-week time-stop

**Source citation:** _________ (chapter, page)
**Status:** ⚠ UNVERIFIED — pending operator transcription

**Transcription:**

```
[Operator drops verbatim text or paraphrase here]
```

**Operator notes:**

```
[Optional]
```

**Cross-reference:** §3e.8 §4.C/§4.C.bis (time-stop discipline) deferred. D.5's confirmation here, alongside M.4 in `minervini-sell-side-rules.md`, is needed before either time-stop default change is informed.

---

## Footnotes / qualifiers (as printed)

```
[Operator notes any source-text footnotes / qualifiers attached to the above rules]
```

---

## Usage notes (not from source — interpretive)

- This file is **reference material only**. Do not edit production code to "match" the rules above without routing the change through the research-branch promotion cycle per V2 Addendum Addition 2 (source-of-truth correction protocol).
- Any discrepancy between current production advisory logic and the rules above is a research question, not a defect.
- Numerical thresholds in the source take precedence over `[UNVERIFIED]` paraphrases that appeared in 3e.8 investigation analysis. Once a rule is CONFIRMED here, the corresponding `[UNVERIFIED]` flag in `docs/3e8-sell-side-advisories-investigation.md` §6.4 may be updated.
- Rule labels (D.1-D.5) are project-internal taxonomy from the 3e.8 investigation, not DST's own numbering. Operator may keep or rename as desired during transcription.
