# D79: the exit form must record the SELECTED broker order's fill, once -- round-0 dispatch brief

**Audience:** a fresh implementer cell with no prior conversation context.

**Mission.** The web exit form can record a fill that is not the selected broker order's. This arc closes both halves:
- **(F2)** there is no duplicate-order guard, so one Schwab order can be recorded twice;
- **(F1)** picking a non-default Schwab candidate leaves the DEFAULT candidate's date and price in the inputs, so an exit can carry another order's date and price.

**This dispatch is ROUND 0 ONLY:** measure, census the forks, and return. The orchestrator routes the forks to their rulers. A later dispatch writes the plan and executes it.

**Commissioned (operator, verbatim):**
- 2026-09-28: "exit double-record defect will be after the pause."
- 2026-09-28: "Concur with RDs recommendation.  Let's plan it to dothose two fixes post-pause."
- 2026-10-18: "draft the brief."

Register row **D79**, `docs/tool-director-context.md` section 4. Timing: after the pause, before the first live exit.

**Base:** `main` @ the commit adding this brief. **Worktree:** `.worktrees/d79-exit-identity`, branch `d79-exit-identity`.

**Cell:** `implementer-opus-high`, the writing-plans default. The notch stays at high and not xhigh: round 0 is measurement plus census, and the semantic rulings are the directors'.

**Scope for round 0:** READ-ONLY on `swing/`. Write only measurement scratch outside the repo and, if you want, `tmp_path` probe tests that you delete before return (keep a copy under the evidence directory). **Do NOT open or write the live DB except the `mode=ro` reads named below.**

## 0. Read first

- `docs/implementer-dispatch-recipe.md` in full (the protocol), and `CLAUDE.md`. These gotchas are load-bearing here:
  - the hidden-anchor family ("SERVER-STAMP", "Form-render hidden anchors ... MUST round-trip", "Hidden-anchor 4-tier rejection ladder", "`selected_X_audit_id` is an AUDIT TRAIL, not a DEDUPE KEY", "Price-precision parity", "POST-time recompute ... TOCTOU");
  - the two HTMX browser-only failure surfaces;
  - "A ROLLED-BACK ROWID IS REUSABLE";
  - "Python and SQLite ROUND DIFFERENTLY".
- `docs/harness-architecture.md`: the ENTRY-vs-LABEL test ("Could this row be written honestly with the disputed keys NULL plus a named warning?"). RD's semantics below are stated in its terms.
- **RD's binding identity semantics,** from `comms/orchestrator/read/20260928T163958Z-rd-rd-position-exit-double-record-zero-live.md`. Block-quoted here; read the whole file:

  > (a) EXACT REPLAY -- the selected candidate's schwab_order_id AND its signature hash equal an existing fill's: REFUSE THE ENTRY, typed, naming the recovery ("already recorded as fill N on trade T"). [...]
  > (b) SAME ORDER, DIFFERENT SIGNATURE -- the order id matches but the leg set / quantity / price differs (a partially-filled order that filled further after the first record): NOT a duplicate by proof. Do not refuse on the id alone -- that would block recording real shares. FLAG it on the form and require an explicit operator confirmation; never silently admit, never silently exclude. [...]
  > (c) ANONYMOUS (operator-typed, no order id): a value-tuple match (same trade, date, price, quantity) FLAGS only, at either grain. Never refuse, never exclude -- two identical manual exits are legal.
  > [...] VERIFY BEFORE RULING THE BRIEF: whether one order's legs can arrive as two candidates over time on the real mapper path -- (b) exists only if they can; if the candidate aggregation makes it impossible, (b) collapses into (a) and the brief states why.

- **F1's principle** (RD fyi `20260929T043131Z`, operator-concurred): "the values recorded against a selected Schwab order must BE that order's, or the POST flags the disagreement for confirmation -- a typed date/price contradicting the selected order is a provenance claim the server can check, never a silent override."
- **The witness record that produced F1 and F2:** `docs/superpowers/plans/2026-09-28-exit-rerender-anchor.ledger.md`, section "Operator-witnessed browser check". It covers fill 62: date 09-11 recorded against selected order 1007645251993, whose own date is 08-19, then the order re-offered with empty `possible_duplicates`.
- **The code** (re-ground every anchor; these were read on `47ca888d`):
  - `swing/trades/exit.py:record_exit` (`:148`): no order-id check.
  - `swing/trades/exit_auto_fill.py`:
    - the candidate dataclass and its `signature_hash` (`:319-390`);
    - `_build_candidate`;
    - `_undecidable_duplicates`;
    - `possible_duplicates` (`:344`, `:890`, `:975-1036`);
    - `resolve_exit_auto_fill` (`:521`).
  - `swing/integrations/schwab/trader.py:_compute_signature_hash` (`:195`).
  - `swing/web/view_models/trades.py:build_exit_form_vm` (`:994`): the existing-fill exclusion and the D31 anonymous-row comment block, ~`:1040-1110`.
  - `swing/web/routes/trades.py`, the exit POST:
    - the authoritative-selected install of `schwab_order_id` (~`:3141-3145`);
    - the RETENTION RULE that drops it unless the persisted values `_derives_from` the named candidate (~`:3225-3272`), RD 2026-08-11;
    - the d2-strict re-render helpers merged at `c6640faf` (`_exit_candidates_maps_equal`, `_rerender_exit_form_with_error`, ~`:2415-2560`).
  - `swing/trades/latched_origin.py:83`: `SCHWAB_ORDER_ID_ENVELOPE_KEY`, single-sourced.
  - The template `swing/web/templates/partials/trade_exit_form.html.j2`, which contains no script.
  - `swing/cli.py` `trade exit` (~`:1457`): no Schwab auto-fill path.

**Skill posture:** no copowers skills, and no Codex in round 0.

## 1. Round 0: what to measure (cite file:line on your base, and state the method behind every count)

1. **F2 has TWO mechanisms. Reproduce each on a `tmp_path` DB through the real route (TestClient):**
   - **F2-A, stale-form replay.** Render the form in two "tabs" and POST the same candidate unedited from both. Does the second POST record a second fill? Name the line where a guard is absent.
   - **F2-B, re-offer after the id is dropped.** A non-default pick with corrected values is followed by the retention rule dropping `schwab_order_id`. The envelope then carries only `selected_candidate_order_id`, which D31 makes anonymous. The next render then offers the same order with empty `possible_duplicates`. Reproduce it, and show the envelope at each step.
2. **F1.** Confirm the mechanism: choosing a radio does not change the date, price or shares inputs. Then measure what the POST does with a non-default pick plus submitted values that match the DEFAULT candidate:
   - which `fill_origin` results;
   - what the envelope asserts;
   - whether any server-side check compares the submitted values to the SELECTED candidate's map entry.
3. **RD's case (b): is it reachable?**
   - On the real mapper path, can ONE Schwab order's legs reach the form as TWO candidates, or as one candidate whose signature changes, over time? Example: a partial fill that fills further.
   - Read `_build_candidate`, the aggregation, and what the signature hash covers.
   - Answer REACHABLE or UNREACHABLE with the code reason. If unreachable, (b) collapses into (a), and any identity key may be the order id alone.
4. **RD's point 3 (a lead, unverified):**
   - Does a replayed partial exit leave the journal shorter than the broker in a way `untracked_broker_position` reconciliation would surface? Read the check and trace it against this shape.
   - Say DETECTED, NOT DETECTED or UNDETERMINED, with the reason. Do not lean on it either way.
5. **Live incidence,** via plain `sqlite3` `?mode=ro` on `C:\Users\rwsmy\swing-data\swing.db` (never `swing`'s `connect`):
   - (i) duplicate `json_extract(schwab_source_value_json,'$.schwab_order_id')` across fills (RD and CHARC measured 33 distinct on 33);
   - (ii) every fill whose envelope has `selected_candidate_order_id`: does its recorded date and price match that candidate's map entry? (RD measured 2, fills 22 and 59, both clean.)

   Report counts and the queries.
6. **The census of writers and readers:**
   - every path that writes an exit fill (web POST, CLI `trade exit`, reconciliation/auto-correct, imports);
   - every reader that treats `schwab_order_id` as identity (the VM exclusion, latch readers, reconciliation matchers).

   A guard placed in the route covers only the route. Say which writers a service-level guard would also cover, and whether that is wanted.

## 2. The forks: census each, with your recommendation. You do NOT rule them.

Name each fork's ruler as proposed below. The orchestrator routes the packet, one ruler per item.

- **K1, where the guard lives (CHARC):** in the route only, or in `record_exit`. The latter is the `swing/trades` carve-out the register names as a tripwire. Weigh the CLI path and the other writers from item 6.
- **K2, the identity key (RD):** order id alone, or (order id, signature), per your item-3 finding. Also: where the signature is persisted today (`selected_candidate_signature_hash`? the map?), and whether a fill recorded BEFORE that key existed can be matched at all.
- **K3, what a confirmed F1 contradiction records (RD), the crux of F1 x F2-B.**
  - When the operator CONFIRMS values that contradict the selected order, the retention rule drops the order link. That is RD's own 2026-08-11 rule: a top-level id asserts the persisted values derive from that order.
  - The fill then becomes anonymous, and the order is re-offered (F2-B).
  - Options to lay out, at least:
    - (i) keep the rule; a confirmed contradiction is anonymous, and F2-B is closed by another means (say what);
    - (ii) record the link on a different key than `schwab_order_id`, one that excludes but does not assert the values;
    - (iii) refuse a contradiction outright.
  - For each, say what the ENTRY-vs-LABEL test gives and what the latch and reconciliation readers then see.
- **K4, the F1 surface (orchestrator):**
  - a server-side check of the submitted values against the selected candidate's map entry (REQUIRED by RD's principle);
  - and/or a client-side refill of the inputs on radio change.

  The project has no JS test harness, and HTMX script behaviour is browser-only. State the cost of each.
- **K5, the confirmation flow (orchestrator):** for RD (b), (c) and F1. Find the existing soft-warn / `force` confirm pattern in the entry or exit POST and say whether to reuse it. Respect the `form_values` round-trip gotcha, and say how it composes with the d2-strict re-render merged at `c6640faf`.
- **K6, a schema backstop (CHARC):** a partial unique index on the extracted identity key. This is new schema and a tripwire. Recommend for or against, and give the key it would need given K2.
- **K7, anything else you find.** A fork discovered later stops the loop and returns here, so surface them now.

## 3. Tests you would write

For each, state:
- the case;
- the PRE-fix result and the POST-fix result (recipe section 2's arithmetic);
- which null implementation it kills.

At minimum cover: F2-A replay refused; F2-B re-offer closed (per K3); RD (b) flagged (if reachable); RD (c) anonymous flagged only; F1 contradiction flagged; F1 matching values pass silently; and the d2-strict restore still intact.

## 4. Binding conventions and evidence

- The recipe governs.
- Persist round-0 evidence (probe tests, query text and outputs) under `C:\Users\rwsmy\swing-data\review-transcripts\d79-exit-identity\round0\`.
- If you commit anything to the branch, the usual commit rules hold: conventional; no `Co-Authored-By`, `--no-verify` or amend; the final `-m` paragraph plain prose.
- After the ruling, a later dispatch writes the plan (Codex at `strong`) and executes it. Execution ends in an OPERATOR-WITNESSED browser check, binding for HTMX form work, which needs a working Schwab token and a scratch DB.

## 5. Return report (your final chat message, to the orchestrator only; NEVER post to any mailbox)

- Items 1-6 with citations and methods.
- K1-K7, each with options, your recommendation, and the proposed ruler.
- Section 3's test list with the arithmetic.
- Anything outside scope: FLAG it, do not fix it.

## 6. If you get stuck

STOP and return with what you measured if:
- a premise here does not match the code;
- a reproduction would need the live DB beyond the `mode=ro` reads above.

Return at ~300K depth with whatever is complete.
