# Dispatch brief — the canonical-entry-limit single-source rider

**Audience:** a fresh implementer sub-agent with **no prior conversation context**.
**From:** the Phase-21 orchestrator. **Authorized:** operator (in-session 2026-08-03, relayed via CHARC's dispatch `20260803T094522Z`); RD's merge-QA ruling `20260803T110020Z` attaches the timing condition.
**Base:** `main` (currently `e56856f3`). **Worktree:** `.worktrees/entry-limit-single-source`.
**Schema:** none. **§3 tripwire:** not crossed (no new module/dependency/process/carve-out; `swing/web` + `swing/config.py` only).
**Review tier:** `strong` (production code — see §6). Expected duration: short.

---

## §0 Read first

1. `docs/implementer-dispatch-recipe.md` — **in full**; it is your protocol. Note the tier names were repointed to `strong`/`fast` on 2026-08-03 (§2A + the tier block).
2. `CLAUDE.md` — the project gotchas. Gotcha **#30** (a run/batch stamp is not per-row provenance) and **#31** (a seam comment promising future inheritance is unenforceable) are the family this rider sits in.
3. This brief.

Re-ground every file:line below against live code before editing — line numbers drift.

## §1 Why this exists — the defect, witnessed live

At the 2026-08-03 operator witness of arc 21-B, the panel showed **`Zone cap 37.36`** for AMN while the framework's own prepared order was **`limit 37.35`**. Both numbers were on the same card. The operator's real resting order at the broker was at **37.36** — he placed the number the panel displayed.

The mechanism, verified:

| | true zone cap | rendered `:.2f` | `mandate_limit_price` | operator's live order |
|---|---|---|---|---|
| AMN | 37.3581 | **37.36** ↑ | 37.35 | **37.36** |
| VSTS | 17.4070 | **17.41** ↑ | 17.40 | **17.41** |
| FTRE | 18.8902 | 18.89 ↓ | 18.89 | — |

`swing/latches/constants.py:mandate_limit_price` **floors** to whole cents, on RD's 2026-07-30 ruling that *"a cap that can drift up is not a cap."* Every **display** path instead uses plain `:.2f` / `_fmt_price`, which rounds **half-up** and can therefore print a number **above** the cap. FTRE is the control: its cap rounds down, so display and mandate agree and no divergence appears.

**Why it matters beyond cosmetics:** 21-B's parity ledger records `framework_limit_price` against `actual_limit_price`. A divergence caused by the panel's own display is recorded as **operator deviation**. RD ruled it not merge-blocking (the defect is in 21-A's shipped display, and 21-B is the *detector*), but attached a condition — see §5.

## §2 Scope — and a PREMISE CORRECTION you must know about

CHARC's dispatch characterised this as *"a one-line default change on a display surface."* **The code does not support that characterisation**, and the corrected scope is below. This correction is the orchestrator's, made at brief-authoring time; it is not a licence to widen scope further.

### §2.1 The cap-display fix — SEVEN sites, not one

Every site below renders the cap value with round-half-up and can overstate it:

- `swing/web/view_models/latches.py:650` — `zone_cap=_fmt_price(latch.zone_cap)` (feeds `templates/latches.html.j2:37`, the card's `Zone cap` field — **the one the operator read**)
- `swing/web/view_models/latches.py:1926, 2115, 2123, 2128, 2174` — alarm / prompt strings using `{lat.zone_cap:.2f}` (**2115 is the `ORDER PRICE MISMATCH` line the operator also saw**)
- `swing/latches/orders.py:708, 716` — `LATCH_ARMED_NO_RESTING_ORDER` alarm strings using `{latch.zone_cap:.2f}`

**The fix:** every one of these renders the cap through the **same single source the mandate uses** — `mandate_limit_price` — so the surface can never display a price the framework would not order. Do **not** hand-roll a second flooring expression at any site; import the one function. `swing/web/view_models/latches.py:411` is **out of scope**: it renders the *multiplier* (`x 1.03`), not a cap value.

**Note `_PRICE_DP` is currently defined three times** (`view_models/latches.py:63`, `latches/orders.py:40`, `latches/service.py:41`). CHARC has this banked as a close-time item. **Do not refactor it here** — flag it in your return report if your change touches its neighbourhood.

### §2.2 The `chase_factor` alignment — a config field, not a constant

The operator **retired** his 2026-04-25 pure-trigger discipline (*"don't chase >1% above pivot"*) on 2026-08-03, knowing it is a loosening. `chase_factor` aligns to the zone cap.

But `chase_factor` is **not** a code-only default. It is a full config field with an operator-facing edit surface:

- `swing/config.py:529` — `chase_factor: float = 0.01` (+ the provenance comment at `:523`)
- `swing/config_overrides.py:27, 88-90` — operator override path
- `swing/config_validation.py:45` — validated
- `swing/web/routes/config.py:39` — exposed as an operational tunable in the web config page
- `swing/web/view_models/dashboard.py:836, 838` — `buy_limit = pivot * (1 + chase_factor)` + the echo
- `swing/web/templates/partials/hypothesis_recommendations_expanded.html.j2:34` — renders `(pivot × N%)`

**What to implement (Option A, deliberately conservative):**

1. The dashboard's `buy_limit` derives from the **same single source** as the latch cap — i.e. it produces the value `mandate_limit_price` would produce for that pivot — rather than from a second hard-coded `0.03`. CHARC: *"a second constant that happens to equal the first is the item-6 drift class."* If a literal proves unavoidable, a comment must name the single source it mirrors **and** a test must pin the equality.
2. The default at `config.py:529` moves off `0.01` accordingly.
3. **The provenance comment at `config.py:523` is REPLACED, not annotated** — supersession by replacement. It documents the 2026-07-23 latch posture and the 2026-08-03 retirement. The retired rule's record lives in the commit message, not as a struck-through comment.
4. The config field, its validation, its override path and its web editor **stay**. Removing an operator-facing knob is out of scope for a rider.

**The open question you must NOT decide** (flag it in the return report): keeping `chase_factor` editable leaves a path for the operator to re-diverge the two surfaces. RD's position is that his tighter preference *"should NOT be re-encoded as a second framework rule"* but recorded as a ledger delta — which argues for removing the knob entirely. That is a directors' call, not a rider's.

## §3 Tests — make them discriminating

Per the standing discipline, **compute each assertion's value under both the pre-fix and post-fix paths and confirm the test distinguishes them.** A test that passes under both is worse than no test.

- The cap-display fix needs a case whose third decimal is **≥ 5** (AMN's 37.3581 → pre-fix `37.36`, post-fix `37.35`). A cap that rounds *down* (FTRE's 18.8902 → `18.89` either way) is the **control** and must also be pinned, or the test cannot tell flooring from rounding.
- Pin **display == what the framework would order** at each of the seven sites, rather than pinning a literal string — the literal is what drifts.
- The `chase_factor` alignment needs a test pinning **equality with the latch single source**, so a future edit to one cannot silently diverge the other. This is the whole point of the change.
- Use the frozen-clock fixture for any new date-touching test (binding convention).

## §4 Binding conventions

Conventional commits; **zero `Co-Authored-By`**; no `--no-verify`; no amend. Keep the final `-m` paragraph plain prose — a paragraph opening `Word:` is parsed as a git trailer and pollutes the streak audit (this exact defect cost the 21-B merge an amend). TDD, one red→green→commit per logical change. `ruff check swing/` clean. **Run the FULL fast suite to green BEFORE the Codex review, and again after it converges** (§2/§4 of the recipe). ASCII in anything reaching stdout.

## §5 The timing condition (RD, binding)

**This must land before the next live latch fire can write a real parity row.** The live ledger is currently **empty**, so the first real row is genuinely the one at stake; A+ fires run roughly weekly. If a fire beats the rider, a display-caused delta is mechanically identifiable (exactly +1 cent, on a cap whose third decimal ≥ 5, order at the displayed value) and gets annotated at read time rather than scored against the operator — but that is a fallback, not the plan.

## §6 Adversarial review

Production code → tier **`strong`**, run to `NO_NEW_CRITICAL_MAJOR`, plus **codex-auto-review** as the complementary second eye (recipe §3). **Assert the per-round banner every round** — model `gpt-5.6-sol`, `model_reasoning_effort: high`, and `grep ERROR` the output. A round failing any of the three **did not happen and must not count**. Record the asserted model + effort per round in `.copowers-findings.md`. Persist every round's **response**, not just the prompt.

**Watch items to pass the reviewer:** did the fix reach *all seven* render sites, or only the two the operator happened to see? Is there any remaining path by which a displayed price can exceed the cap? Does the `chase_factor` alignment introduce a second constant rather than a shared source?

## §7 Return report

To the ORCHESTRATOR as your final chat message. **Do not post to any role mailbox.** Include: commits landed; the seven sites with before/after values; the `chase_factor` approach taken and whether a literal was unavoidable; both full-suite results (before-review and post-convergence); the Codex round count with the per-round banner assertions; the trailer audit (`git log <base>..HEAD --format='%H%n%(trailers)'` — every commit empty); and your flag on the §2.2 open question. If a trailer slipped in, **stop and flag it** — the orchestrator resolves it at merge.

## §8 If you get stuck

Stop and report to the orchestrator rather than working around. In particular: if the `chase_factor` single-sourcing turns out to require touching the config validation or the web config route in a way this brief did not anticipate, **stop and flag it** — that is a scope question, and this brief has already had its premise corrected once.
