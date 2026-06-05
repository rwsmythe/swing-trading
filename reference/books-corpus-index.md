# Reference book corpus — index

Durable map of the transcribed trading-book corpus. **This index is tracked in git; the book
content is NOT** (`reference/Books/` and `reference/minervini/` are gitignored — see `.gitignore`
lines 123–124, operator-decided "keep untracked" 2026-06-04). So a fresh clone gets this index +
the converter, but must regenerate the `.md`/figures locally from the PDFs.

**Each transcribed book lives at** `reference/Books/<slug>/<slug>.md` + `reference/Books/<slug>/figures/*.png`.

**To (re)generate** from a PDF dropped in `reference/Books/`: `python scripts/convert_books_pdf_to_md.py`
(uses `pymupdf4llm`; idempotent — skips any book whose `<slug>.md` already exists). For a PDF outside
`reference/Books/`, call `convert_one(pathlib.Path(<pdf>))` from that script (it writes to
`reference/Books/<slug>/`). Figures are named `<pdf-stem>.pdf-PPPP-II.png` (page, image index).

> **Corpus status (2026-06-04): COMPLETE** — every book PDF on disk has a `.md` + figures.

---

## Minervini — PRIME (SEPA / trend-template / VCP; the core methodology our screen + detectors implement)

| Book | Author / year | Path slug | What it's for |
|---|---|---|---|
| **Trade Like a Stock Market Wizard** | Mark Minervini, 2013 | `trade-like-a-stock-market-wizard-2013` | SEPA, the 8-point trend template, VCP. **Dense annotated ticker+year chart examples** — the PRIME source for the Minervini exemplar-recall arc. |
| **Think & Trade Like a Champion** | Mark Minervini, 2017 | `mark-minervini-think-trade-like-a-champion-access-publishing-group-2017` | Specific entry points, risk/position management, sell-side specifics (the 7-week rule etc.). **Now available** — resolves the "NOT AVAILABLE" gaps in `reference/methodology/minervini-sell-side-rules.md` (M.1/M.4/M.5/M.6/M.7 re-verifiable). Consolidated here 2026-06-04 (was `reference/minervini/`). |
| **Momentum Masters** | Minervini, Ryan, Zanger, Ritchie II | `momentum-masters-mark-minirvani` | Roundtable Q&A — entry/exit/risk across four super-traders. |
| **Mindset Secrets for Winning** | Mark Minervini | `mind-secrets-for-winning-mark-minervini` | Trading psychology / discipline. |

## O'Neil / CANSLIM lineage (RS leadership, pocket pivots, buyable gap-ups)

| Book | Author / year | Path slug | What it's for |
|---|---|---|---|
| **Trade Like an O'Neil Disciple** | Morales & Kacher, 2010 | `trade-like-an-o-neill-disciple-2010` | CANSLIM, pocket pivots, buyable gap-ups, sell rules. |
| **In the Trading Cockpit with the O'Neil Disciples** | Morales & Kacher | `in-the-trading-cockpit-with-the-o-neil-disciples-strategies-that-made-us-18-000-in-the-stock-market` | Applied O'Neil-disciple case studies. |

## Stage analysis (the stage-1..4 model `trend_template.structural_stage` references)

| Book | Author / year | Path slug | What it's for |
|---|---|---|---|
| **Secrets for Profiting in Bull and Bear Markets** | Stan Weinstein, 1988 | `stan-weinstein-stan-weinsteins-secrets-for-profiting-in-bull-and-bear-markets-mcgraw-hill-1988` | Canonical stage-analysis source (stage 1–4). |

## Qullamaggie / execution

| Book | Author / year | Path slug | What it's for |
|---|---|---|---|
| **The Disciplined Swing Trader: Forging Consistency from Knowledge** | Dani (@trades_lakes), Qullamaggie-based | `the-disciplined-swing-trader-forging-consistency-from-knowledge` | A+ setup criteria, precision entries, rule-based exits, execution + psychology. **NOT a Minervini book** — community notes; complements the Qullamaggie KB. Methodology, not annotated ticker+date worked examples. |

## Momentum / superstocks

| Book | Author / year | Path slug | What it's for |
|---|---|---|---|
| **Insider Buy Superstocks** | Jesse Stine, 2013 | `insider-buy-superstocks-2013` | Explosive-growth small-cap momentum. |

## Market-Wizards interviews (Schwager — broad trader interviews; context, not setup rules)

| Book | Author | Path slug | What it's for |
|---|---|---|---|
| **Stock Market Wizards** (pt. 1 & 2) | Jack Schwager | `stock-market-wizards-interviews-with-america-s-top-stock-traders-1` · `…-2` | One book split across two transcription files. |
| **The New Market Wizards** | Jack Schwager | `the-new-market-wizards-conversations-with-america-s-top-traders` | Trader interviews. |
| **The Little Book of Market Wizards** | Jack Schwager | `the-little-book-of-market-wizards-lessons-from-the-greatest-traders` | Condensed lessons. |

## Trading psychology / general

| Book | Author / year | Path slug | What it's for |
|---|---|---|---|
| **Trading in the Zone** | Mark Douglas, 2000 | `mark-douglas-trading-in-the-zone` **and** `trading-in-the-zone-master-the-market-with-confidence-discipline-and-a-winning-attitude-2000` | ⚠️ **DUPLICATE** — two transcriptions of the same book. Prefer `mark-douglas-trading-in-the-zone`; the other is a redundant copy. |
| **Trading for a Living** | Alexander Elder, 1993 | `trading-for-a-living-psychology-trading-tactics-money-management-1993` | Psychology, tactics, money management. |
| **The Big Secret to Trading Success** | KJ Trading Systems | `the-big-secret-to-trading-success` | Systematic/algorithmic trading guide. |

---

## Non-book reference artifacts

- `reference/minervini/896159773-Minervini-Trading-Strategy-Deep-Dive.txt` — community strategy notes (non-book).
- `reference/minervini/Mark Minervini - Think & Trade Like a Champion…(2017).pdf` — redundant source PDF (the canonical transcription now lives under `reference/Books/`; an identical PDF also sits at `reference/Books/` top level).
- Internal project PDFs (not books, not transcribed): `legacy/swing_trading_task_list.pdf`, `reference/swing_trading_priority_terms_reference.pdf`, `reference/phase_0_3_chart_reading_fundamentals.pdf`.

## Known stale references to fix

- `reference/methodology/minervini-sell-side-rules.md` treats *Think & Trade Like a Champion* as "NOT AVAILABLE to operator" (lines 19, 81, 89, 93, 142–143) and left M.1 / M.4 (7-week rule) / M.5 / M.6 / M.7 unverified on that premise. The book is now transcribed — those rules are re-verifiable (ties to the backlog "Minervini + body-of-knowledge reference review").
