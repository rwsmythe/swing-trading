# SPCX carve-out executing — Codex review findings (review-strong, gpt-5.5, effort=high)

## Round 1
### Codex response (verbatim, final findings block)
```
swing/web/routes/reconcile.py:822:            disc.resolution != "pending_ambiguity_resolution"
swing/web/routes/reconcile.py:831:                    f"pending_ambiguity_resolution state."
swing/web/routes/reconcile.py:1193:                and post_race != "pending_ambiguity_resolution"
swing/web/view_models/dashboard.py:63:        "AND resolution='pending_ambiguity_resolution' "
swing/web/view_models/dashboard.py:78:        "AND resolution='pending_ambiguity_resolution'"
swing/web/view_models/reconcile.py:743:    ``resolution == 'pending_ambiguity_resolution'`` AND
swing/web/view_models/reconcile.py:759:    if disc.resolution != "pending_ambiguity_resolution":
swing/web/view_models/reconcile.py:761:            "discrepancy is not pending_ambiguity_resolution; got "
swing/web/view_models/reconcile.py:864:      longer in ``pending_ambiguity_resolution`` state. The 3 ``disc_*``
swing/web/view_models/reconcile.py:953:# does NOT route through the ``pending_ambiguity_resolution``-gated

codex
MAJOR, `swing/config.py` config-normalizer hunk: `_normalize_out_of_framework_tickers` accepts any iterable of strings, so a malformed TOML table/dict is treated as a valid ticker list by iterating its keys. Example: `[reconciliation.out_of_framework_tickers] SPCX = true` parses as `{"SPCX": true}` and normalizes to `("SPCX",)`.

Why it matters: user-config TOML is genuinely unconstrained, and the binding spec requires a CONFIG LIST with malformed values degrading, not silently becoming an active carve-out. This can suppress `untracked_broker_position` for a ticker the operator did not validly declare, violating C2/L3’s “never silent / no blanket ignore unknowns” intent.

Fix: make the normalizer accept only list/tuple-style sequences of strings, explicitly reject `dict`/tables and other iterables, and keep `apply_overrides` logging-and-ignoring rejected user-config values. Also remove the `tuple(...)` pre-wrap in `load()` so bare strings in tracked config are not split into characters before validation.

NEW_CRITICAL_MAJOR
tokens used
139,356
MAJOR, `swing/config.py` config-normalizer hunk: `_normalize_out_of_framework_tickers` accepts any iterable of strings, so a malformed TOML table/dict is treated as a valid ticker list by iterating its keys. Example: `[reconciliation.out_of_framework_tickers] SPCX = true` parses as `{"SPCX": true}` and normalizes to `("SPCX",)`.

Why it matters: user-config TOML is genuinely unconstrained, and the binding spec requires a CONFIG LIST with malformed values degrading, not silently becoming an active carve-out. This can suppress `untracked_broker_position` for a ticker the operator did not validly declare, violating C2/L3’s “never silent / no blanket ignore unknowns” intent.

Fix: make the normalizer accept only list/tuple-style sequences of strings, explicitly reject `dict`/tables and other iterables, and keep `apply_overrides` logging-and-ignoring rejected user-config values. Also remove the `tuple(...)` pre-wrap in `load()` so bare strings in tracked config are not split into characters before validation.

NEW_CRITICAL_MAJOR
```
(Full transcript header confirms: model gpt-5.5, reasoning effort: high, sandbox read-only.)

### Verdict: NEW_CRITICAL_MAJOR (1 MAJOR)

### Adjudication
- R1 MAJOR (config-normalizer accepts any iterable; TOML table iterates KEYS -> silent carve-out; tuple() pre-wrap in load() splits a bare string into chars): VALID, ACCEPTED. This is a genuinely-unconstrained user-config input (NOT schema-prevented) -> in-scope per the recipe's adjudication note (guard genuinely-unconstrained inputs). Fix: (1) normalizer accepts ONLY list/tuple sequences of strings, explicitly rejects dict/str/bytes/other iterables with TypeError; (2) remove the tuple() pre-wrap in load() so a bare-string tracked value is rejected, not char-split; (3) apply_overrides already logs-and-ignores on TypeError (unchanged).

## Round 2 (post R1 fix)
### Codex response (verbatim verdict block)
```
NO_NEW_CRITICAL_MAJOR
tokens used
97,143
No CRITICAL/MAJOR findings.

Round 2 fix looks complete: the normalizer now rejects non-list/tuple values, bare strings/bytes, dict/TOML-table values, sets, other iterables, and non-string elements; user-config override catches `TypeError` and falls back without activating a carve-out. The orphan-pass carve-out is scoped and surfaced via `cash_warnings` plus summary counter, and the existing-row resolver uses bound SQL placeholders, guards empty `IN`, avoids caller-held transactions, and delegates each row to `resolve_discrepancy` for the required audited state transition.

NO_NEW_CRITICAL_MAJOR
```
(Transcript header confirms: model gpt-5.5, reasoning effort: high.)

### Verdict: NO_NEW_CRITICAL_MAJOR -- CONVERGED (2 rounds).

### Adjudication
- R1 MAJOR confirmed fixed; Codex verified the strict normalizer rejects dict/TOML-table/set/str/bytes/other iterables + non-string elements, apply_overrides degrades on TypeError, and confirmed the orphan-pass carve-out scoping + cash_warnings/summary surfacing + the resolver's bound placeholders / empty-IN guard / no-caller-held-tx / resolve_discrepancy delegation. Zero new critical/major.
