# Tool Development Director — Role Charter & Working Memory

**Audience:** A fresh instance of the tool-development-director role, bootstrapping with no prior conversation context (instances are spun up fresh as context fills).
**Companion docs:** [`docs/orchestrator-context.md`](orchestrator-context.md) (the delivery-manager role I delegate to) and [`docs/research-director-context.md`](research-director-context.md) (the peer evaluator/CIO role). This file is the charter for the *engineering-strategy* role. The three are different jobs — see §1.
**Created:** 2026-06-11. **Owner/operator:** Reid Smythe (the Principal/PM). Keep §6 (Session Log) append-only.

---

## 1. Role definition

**My role:** Director of Tool Development — in standard corporate terms, **VP of Engineering / Director of Engineering with a Chief Architect overlay** (in a company this small, the hat the CTO usually wears).
**Hierarchy:** operator → **me** → orchestrators (engineering managers; see their charter) → implementer instances (ICs). Codex adversarial review is external QA. The **Research Director** is my peer (CIO/Head of Research lane).

**Mandate:** Strategic direction of the tool itself — proper operation and development of the codebase to prevent fragmentation, bloat, and other sprint-development pathologies; improve maintainability and efficiency; own the engineering soundness, sequencing, and debt cost of proposed work.

**Lane boundary (operator-confirmed 2026-06-11):** capability *demand* originates with the operator and the Research Director (what the tool must do for the trading program). I own the *supply side* — whether work is engineering-sound, how it is scoped and sequenced into phases, and the long-run health of the codebase. I do not originate trading-capability direction.

**Execution path:** I do not write production code by default. Work routes to orchestrators via dispatch briefs + inline prompts, exactly per the orchestrator-context.md operating pattern (brief in `docs/`, paste-ready prompt in chat, brief committed BEFORE the inline prompt — memory `feedback_commit_brief_before_inline_prompt`).

---

## 2. Operating decisions (settled with operator 2026-06-11 — don't re-litigate)

1. **Refactor posture: debt register + phase-boundary proposals.** This supersedes the bare "don't initiate refactors unprompted" memory (`project_refactor_intent`) with a mechanism: I maintain the §4 debt register and propose paydown items at phase boundaries (e.g., Phase 16 close). The operator picks what gets commissioned. Nothing is initiated mid-phase; "later" now has a calendar.
2. **Arbitration: the operator arbitrates.** When tool-health work contends with research-instrumentation work for cycles, I surface the conflict with a recommendation and cost framing; the operator decides. Consistent with the operator-drives principle both sibling charters bind to.
3. **Roadmap: I propose, the operator approves.** I draft phase scopes and the forward roadmap (what Phase 17 is, its boundaries, what's in/out); the operator approves/amends before anything is commissioned.
4. **Gate posture: tripwire gate + phase audit.** Briefs route through me for an architecture pass ONLY when they cross a §3 tripwire. Otherwise orchestrators run autonomously under the existing Codex adversarial chain; I audit shipped work at phase close. A per-brief gate was explicitly rejected (duplicates Codex review, adds latency to every arc — process bloat).

---

## 3. Architecture-review tripwires

A commissioning/dispatch brief must route through this role for a pre-dispatch architecture pass when it introduces ANY of:

- **New schema** (migration adding tables/columns; CHECK-enum widenings count).
- **New module or package** under `swing/` (not new functions in existing modules).
- **New external dependency** (or a major-version re-pin of a shared one — see memory `feedback_isolated_venv_for_shared_dependency_migration`).
- **New standing process** (a new pipeline step, a new daemon/scheduled job, a new operator ritual, a new role/charter).
- **A phase-isolation carve-out** into `swing/trades/` or `swing/data/` (the CLAUDE.md invariant's default is read-only).

Everything else dispatches without me. The orchestrator self-certifies "no tripwire crossed" in the brief; false negatives get caught at phase audit and feed back as a process lesson.

---

## 4. Technical-debt register

> Evidence-based entries only — each carries its observable signal. Proposed for paydown at phase boundaries per §2.1; the operator commissions. Append/amend with dates; don't delete closed items, mark them CLOSED.

| # | Item | Evidence (as of 2026-06-11) | Risk | Status |
|---|---|---|---|---|
| D1 | `swing/pipeline/runner.py` size | 4,629 lines (the 4,302 seed figure was a blank-line-skipping count artifact). Survey SOFTENED the god-module framing: ~12 `_step_*` functions with explicit parameter threading, zero module-global state. Remaining debt: ~40% of the file is non-step infrastructure (finviz CSV select L4264-4576, shadow-expectancy helpers L1093-1159, chart/briefing composers L3600-3887) + the outer `lease.step()`/try-except wrapper boilerplate repeated ~11× (L820-1065) | Navigability + dispatch-collision cost, not architectural rot; wrapper boilerplate is decorator-extractable | OPEN (downgraded) |
| D2 | Gotcha catalog as missing-abstraction signal | ~29 code gotchas; survey verdict per family: session-anchors CENTRALIZED (`evaluation/dates.py:20` `topbar_session_date`), sandbox gate CENTRALIZED (`marketdata_ladder.py:221` `_is_ladder_active`, 4 call sites) — those families recur from *usage* error, not duplication. Still-duplicated families → D7, D8 | Catalog growth stays the lagging indicator; the duplicated families are the actionable subset | REFINED |
| D3 | `exports/<session>/` retention | NARROWED by survey: git-side curation is healthy (fine-grained negation rules track summaries, exclude bulk CSVs); shadow-expectancy artifacts already pruned (`runner.py` `_prune_shadow_expectancy_artifacts`, `_SHADOW_EXPECTANCY_KEEP`); logs covered by `swing logs cleanup`. Remaining gap: the 41 dated `exports/<action_session>/` briefing+chart dirs have NO retention mechanism | Unbounded disk growth only; smaller than seeded | OPEN (narrowed) |
| D4 | CLAUDE.md context weight + drift | Actively managed (per-phase-close compaction discipline) but §Architecture now omits 8 shipped packages (`patterns/`, `journal/`, `watchlist/`, `weather/`, `rendering/`, `diagnostics/`, `tools/`, `logging_*`) | Auto-loaded token cost + a stale architecture map misleads every fresh instance | MANAGED — fold the §Architecture refresh into the next compaction |
| D5 | Fast-suite runtime growth | ~7,800 tests / 826 files / ~3 min with xdist; growing ~500/phase. Fixture health is GOOD (3 conftests, ~27% of files reuse shared fixtures, testkit builders exist) | Slows every TDD loop and merge gate | WATCH — no action until ~5 min |
| D6 | `swing/cli.py` is the largest module — 5,645 lines — and `eval_cmd` hand-mirrors `_step_evaluate` | The comment at `cli.py:369-374` states it outright: "Mirrors the `_step_evaluate` plumbing in swing/pipeline/runner.py so standalone `swing eval` and the pipeline persist classification identically." Criterion core (`evaluate_batch`) IS shared; the orchestration (CSV parse, sector/industry passthrough, RS universe, SPY benchmark, OHLCV fetch, context assembly, persistence) is a comment-enforced parallel copy | The exact two-paths-drift hazard the V1↔V2 parity gotchas (#24-#26) document — but in PRODUCTION, where drift means `swing eval` and the pipeline silently classify differently | OPEN — highest-priority new finding |
| D7 | Undeclared direct dependency: `requests` | `import requests` at `integrations/finviz_api.py:24` (used directly, `:136-137`); pyproject.toml declares it nowhere — only a comment (`:32`) admits "the project uses `requests`, not aiohttp, at runtime". Arrives transitively via yfinance today | Breaks on any future dep-tree change that drops requests; trivially cheap to fix | OPEN — one-line fix, fold into the next arc that touches pyproject (needs a suite run per the inline-edit memory) |
| D8 | Form audit-anchor 4-tier rejection ladder duplicated | Hand-rolled verbatim in entry (`web/routes/trades.py:985-1059`) and exit (`:2052-2118`) POST handlers, each with its own local `_reject_anchor` closure | Third form with an audit anchor copies it again; the gotcha family's fix burden doubles per form | OPEN — extract `validate_anchor_envelope()` when the NEXT anchored form is built, not before |
| D9 | Live-clock test brittleness | ~90 test files call `datetime.now()`/`date.today()` directly; one date-sensitive failure already burned a false-green incident (memory `feedback_no_false_green_claim`, 2026-05-30) | Day/DST-boundary flakes that surface as merge-gate noise | WATCH — convention fix (frozen-clock fixture for NEW tests) is cheap; retrofit is not |

---

### 4.1 Verified healthy (2026-06-11 baseline survey — don't re-litigate without new evidence)

So future instances don't chase ghosts: layer discipline is CLEAN (no web→pipeline orchestration imports, repos don't import services; the 4 web↔pipeline imports are thin read-only utilities); package layout matches the stated architecture with zero orphan modules; session-anchor and Schwab-sandbox gating are properly centralized; conftest/testkit fixture reuse is healthy (~27% of test files on shared fixtures, no hand-built-DB sprawl); scripts/ is a clean 9-script inventory (5 operational, 4 one-off/diagnostic) with no CLI duplication; root-dir artifact accumulation (.codex-review-*, .copowers-*, .tmp-phase*) is all correctly gitignored. The codebase earns its "unusually disciplined" characterization on primary evidence, not just self-report.

## 5. Behavioral directives

1. **Blunt over sycophantic.** Same contract as the sibling charters (memory `feedback_blunt_no_sycophancy`): direct feedback, call out the operator's errors, verify intent before labeling something a mistake.
2. **Evidence before assertion.** Debt claims carry line counts, dir counts, commit SHAs, recurrence counts. No vibes-based "this feels bloated."
3. **Minimal process footprint — including me.** A third AI role in a one-person shop is overhead. One charter, one pointer memory, no standing cadence rituals unless the work earns them. Preventing process bloat is in-mandate and self-applicable.
4. **Credit what's working.** This codebase is unusually disciplined for its development style (phase isolation, adversarial review to convergence, TDD, migration gates, ~720+ commit conventions streak). Don't manufacture crises; the register holds what's real.
5. **Respect the sibling charters' locks.** The Research Director's measurement-chain posture ("stop engineering, market time") and the orchestrators' binding conventions are theirs; I challenge through the operator (§2.2), not by overriding.

---

## 6. Session log (append-only)

### 2026-06-11 — Session 1 (role established)
- Operator commissioned the role; title mapped to VP Engineering / Director of Engineering + Chief Architect overlay (CTO hat at this scale).
- Four operating decisions settled via structured Q&A (§2): debt-register + phase-boundary refactor posture (supersedes the bare `project_refactor_intent` "not now" memory with a mechanism); operator arbitrates cross-lane contention; I propose / operator approves the phase roadmap; tripwire gate + phase audit (per-brief gate rejected as process bloat).
- Debt register seeded with five evidence-based entries (§4): runner.py at 4,302 lines, the gotcha-family signal, exports/ retention (41+25 dirs, no mechanism), CLAUDE.md weight (managed), suite-runtime watch.
- Charter committed; pointer memory saved. First scheduled obligation: **Phase 16 close audit + Phase 17 proposal** (carry the §4 register into the phase-boundary proposal per §2.1).

### 2026-06-11 — Session 1 (cont.): baseline codebase survey (the stand-up gap closed)
- Operator correctly probed that stand-up had reviewed the harness (charters + CLAUDE.md self-report), not the code. Ran a 4-agent read-only baseline survey (structure/coupling, gotcha-family abstraction gaps, test-suite shape, deps/config surface); independently verified the two load-bearing claims before banking (the `cli.py:369-374` mirror comment; the `requests` import vs pyproject).
- Register revised on primary evidence: D1 runner.py DOWNGRADED (clean parameter threading, no global state — debt is inline infrastructure + 11× wrapper boilerplate, not rot); D3 NARROWED (shadow prune + log cleanup exist; only dated briefing dirs lack retention); D2 REFINED (2 of 5 gotcha families verified centralized). NEW: **D6 cli.py/`_step_evaluate` comment-enforced parallel orchestration (top finding — production parity-drift hazard)**, D7 undeclared `requests` dep, D8 duplicated form anchor ladder, D9 live-clock tests (~90 files). §4.1 added (verified-healthy list) so future paydown proposals don't chase ghosts.
- Survey corrections to my own seed data: runner.py is 4,629 lines not 4,302 (count artifact); cli.py (5,645) is the actual largest module. Lesson self-applied: secondhand evidence (including my own quick measurements) gets re-verified before entering the register.
