# OhlcvBar Bad-Bar (Schwab regular-session) Fix Arc -- Brainstorming Dispatch Brief

**Audience:** Fresh Claude Code instance dispatched as the brainstorming implementer for the Schwab malformed-bar fix. No prior conversation context.

**Mission:** Produce a LOCKed, Codex-converged brainstorm spec for handling the ~2-4 malformed regular-session daily bars Schwab returns per pipeline run -- which currently fail the WHOLE Schwab window (the ticker degrades entirely to yfinance) -- so that Schwab stays the source for the good bars (or whatever handling the operator triages).

**Skill posture:** `copowers:brainstorming`. After the spec is written, run the **SINGLE Codex chain to convergence** (`NO_NEW_CRITICAL_MAJOR`; ~5-round cap suspended -- `feedback_codex_round_limit_suspended`). **Codex transport (MCP DEAD):** `wsl.exe bash -ilc 'export PATH="$HOME/.local/node22/bin:$PATH"; cat prompt.txt | codex exec -s read-only --skip-git-repo-check -'` (PATH prefix REQUIRED; codex-cli 0.135.0; pre-generate any diff on Windows; tell Codex NOT to run git). **Persist BOTH prompts AND responses** (incl. the final `NO_NEW_CRITICAL_MAJOR`) to `.copowers-findings.md`.

**Output:** spec at `docs/superpowers/specs/2026-06-07-schwab-bad-bar-handling-design.md`.

---

## §1 The confirmed problem (operator-witnessed + orchestrator-verified -- GROUND it, don't re-derive)
Schwab's `price_history` daily bars occasionally violate the `OhlcvBar` invariant -- `high < max(open,close)` OR `low > min(open,close)` -- in REGULAR-session bars (ext-hours confirmed OFF since the data-integrity arc; the "ext-hours causes these" hypothesis was FALSIFIED at that arc's live gate). The price-history mapper rounds o/h/l/c to 4dp then constructs `OhlcvBar`; an invariant violation now raises the typed `SchwabBarConsistencyError` (data-integrity arc A3/A4), which the ladder catches -> the ticker's ENTIRE window falls back to yfinance. So ONE malformed bar discards ALL of that ticker's good Schwab bars. Frequency ~2-4/run (PLTR + TWLO at Run 93; ~49 historical rows in `schwab_api_calls` with the invariant error_message). The END data is correct (yfinance is clean), but Schwab-as-primary is needlessly lost for those tickers + the #24/#26 yfinance-freshness/temporal-mutation concerns apply to the fallback.

**STEP-0 re-ground (discipline #2):** the mapper `OhlcvBar` construction + the `try/except SchwabSchemaParityError` placement (the data-integrity arc moved it -- re-grep `swing/integrations/schwab/mappers.py`); the `OhlcvBar.__post_init__` invariant (`swing/integrations/schwab/models.py` ~483/544); where the ladder catches `SchwabBarConsistencyError` -> yfinance (`marketdata_ladder.py` ~447); the per-bar vs per-window failure granularity.

## §2 CHARACTERIZE the bad bars FIRST (the brainstorm's first deliverable -- it shapes the fix)
Before choosing a handling, CHARACTERIZE the actual malformed bars (read-only): query the live `schwab_api_calls` rows with the invariant `error_message` (they carry the offending high/low/open/close values, e.g. `high (32.24) must be ...`); quantify HOW malformed (by how many cents/bps?), WHICH symbols/symbol-classes, and whether it looks like (a) a Schwab API quirk fixable at the REQUEST (a param/frequency/period that avoids it -- be SKEPTICAL given the ext-hours hypothesis already failed), (b) a precision/rounding artifact (the 4dp round interacts with Schwab's own rounding?), (c) a corporate-action-adjustment artifact, or (d) irreducibly bad source data. This determines whether the fix is request-side (avoid) or response-side (handle).

## §3 Candidate fix approaches (the CENTRAL OQ -- surface for operator triage; rec noted)
- **(a) Drop-just-the-bad-bar (RECOMMENDED default):** per-bar isolation in the mapper -- skip ONLY the invariant-violating bar(s), keep building the window from the good bars (mirrors the existing "bad-exemplar isolation" gotcha). Schwab stays the source for the good bars; the window has a 1-bar gap. **Must verify the gap is safe for ALL consumers** (chart render, SMA/MA computation, detect/observe windows, `OhlcvCoverageError`/sliced-count checks, the OhlcvBar-window contract) -- a missing interior bar may break a consumer that assumes contiguous sessions.
- **(b) Repair-clamp:** widen the bad bar to satisfy the invariant (`high = max(high,open,close)`, `low = min(low,open,close)`). Keeps the window contiguous but FABRICATES a data point -- needs a strong rationale + a clear marker/audit; weigh against V1 honesty norms.
- **(c) Request-side avoid:** if §2 finds a request param/frequency that avoids the malformed bars, fix at the source (cleanest if it exists -- but the ext-hours precedent says don't assume).
- **(d) Accept-the-fallback:** no code change; formalize "Schwab bad bar -> yfinance for that ticker is acceptable" + document. (Current behavior; the "fix" is a recorded decision.)

## §4 Surfaces the brainstorm MUST ground + decide
- The mapper's failure granularity (per-bar vs per-window) + how to make it per-bar without breaking the typed-error contract / the audit-row close discipline.
- Consumer tolerance of a 1-bar gap (if approach a): chart, SMA, detect Pass-1/Pass-2, observe `_bar_for_date`, the `resolve_ohlcv_window`/coverage checks, #28/#29 depth.
- A #27 audit of dropped/repaired bars (count + which dates) so the handling is never silent.
- Interaction with the just-shipped data-integrity arc (typed `SchwabBarConsistencyError` + mapper float-normalization) + the fetch-vs-write arc (the fetch now runs outside the fence) -- both intact.
- Whether the audit row should record `success` (window returned) vs `error` (a bar was dropped) -- the schwab_api_calls semantics.

## §5 Open questions for operator triage (surface)
- **OQ-A (central):** the fix approach (a/b/c/d per §3).
- **OQ-B:** if (a), the audit/visibility of dropped bars (a #27 warnings_json entry + a count? a per-ticker drop log?).
- **OQ-C:** scope -- is this a full code arc or does §2 reveal it's an "accept + document" decision (no executing phase)?

## §6 Locks / invariants (propagate)
NO schema expected (v24) -- confirm; the `OhlcvBar` invariant stays STRICT (do NOT relax `__post_init__` -- handle at the mapper, not by weakening the model); the data-integrity arc's typed error + float-normalization intact; the fetch-vs-write reorder intact; the audit single-tx + ladder fallback disciplines; #28/#29 depth; #27 no-silent-skip; F6 empty-result; ZERO `Co-Authored-By`; ASCII.

## §7 OUT OF SCOPE
The deadlock fix (CLOSED); the daily-management #16 (banked); B-1..B-8; any schema change (unless §2/§3 forces one -- then surface it as a CRITICAL OQ).

## §8 Dispatch metadata
- **Subagent:** `general-purpose`, foreground, harness-default model. **Worktree:** branch `bad-bar-fix-arc-brainstorm` from main HEAD (orchestrator states the SHA in the inline prompt). Brainstorm writes a SPEC (no code). You MAY (and SHOULD, for §2) read the live DB `mode=ro` to characterize the bad bars. SINGLE Codex chain to convergence. Leave the worktree INTACT.

## §9 Return report (mirror prior brainstorm returns)
Final HEAD + commits; spec path + section map; Codex convergent verdict (cite `.copowers-findings.md`); **the §2 bad-bar characterization** (the empirical finding -- quirk vs irreducible; request-side vs response-side) + the recommended approach + the OQs surfaced; the consumer-gap-safety analysis (if approach a); the schema verdict; locks preserved; ZERO `Co-Authored-By`; worktree intact; writing-plans readiness (or an "accept + document, no further phases" recommendation if §2/OQ-C lands there).

---

*End of brief. Brainstorm the Schwab malformed-bar handling: CHARACTERIZE the bad bars first (live schwab_api_calls error_messages -- quirk vs irreducible, request- vs response-side), then design the fix (rec: drop-just-the-bad-bar with per-bar mapper isolation + a #27 drop audit + a consumer-gap-safety proof, vs repair-clamp / request-avoid / accept-fallback -- the central OQ). Keep the OhlcvBar invariant STRICT; handle at the mapper. NO schema expected. OUTPUT: an executing-ready spec (or a documented accept-decision if that's where the evidence lands).*
