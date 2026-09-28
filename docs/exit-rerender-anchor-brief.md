# Exit POST re-render: round-trip the submitted anchor (RD 1(iii) / 22-F AL-6) -- dispatch brief

**Audience:** a fresh implementer cell with no prior conversation context.
**Mission:** make the exit POST's refusal re-render carry the auto-fill anchor the operator SUBMITTED, the way the entry POST's re-render already does, instead of re-deriving it from a fresh Schwab fetch. The operator directed it on 2026-09-28 ("perform the followups").
**Base:** `main` @ `dcb39030`. **Worktree:** `.worktrees/exit-rerender-anchor`, branch `exit-rerender-anchor`.
**Cell:** `implementer-opus-high`. The reason the notch moved from the Sonnet executing default: this is a real-money form's audit anchor, there is a design question (WHAT round-trips) to settle in round 0, and a wrong answer here is confident and hard to see in TestClient.
**Scope:** `swing/web/routes/trades.py` and `swing/web/view_models/trades.py`, their templates if needed, and tests. **`swing/trades/` and `swing/data/` are read-only.** NO schema, NO migration, NO new dependency; any of those is a STOP.

## 0. Read first

- `docs/implementer-dispatch-recipe.md`, in full (the protocol), and `CLAUDE.md`. Its Web/HTMX/forms gotchas are load-bearing here, especially:
  - "POST-time recompute of 'latest-of-something' creates a GET/POST TOCTOU window";
  - "Form-render hidden anchors ... MUST round-trip";
  - "Hidden-anchor 4-tier rejection ladder";
  - "Price-precision parity";
  - "SERVER-STAMP, don't trust hidden inputs";
  - the two HTMX browser-only failure surfaces.
- **The precedent:** `swing/web/routes/trades.py:_rerender_entry_form_with_error` (~`:444`) and its `submitted_*` parameters (~`:469-548`). This is how the entry POST's refusal re-render replays the SUBMITTED anchor rather than refetching. The test pinning it is 22-F's A1-e (see below).
- **The defect site:** the exit POST handler's `except ValueError` branch (~`:3188-3202` on the base). It calls `build_exit_form_vm(trade_id=..., cfg=..., cache=..., executor=...)` fresh, which re-fetches Schwab orders and builds a NEW anchor. The template (`partials/trade_exit_form.html.j2`) gets only `vm` and `error_message`. Read `build_exit_form_vm` (`swing/web/view_models/trades.py` ~`:971`) end to end, and the exit template's hidden inputs, including the per-candidate `candidate_signature_hash_<i>` inputs (~`:73-130`).
- **The record:** RD's read, verbatim, from `comms/orchestrator/read/20260925T072925Z-rd-f-f1-ruling-a-degrade-both-rows-entry-tw.md`:

  > "(iii) Read, not ruled, outside F-F1: the exit POST re-render (routes/trades.py:3139) rebuilds the VM fresh and does not round-trip the submitted anchor at all, parity error or not. Pre-existing; it does not change whether the exit proceeds; the orchestrator's queue."

  In the 22-F plan it is declared as AL-6 (`docs/superpowers/plans/2026-09-25-phase22-arc-f-handler-escape-sweep.md`, section 10), and its test A1-e' deliberately asserts NOTHING about the anchor. The ENTRY twin A1-e pins "hidden anchor equals the submitted string byte-for-byte, kind 'populated'". Find both tests (grep `A1-e`) and read them.

**Skill posture:** no copowers skills; run Codex by hand per recipe §3 at the **`strong`** tier (production code).

## 1. Round 0: premise + fork census, NO Codex, then RETURN

Before writing any code, measure and return. Do NOT proceed past round 0 in this dispatch. The orchestrator rules the forks and re-dispatches you, or a fresh cell, to execute. Your round-0 return carries:

1. **Premise check.** Is the defect as stated on the base? Say which exit-POST refusal paths re-render the form:
   - the `record_exit` `ValueError` branch;
   - any earlier validation re-render in the handler (read the whole handler, from its form parse down to `record_exit`);
   - the anchor-rejection paths (`_reject_anchor`).
   For each, say whether it re-derives or round-trips the anchor. Cite file:line on the base.
2. **What the exit anchor IS.** Name every hidden input the exit form posts that the POST validates or persists:
   - `schwab_source_value_json`, `auto_fill_audit_at`, `fill_origin_at_form_render`;
   - the per-candidate signature hashes;
   - anything else.
   For each, say how the POST consumes it.
3. **The operator's typed values.** Does the exit refusal re-render preserve exit price, shares, date, reason and notes, or does the fresh VM reset them? Measure it.
4. **The design forks, each with your recommendation:**
   - (a) Round-trip exactly the set the entry precedent round-trips, or the full exit anchor set including candidate hashes.
   - (b) What `auto_fill_kind`, banner and advisory state the restored form shows (the entry precedent's Codex R2 Minor #1 restores `'populated'`).
   - (c) What happens when the submitted anchor is malformed at re-render time. Does it go through the 4-tier rejection ladder, or is it restored verbatim?
   - (d) Whether the re-render may still fetch Schwab at all, for example for the candidate list, or must not.
   - (e) Whether the typed values round-trip, if they currently do not. That may be a separate defect; say so.
5. **Tests you will write,** with the pre-fix and post-fix arithmetic for each, per recipe §2.

## 2. After the ruling (a later dispatch; stated here so round 0 plans for it)

- The execution is TDD, RED-first, one commit per logical change.
- The full fast suite runs green before and after Codex.
- Codex runs at `strong` to convergence, with every round persisted to `C:\Users\rwsmy\swing-data\review-transcripts\exit-rerender-anchor\r<N>\`.
- **Then an OPERATOR-WITNESSED browser check is BINDING** (CLAUDE.md: HTMX form work). The orchestrator runs it step by step with the operator, against the worktree's code (`PYTHONPATH=. python -m swing.cli web`), not the editable install.

## 3. Binding conventions

The recipe governs:
- conventional commits;
- no `Co-Authored-By`, no `--no-verify`, no amend;
- the final `-m` paragraph plain prose;
- bare `git` from the worktree cwd;
- ruff `swing/` clean;
- ASCII in any user-facing string.

**Do not open or write the live DB.**

## 4. Return report (round 0; your final chat message, to the orchestrator only; never post to any mailbox)

- Items 1-5 above, with file:line citations on base `dcb39030` and the method behind every count.
- If round 0 finds the premise FALSE (the anchor already round-trips), say so plainly with the evidence. That closes the item.
- Anything outside scope: FLAG it, do not fix it.

## 5. If you get stuck

- STOP and return with what you measured if:
  - the fix would need `swing/trades/` or `swing/data/`;
  - the premise does not match the code.
