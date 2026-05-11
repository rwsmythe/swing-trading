# Minervini SEPA Sell-side Rules

**Source:** *Trade Like a Stock Market Wizard*, Mark Minervini, McGraw Hill 2013.
**Transcribed:** _________ by _________
**Status:** ⚠ SCAFFOLDING — operator transcription pending per phase3e-todo §3e.8 §4.G operator-action.

---

## Provenance + format

This file follows the `minervini-trend-template.md` precedent: source citation + verbatim or paraphrased transcription + operator interpretive notes. Each section below corresponds to a sell-side claim referenced in the [3e.8 sell-side advisories investigation](../../docs/3e8-sell-side-advisories-investigation.md) §6.4 `[UNVERIFIED]` triage matrix (rows 1-7).

For each rule the operator either:
- **CONFIRMED** — fills in source citation + verbatim text below; updates `Status` line accordingly
- **CORRECTED** — fills in actual rule from source; notes how the §3e.8 paraphrase differed
- **NOT-PRESENT** — explicitly notes the rule is absent from the surveyed chapters; updates `Status` to `NOT-PRESENT-IN-SOURCE`

Once all 7 rules are dispositioned, the `Status` line at the top flips from `⚠ SCAFFOLDING — operator transcription pending` to `✓ COMPLETE` (or `~ PARTIAL — N/7 rules dispositioned`). When `Status` flips to `✓ COMPLETE`, this file becomes a reference-grade source-of-truth per V2 Addendum Addition 2.

---

## M.1 — 1.25× backstop expectancy heuristic

**Source citation:** _________ (chapter, page)
**Status:** ⚠ UNVERIFIED — pending operator transcription

**Transcription (verbatim or paraphrased):**

```
[Operator drops verbatim text or paraphrase here]
```

**Operator notes / interpretation:**

```
[Optional operator interpretation; how this rule maps to framework state]
```

---

## M.2 — Sell into strength

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

**Cross-reference:** §3e.8 §4.B (trim/sell-into-strength advisory) commissioned in implementation bundle 2; default thresholds (+1R / 25%) are operator-tunable and may be re-anchored to specific values from this rule.

---

## M.3 — Sell on close below N-day MA (specific N values)

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

**Cross-reference:** Existing framework rules `exit_below_10ma` / `exit_below_20ma` / `exit_below_50ma` ([`swing/trades/advisory.py`](../../swing/trades/advisory.py)) — verify N values match Minervini's specific guidance.

---

## M.4 — 7-week rule (time-stop)

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

**Cross-reference:** §3e.8 §4.C/§4.C.bis (time-stop discipline) deferred. Resolution of M.4 here is a precondition for revisiting whether to raise the global default from 10/0.5R to 49/0.X (or per-hypothesis override).

---

## M.5 — Parabolic / blow-off-top extension thresholds

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

**Cross-reference:** §3e.8 §4.D (parabolic-extension detector) commissioned in implementation bundle 2. Default thresholds (25% / 5 days / 15% above 20MA) are operator-tunable; M.5's specific values may re-anchor them.

---

## M.6 — Violated MA on volume

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

**Cross-reference:** §3e.8 §4.I (volume-confirmed close-below-MA overlay) deferred with §4.G-completion-gate-trichotomy. Resolution of M.6 here drives one of three dispositions:
- **Specific volume threshold** in source → §4.I gets commissioned with confirmed defaults
- **Qualitative without threshold** → §4.I escalates to second-source gate (like §4.H)
- **Not present in source** → §4.I dropped

---

## M.7 — Gap-down on news

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

## Footnotes / qualifiers (as printed)

```
[Operator notes any source-text footnotes / qualifiers attached to the above rules]
```

---

## Usage notes (not from source — interpretive)

- This file is **reference material only**. Do not edit production code to "match" the rules above without routing the change through the research-branch promotion cycle per V2 Addendum Addition 2 (source-of-truth correction protocol).
- Any discrepancy between current production advisory logic and the rules above is a research question, not a defect.
- Numerical thresholds in the source (specific MA periods, percentage thresholds, volume multipliers, time windows) take precedence over `[UNVERIFIED]` paraphrases that appeared in 3e.8 investigation analysis. Once a rule is CONFIRMED here, the corresponding `[UNVERIFIED]` flag in `docs/3e8-sell-side-advisories-investigation.md` §6.4 may be updated.
- Rule labels (M.1-M.7) are project-internal taxonomy from the 3e.8 investigation, not Minervini's own numbering. Operator may keep or rename as desired during transcription.
