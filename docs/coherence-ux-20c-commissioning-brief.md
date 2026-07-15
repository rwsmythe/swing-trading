# Commissioning Brief — 20-C: the coherence-UX cluster (D23 + D24)

**From:** CHARC. **To:** the Phase-20 orchestrator. **Arc:** 20-C ([`phase20-scope-charc.md`](phase20-scope-charc.md)). **Committed:** 2026-07-14. Parallel to 20-B (file-disjoint: web-only). **No deadline pressure.**
**§3 verdict:** NO tripwire — web routes/VMs/templates + tests only. NO schema (v31). The ONE PRINCIPLE (RD-endorsed): **a coherence finding routes the operator to the DATA FIX, never just the acknowledge** — the D25 saga began because both surfaces funneled to bail-water buttons.

## §0 References

- **Register D23:** the `untracked_broker_position` resolve page offers ONLY the one-shot acknowledge; the durable fix (`[reconciliation] out_of_framework_tickers` in `~/swing-data/user-config.toml` + `swing schwab resolve-out-of-framework`) is invisible — RKLB re-emitted 7× before CHARC found the config path (the SPCX precedent proved it works).
- **Register D24:** the cash-coherence badge renders UNLINKED when equity_delta-lit (`dashboard.py:54-68` returns None by design; `status_strip.html.j2:24` renders the span) — a call-to-action with no action. **+ the banked stored-vs-emit note:** `reconciliation_runs.equity_delta_dollars` stores the RAW OOF-INCLUSIVE gap; the badge/emit basis is OOF-NETTED — any diagnostic surface must display the netted basis and label the raw field correctly (RD: a future read must never consume the raw field un-netted).
- Surfaces: `swing/web/routes/reconcile.py` (the resolve pages) · `swing/web/view_models/dashboard.py` (badge + link) · `status_strip.html.j2` · the reconcile templates.
- The 19-F precedent for this exact surface family (HTMX gotchas: `hx-headers`, 204+HX-Redirect, target-route-exists, browser-only failure modes — ALL apply).

## §1 Requirements

### D23 — the untracked-position page surfaces the durable path
1. On the `untracked_broker_position` resolve page, ABOVE the one-shot acknowledge: a **"recurring holding?"** block explaining the durable disposition — declare the ticker out-of-framework — with the exact config stanza (ticker pre-filled), the exact `swing schwab resolve-out-of-framework` line, and when to choose it vs journaling vs one-shot acknowledging. **V1 = guidance, not a write-path** (a web write to `user-config.toml` is a NEW config-write surface — explicitly OUT of scope; note it as a V2 candidate if the plan is tempted).
2. The acknowledge flow itself is UNTOUCHED (it is correct for genuinely one-off findings).

### D24 — the equity_delta gets a destination + a diagnostic
3. A read-only **equity_delta diagnostic view** (route + template): the OOF-NETTED breakdown — ledger `current_equity` vs broker NLV vs Σ declared-OOF MV vs swing-NLV vs the netted delta — each line labeled with what it means, plus the route-to-the-data-fix guidance (unrecorded OOF buy → `journal oof-buy`; unrecorded deposit → the cash paths; unexplained → the forensic-decomposition playbook, citing the 2026-07-10 doc as the worked example). Display basis = NETTED; if the raw stored field is shown at all it is labeled raw/OOF-inclusive.
4. **The badge links in BOTH lit states:** the existing pending-mismatch link stays; the equity_delta-lit case now links to the diagnostic view (replacing the dead `<span>` — D24's literal complaint). The `_first_pending_cash_resolve_link_path` mirror-contract comment (`dashboard.py:56`) must be updated coherently — count and link must still agree.
5. NO new base-VM fields (the every-base-VM-or-500 gotcha — the badge fields already exist on DashboardVM only); no schema; read-only queries.

## §2 Tests + witness

- TestClient: the diagnostic route renders with seeded equity_delta state; the badge href discriminates the two lit states; the D23 block renders on the untracked page with the ticker interpolated; HX-Redirect targets exist where applicable.
- **BINDING operator GUI witness, BOTH states per the seeded-gate memory:** (a) SEEDED/lit — the badge links, the diagnostic shows the netted breakdown, the D23 block reads sensibly; (b) the CURRENT CLEAN default — badge absent, nothing regressed on the live dashboard. Browser, not TestClient (the HTMX family).

## §3 Gates + cells

RD fyi at return (the netted-basis display is his banked note — flag if the plan deviates from netted). review-strong + codex-auto-review; suite + ruff + merged-head no-false-green. Cells: writing-plans + executing `implementer-opus-high` (or the orchestrator's judged fold). The ORCHESTRATOR posts the return to `charc,rd` after its QA.
