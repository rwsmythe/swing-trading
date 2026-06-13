# Phase 17 Arc 17-A — Task-C operator divergence rulings

**Recorded:** 2026-06-12, at the Phase-0 checkpoint (the executing-plans hard stop),
before any extraction begins. Operator-ruled; the implementer resolved none of them.
The Phase-0 golden-parity harness
([`tests/evaluation/test_orchestration_parity_golden.py`](../tests/evaluation/test_orchestration_parity_golden.py))
MEASURED each divergence through the production derivation chain (real CSV parse →
`read_or_fetch_archive` → `evaluate_batch`, network pinned offline) before routing.

## The six rulings

| Tag | Ruling | Seam | Disposition |
|---|---|---|---|
| **DIVERGENCE-1** (held union) | **intentional** | `augmentation.held_tickers` | pipeline supplies held tickers; CLI supplies empty `UniverseAugmentation()`. NOT a policy field. |
| **DIVERGENCE-2** (Arc-7 pin injection) | **intentional** | `augmentation.pinned_inject` + `output.note_pin_injection` | pipeline injects pins + emits the `pin_injection` warning; CLI supplies empty augmentation + no-op `note_pin_injection`. NOT a policy field. |
| **DIVERGENCE-EQUITY** (`current_equity` source) | **unify** | `current_equity` parameter | BOTH adapters now compute `sizing_equity(real_equity=current_equity(...), floor=...)` — the CLI now honors the capital-floor convention. NOT a policy field. No persisted effect (equity feeds position sizing only), so the parity assertion (shared columns identical) is unchanged. |
| **DIVERGENCE-ERROR-DEDUP** (error vs excluded dedup) | **unify** | `EvaluationBehaviorPolicy.dedup_error_rows` → **DELETED** | dedup becomes unconditional shared code. Fixes the latent CLI crash (a blocklisted-AND-fetch-failing ticker produced excluded+error rows → `UNIQUE(evaluation_run_id, ticker)` IntegrityError → whole eval rolled back). The CLI crash assertion migrates to a parity assertion (one excluded row, exit 0) in the CLI-adapter task (Task 2.2). |
| **DIVERGENCE-EXCLUDED-CLOSE** (held excluded-row close) | **unify** | `EvaluationBehaviorPolicy.preserve_held_close` → **DELETED** | preserve-fetched-close on excluded rows becomes unconditional shared code (`close = last fetched close if available else None`). Since D1 is intentional (CLI has no held rows), the CLI sees this only for a blocklisted ticker that fetches successfully — no existing assertion pins that to `None`, so the harness + suite stay green. |
| **DIVERGENCE-SPY-GUARD** (SPY fetch failure) | **intentional** | `EvaluationBehaviorPolicy.spy_failure_mode` → **KEPT** | the only surviving policy field. Pipeline `"raise"` (SPY fetch exception fails the step); CLI `"warn_and_zero"` (warn + `spy_return=0.0`, continue). 1:1 discriminating tests name the ruling. |

## Resulting `EvaluationBehaviorPolicy` (C2)

Two of three candidate policy fields ruled unify → DELETED. **One field survives:**

```python
@dataclass(frozen=True)
class EvaluationBehaviorPolicy:
    spy_failure_mode: str   # "raise" (pipeline) | "warn_and_zero" (CLI) -- C1: required, no default
```

`EvaluationBehaviorPolicy` survives (this is NOT the all-unify edge case, so the `behavior`
parameter stays). C1: `spy_failure_mode` is required (no default); both adapters construct
the policy explicitly (`EvaluationBehaviorPolicy(spy_failure_mode="raise")` /
`EvaluationBehaviorPolicy(spy_failure_mode="warn_and_zero")`), never `EvaluationBehaviorPolicy()`.

## Unified `data_asof` (faithfulness note)

The orchestrator preserves the CLI's three-branch `data_asof` (the pipeline's two-branch
form is a strict subset because pipeline `as_of_date` is always `None`):

```python
data_asof = (max(max_dates).date() if max_dates
             else as_of_date if as_of_date is not None
             else last_completed_session(run_now))
```
