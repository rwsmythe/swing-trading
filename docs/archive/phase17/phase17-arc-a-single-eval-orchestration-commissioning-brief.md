# Phase 17 Arc 17-A — Single Evaluation Orchestration (commissioning brief)

**Authored:** 2026-06-12 by CHARC. **Register item:** D6 (top production drift hazard). **Roadmap:** [`docs/phase17-todo.md`](phase17-todo.md) §17-A.
**§3 tripwire (new module under `swing/`):** satisfied by construction — CHARC authors this brief and settles the module shape in §3 below. The plan routes BACK through CHARC only if executing discovers a schema need, a new dependency, or a departure from the §3 shape.
**Cycle shape:** writing-plans → executing (NO brainstorm — this brief is the locked design intent; the §4 divergence rulings are the operator's, gathered at the Phase-0 checkpoint). Codex adversarial review to convergence at each phase; every round's RESPONSE persisted to a gitignored on-disk file.

## 1. Mandate

Kill the comment-enforced parallel copy: `swing/cli.py:360` `eval_cmd` hand-mirrors `swing/pipeline/runner.py:1382` `_step_evaluate`'s orchestration so that "standalone `swing eval` and the pipeline persist classification identically" (the mirror comment at cli.py:~381). The criterion core (`evaluate_batch`) is already shared; the orchestration is not. Extract ONE shared orchestration path consumed by both entry points; the mirror comment dies because the mirror dies.

## 2. Grounding (verified on disk 2026-06-12 — the writing-plans engineer re-verifies at branch start)

The parallel stages (enumerated from both bodies): (1) ticker extraction + sector/industry passthrough map; (2) RS universe load + `universe_version_hash`; (3) SPY benchmark fetch (365-day lookback, `weeks*5` bar sufficiency, 0.0-fallback warnings); (4) per-ticker OHLCV fetch; (5) drift-safe context assembly (`run_now` captured ONCE; `action_session_for_run(run_now)`); (6) `evaluate_batch`; (7) synthesized `excluded`/`error` rows (`rs_method="unavailable"`); (8) persistence with sector/industry.

**KNOWN-SUSPECTED EXISTING DIVERGENCES (grounded 2026-06-12; the Phase-0 harness confirms or refutes):**
- `_step_evaluate` unions `list_open_trades` tickers into the universe (runner ~1420, the PriceCache-freshness gotcha) — `eval_cmd` does NOT (`list_open_trades` appears at cli.py:80/:976, neither inside `eval_cmd`).
- `_step_evaluate` carries the Arc-7 pin injection (screen ∪ pinned ∪ held) — `eval_cmd` predates it.

These may be intentional (pipeline-only concerns) or accidental drift — exactly what D6 predicts. NEITHER is resolved by the implementer.

## 3. Architecture (settled — the tripwire content)

- **New module: `swing/evaluation/orchestration.py`** — `evaluation/` already owns the criteria + date semantics; orchestration of an evaluation run is its natural third concern. NOT under `trades/` or `data/` (no phase-isolation carve-out anywhere in this arc — the orchestrator CONSUMES existing repos/services read-and-write through their existing public functions).
- **Shape:** one orchestration function (plan names it) taking explicit injection seams for the genuinely-different concerns: the universe-augmentation set (open-trade union / pin injection — supplied by the PIPELINE adapter per its existing semantics; the CLI adapter supplies whatever §4's rulings say), the output channel (click.echo vs pipeline log/warnings), and connection/fetcher provenance. Everything not injected is SHARED CODE.
- **Two thin adapters remain:** `eval_cmd` and `_step_evaluate` become parameter-assembly + call + result-handling. The mirror comment is DELETED, replaced by a one-line pointer to the shared module.
- **Untouched semantics (locks):** `_step_evaluate`'s lease/fence discipline and the #16 fetch-hoist locus; the Arc-7 pin/held union semantics in the pipeline path; `evaluate_batch` and everything below it; NO schema; NO new dependency; per-step timing emission (#25/Arc-1) unchanged.

## 4. Phase 0 — the golden-parity characterization harness (BINDING PRECONDITION)

Before ANY extraction: a harness that drives the SAME fixed inputs (a real finviz CSV fixture + a pinned OHLCV archive state) through BOTH current paths via their PRODUCTION derivation chains (no stub-only fixtures — the byte-parity-insufficient gotcha) and diffs the persisted candidate rows column-by-column.

- The harness lands FIRST, green against the CURRENT code, pinning today's behavior — including any divergences it finds, which it pins AS divergences (explicit expected-difference assertions, each tagged `DIVERGENCE-n`).
- **CHECKPOINT (hard stop):** the divergence list goes to the OPERATOR for canonical-behavior rulings before extraction begins. Each ruling becomes either (a) unified behavior with a migration of the assertion, or (b) an INTENTIONAL difference, kept as an injected-seam parameter and TESTED as intentional. No silent unification, no silent preservation.
- The harness stays green through the extraction and remains in the suite afterward as the permanent parity regression.

## 5. Tasks (the plan decomposes; this is the spine)

P0 harness → operator divergence rulings (checkpoint) → extract the shared orchestrator (module + pipeline adapter first, the CLI adapter second — the pipeline path is the gate-bearing one) → delete the mirror + comment → full suite + ruff on the final head. TDD per task; conventional commits; ZERO Co-Authored-By; plain-prose final `-m` paragraph.

## 6. Operator gate (binding)

One nightly pipeline run + one manual `swing eval` against the SAME session inputs → an operator-witnessed diff query showing identical persisted classification rows, modulo the §4-ruled intentional differences (each of which is demonstrated to match its ruling). Plus: the CLI UX surface unchanged (`swing eval` output text/exit codes — pin with a characterization test if the plan finds any risk).

## 7. Riders landing with this arc

- **R2 (P6/D9):** the frozen-clock convention line lands in `docs/orchestrator-context.md` with this first Phase 17 dispatch (orchestrator-lane content; NEW date-touching tests in this arc use the frozen-clock fixture).
- **R1 (P4/D7) does NOT land here** unless the plan unexpectedly touches pyproject — it shouldn't.

## 8. Return report

Via the mailbox (`--type return_report --to charc,operator`). **Explicitly itemize compliance with every §3 lock and the §4 checkpoint protocol** — the Phase 16 close audit's process lesson: GO-note/lock compliance is VERIFIED at QA, not assumed. Include: the divergence list + rulings, per-task commits, test counts read off the final head, Codex rounds + verdict, deviations with rationale.
