# Phase-14 Cross-Sub-Bundle Integration Review -- Operator Coherence Checklist

**What this is:** the Phase-14 close-out item (commissioning brief Sec 9.1 Q6) -- an **operator-driven browser walkthrough** confirming the Phase-14 sub-bundles **cohere as one surface**: consistent session anchors, consistent per-trade/per-ticker data across pages, working cross-references, legible light + dark mode, and graceful empty/default states. NOT a feature; a retrospective QA pass. One of the two small near-term items (with the finviz fix); precedes the data-integrity arc.

**What "coherence" means here:** the sub-bundles shipped independently (SB1 data-wiring · SB2 temporal-log · SB3 charts · SB4 review/journal · SB5 metrics · SB5.5 Schwab + the close-out/follow-on batches). This pass checks the **seams between them** -- the same date everywhere, the same trade's numbers everywhere, thumbnails matching their full charts, no broken cross-links, no blank boxes where an empty-state caption belongs.

**How to run:** stand up the app and click through the sections below in order. For each check, mark **OK** or log an issue in §Issues at the bottom (the orchestrator triages each into a follow-up fix). Your live DB has limited data (Run 89 just ran; few/no open trades; likely <5 reviewed trades) -- that is EXPECTED; several surfaces will show **empty/default states**, and verifying those render gracefully (captions, suppression floors -- NOT blank boxes) is part of the pass (the "witness the unseeded default" discipline).

```
swing web            # http://127.0.0.1:8080  (or note your port)
```
Toggle dark/light mode on each visual surface (the theme switch) -- the SVG-text-needs-`fill` gotcha (#22) means dark-mode legibility is a real failure surface.

---

## A. Dashboard ( `/` or `/dashboard` ) -- SB1 wiring + P14.N1 thumbnails + SB3 weather/trend
- [ ] **Topbar date** is present + correct (the last completed session). NOTE the exact date shown -- you will cross-check it on every other page (§J).
- [ ] **Open-positions table** renders; each row's **thumbnail** (P14.N1) renders (no broken-image icon) and visually matches that ticker's price action. Click a row to **expand** (`/trades/open/{id}/expand`) -- the expand opens WITHOUT the row collapsing/wiping (the hx-target row-collapse gotcha). [If zero open trades: the empty state reads cleanly.]
- [ ] **Hypothesis-recommendations table** renders; its **thumbnails** (`/hyp-recs/{ticker}/thumbnail`) render + match. [Empty state OK if none.]
- [ ] **Daily-management tile** (SB1): the "covers this row's session date" wording is right; the PROVISIONAL flag behavior is sane.
- [ ] **Market-weather** (SB3 F-2): the weather status + the trend render; the weather-chart (`/dashboard/weather-chart/refresh`) draws in BOTH light + dark (no invisible lines).
- [ ] **In-progress bar** (if a pipeline ran recently) reflects the right session.

## B. Watchlist ( `/watchlist` ) -- SB1 + thumbnails
- [ ] Rows render; **expand** (`/watchlist/{ticker}/expand`) works; thumbnails render + match. [Empty OK.]
- [ ] The watchlist's "as of" framing matches the dashboard date (§A topbar).

## C. Charts -- SB3 (v23 ticker_detail) + the segmented-polyline/spine work (F-3/F-4)
- [ ] A full chart (`/charts/{TICKER}.png` for an open-trade or watchlist ticker, or via a row's chart link) renders: axes legible, the price series + SMAs draw, no mathtext/`$` artifacts in labels.
- [ ] A **thumbnail and its full chart agree** -- same ticker, same recent window, same shape (the thumbnail is a faithful mini of the chart, not a different window).
- [ ] Dark + light both legible.

## D. Journal ( `/journal` ) -- SB4
- [ ] The journal listing renders with per-trade **thumbnails** (SB4); each `/journal/trades/{id}` detail opens; the `/journal/trades/{id}/chart` renders.
- [ ] A trade's **journal numbers** (entry / stop / exit / R / pattern) match what the same trade shows on the dashboard (if open) and the review surface (§E). [If no closed trades: empty state OK.]

## E. Reviews + post-trade review ( `/reviews/pending`, `/trades/{id}/review` ) -- SB4 + B-7 (#21) + nav-date (#22)
- [ ] **`/reviews/pending` topbar shows the date** (the #22 nav-date fix -- it must NOT be blank, and must match §A).
- [ ] Open a review (`/trades/{id}/review` or a pending review): the form renders; the **process-grade + mistake-tags + the B-7 `failure_mode` select** (#21) all present + independent (failure_mode is optional/NULL-able).
- [ ] The review chart (`/trades/{id}/review/chart`) renders.
- [ ] [If you have a reviewed trade] its grade/failure-mode here is consistent with how it appears in the metrics tiles (§F).

## F. Metrics overview ( `/metrics` ) + the 9 tiles -- SB5 + #22 (process-grade-trend) + #23 (pattern-outcomes isolation)
- [ ] **`/metrics` overview** renders; the 9 tile cards/sparklines draw in light + dark (the `var(--accent)` dark token).
- [ ] Visit each tile and confirm it renders + handles the under-floor/empty default (a caption, not a blank box): `/metrics/trade-process` · `/metrics/tier-comparison` · `/metrics/deviation-outcome` · `/metrics/capital-friction` · `/metrics/maturity-stage` · `/metrics/identification-funnel` · `/metrics/process-grade-trend` · `/metrics/pattern-outcomes` · `/metrics/hypothesis-progress`.
- [ ] **`/metrics/process-grade-trend`** (#22 redesign): the 3 small-multiple panels (GRADES / RATE / COST) are each legible against their own scale -- NO plunge-lines -- in BOTH light + dark (the axis/legend/caption text is visible in dark -- the gate-fix).
- [ ] **`/metrics/pattern-outcomes`** (#23): renders; under-floor/suppressed cells read cleanly. **Invisible-widen check:** this tile + the pattern queue (§G) should reflect ONLY aplus-origin patterns -- the 55 watch detections Run 89 just wrote must NOT appear here.

## G. Patterns ( `/patterns/queue`, `/patterns/exemplars` ) -- SB2/Phase-13 + #23 isolation
- [ ] **`/patterns/queue`** (the active-learning review queue) renders. **Invisible-widen check:** it should NOT be flooded by the ~watch detections -- the #23 isolation keeps it aplus-origin. (Post-Run-89, confirm it isn't suddenly showing dozens of watch-ticker review items.)
- [ ] `/patterns/exemplars` renders.

## H. Schwab status ( `/schwab/status` ) -- SB5.5 + schwabdev-v3 (#20)
- [ ] The status page renders the **live token state** (presence/days-remaining) off the v3 reader. [Note: the topbar Schwab BADGE was removed in the v3 arc; the page is the single health surface.]
- [ ] It does NOT error / show a stale daemon-checker artifact (the v3 arc deleted the daemon checker).

## I. Pipeline ( `/pipeline` ) -- SB1
- [ ] The pipeline surface shows **Run 89** (or the latest) as complete with its session date; the two-read state (last-good vs what's-happening) reads sanely.

## J. CROSS-SURFACE COHERENCE (the heart of this review)
- [ ] **One date everywhere:** the topbar/"as of" date is IDENTICAL across dashboard, watchlist, reviews-pending, journal, metrics. (The session-anchor gotcha family -- a mismatch here is the classic Phase-14 seam bug.)
- [ ] **One trade, one set of numbers:** pick any one trade (open or reviewed) and confirm its ticker/entry/stop/pattern/grade read the SAME on every surface that shows it (dashboard ↔ journal ↔ review ↔ metrics).
- [ ] **Thumbnails are faithful minis** of their full charts (not a different ticker/window) everywhere they appear (dashboard, watchlist, hyp-recs, journal).
- [ ] **Dark mode is uniformly legible** -- no invisible chart/sparkline/axis text on ANY surface.
- [ ] **Empty/default states are graceful everywhere** -- captions + suppression floors, never a blank box, given your sparse live data.
- [ ] **Cross-links resolve** -- row expands, chart links, review links all open the right thing (no 404/blank).

---

## K. OPTIONAL -- light recon for the data-integrity arc (note only; do NOT act)
While you are clicking through the charts + metrics, jot anything that looks like **stale current-day data** (a chart whose last bar looks like an in-progress/partial day) or **obviously-off OHLC** (a candle whose body pokes outside its high/low -- the extended-hours artifact). This is NOT part of the coherence pass and needs no action -- it is free early recon for the upcoming regular-session + completed-day data-integrity arc. Drop any sightings in §Issues tagged `[data-recon]`.

---

## Issues log (operator fills; orchestrator triages each into a follow-up)

| # | Surface / route | What's wrong | Light/Dark | Severity (your gut) |
|---|---|---|---|---|
| 1 | | | | |
| 2 | | | | |

*(Add rows as needed. Tag data-integrity sightings `[data-recon]`. When you're done, hand the filled log back -- the orchestrator converts each coherence issue into a small fix and parks the `[data-recon]` notes for the data-integrity arc.)*

---

*End of checklist. Phase-14 cross-sub-bundle integration review -- an operator browser walkthrough confirming the independently-shipped sub-bundles (SB1-SB5.5 + close-out/follow-on) cohere: one session date everywhere, one trade's numbers everywhere, faithful thumbnails, uniform dark-mode legibility, graceful empty states, and the #23 invisible-widen holding in the live pattern-outcomes tile + queue. Log issues; the orchestrator triages.*
