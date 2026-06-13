# Phase 17 — 17-D.5: Weather mini-chart axis-label declutter (FIX-DIRECT)

**Audience:** A fresh Claude Code instance with no prior conversation context. This is a small, operator-specified bug fix in the 17-D bug container — one renderer, ~2 lines + a regression test + an operator visual gate. Known mechanism; no investigation phase.

**Mission:** Remove the overlapping axis labels from the "Market weather (SP500 daily)" mini-chart: drop the **"Price"** ylabel, the **"Volume"** ylabel, and the **"10^6"** scale-factor — on the weather chart ONLY. Leave everything else (candlesticks, MA line, the `trend: stage_2` badge, the left/right price ticks, volume bars, date axis).

**Expected duration:** ~30–45 min including the visual gate.

---

## §0 Read first
- [`swing/web/charts.py`](../swing/web/charts.py): `render_market_weather_svg` (≈L827 — the target); `_render_candles_fig` (≈L477 — the shared builder, returns `(fig, price_ax, vol_ax)`); `_resolve_volume_ax` (≈L436, docstring explains the `"Volume  $10^{6}$"` mpf scale-factor suffix); `render_ticker_detail_svg` (≈L632) + `render_position_detail_svg` (≈L721) — these explicitly `set_ylabel("Price (USD)")`/`set_ylabel("Volume")` and **must stay unchanged**.
- [`tests/web/test_charts_volume_yticks_stripped.py`](../tests/web/test_charts_volume_yticks_stripped.py) — the canonical test family for this chart; note `test_render_ticker_detail_preserves_volume_ylabel` (the scope-LOCK guard you must NOT break) and the spy/rebuild helpers.
- CLAUDE.md §Gotchas "Matplotlib mathtext fires on `$` `^` `_`" and "Byte-parity tests are INSUFFICIENT substitutes for operator-visual gates when fixtures bypass the production data-derivation path."

**Skill posture:** TDD (failing test → fix → pass). After the fix lands, run a standalone `copowers:review` (light adversarial — the blast radius is one renderer) to convergence. Do NOT run brainstorming/writing-plans (FIX-DIRECT, known mechanism). Persist any Codex/review responses to a gitignored `.copowers-findings.md`.

---

## §1 The mechanism (already diagnosed — do not re-investigate)
`render_market_weather_svg` calls `_render_candles_fig(..., volume=True)` and sets **no** ylabels of its own. So the right-side labels are mplfinance defaults: the price panel ylabel `"Price"` and the volume panel ylabel `"Volume  $10^{6}$"` (one string — the `$10^{6}$` is mpf's auto scale-factor in mathtext). In the 400×150 figure these rotated labels overlap the rotated date ticks.

`_render_candles_fig` resolves and returns `vol_ax` (its internal `_resolve_volume_ax` runs during the build), so clearing the ylabels **after** the call is safe and does not break volume-axis resolution.

## §2 The fix (scoped to `render_market_weather_svg` ONLY)
In `render_market_weather_svg`, capture the volume axis (currently discarded as `_vol_ax`) and clear both ylabels after `_render_candles_fig` returns:

```python
fig, price_ax, vol_ax = _render_candles_fig(
    df, ma_windows=(50, 200),
    figsize=_figsize_inches(_MARKET_WEATHER_SIZE_PX), volume=True,
)
# 17-D.5: declutter the cramped 400x150 mini-chart — drop the mpf-default
# axis labels that overlap the rotated date ticks. "Price" (price panel) and
# "Volume  $10^{6}$" (volume panel; the $10^{6}$ scale-factor is part of the
# one ylabel string) both go. Weather chart ONLY — ticker_detail /
# position_detail keep their explicit "Price (USD)"/"Volume" labels.
price_ax.set_ylabel("")
if vol_ax is not None:
    vol_ax.set_ylabel("")
```
(Keep the existing `trend:` badge + `_set_suptitle_no_math(...)` lines unchanged. Empty-string ylabels are ASCII-safe.)

**Do NOT:** touch `_render_candles_fig` (shared — would strip labels off the big ticker charts too); touch the explicit `set_ylabel` calls in the other two renderers; add any `$`/`^`/`_` text anywhere (mathtext gotcha).

## §3 Regression test (must hit the PRODUCTION path)
Add a test to `tests/web/test_charts_volume_yticks_stripped.py` (or a sibling) that calls the **production** `render_market_weather_svg(bars=..., trend_template_state="stage_2")` and asserts the weather chart's price ylabel is `""` and its volume-panel ylabel is `""` (no longer starts with "Volume"). Capture the figure by spying on `_svg_bytes_from_fig` (it receives the `fig` just before serialize+close) — e.g. monkeypatch it to stash `fig` then delegate to the real impl, and introspect `fig.axes` / the price axis ylabel.

**LOCK:** the test must exercise `render_market_weather_svg`, NOT rebuild via `_render_candles_fig` directly — a builder-rebuild asserts the wrong path and FALSE-PASSES (the builder still carries the mpf-default labels; the fix lives in the renderer). Add/keep an assertion that `render_ticker_detail_svg` still yields a `"Price (USD)"`/`"Volume"`-labelled chart (the existing `test_render_ticker_detail_preserves_volume_ylabel` covers ticker_detail's volume ylabel — confirm it stays green).

## §4 Binding conventions
- Branch `main`; conventional commit (`fix(web): 17-D.5 — declutter weather mini-chart axis labels`); **NO `Co-Authored-By`, NO `--no-verify`, NO amend.** Verify `git log -1 --format='%(trailers)'` empty.
- Fast suite `python -m pytest -m "not slow" -q` green on the merged head; `ruff check swing/` zero new violations.
- TDD: write the failing production-path test first (it fails because the labels are currently the mpf defaults), see it fail, apply the fix, see it pass.

## §5 Done criteria + GATE
- The two-line fix + the production-path regression test land; existing chart tests (incl. the volume-ytick-strip + ticker_detail-ylabel-preserve guards) stay green; ruff clean; trailers `[]`.
- `copowers:review` converged (responses persisted).
- **Operator-witnessed visual gate (BINDING):** the operator opens the web dashboard, regenerates/refreshes the Market-weather chart, and confirms "Price", "Volume", and "10^6" are gone and nothing else (candles, MA, trend badge, price ticks, volume bars, dates) regressed. This is the real confidence source — string/structural tests are necessary but not sufficient for rendered chart text.

## §6 Return report (your final chat message ONLY)
Report: the commit SHA; the test added (name + the spy mechanism + why it hits the production path); the `copowers:review` verdict + persisted-findings path; confirmation the scope-LOCK guards (ticker_detail/position_detail labels) stayed green; the exact steps for the operator to drive the visual gate. **Do NOT post to the mailbox or any director** — that is the orchestrator's post-QA action.
