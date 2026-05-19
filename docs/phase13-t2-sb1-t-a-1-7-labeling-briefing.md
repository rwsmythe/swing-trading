# Phase 13 T2.SB1 — T-A.1.7 Operator-Paired Labeling Session Briefing

**Audience:** Fresh paired Claude Code session dispatched to execute the T-A.1.7 operator-paired exemplar-bootstrap pass. No prior conversation context.

**Mission:** Drive the operator through the dev-time silver-tier labeling workflow + spot-check + promote-to-gold + commit-corpus flow, producing ≥25 gold-tier exemplars (≥5 per V1 pattern class × 5 classes) on the worktree branch. This session is NOT the executing-plans implementer; that session is paused awaiting the resume signal you produce.

**Constraint:** This is a paired, conversational session. Each candidate window is labeled INTERACTIVELY (operator picks the ticker + date range, you dispatch the subagent, operator reviews via web UI). Do NOT batch-process across multiple candidates without operator confirmation between each.

---

## §0 Status at session start

- **Worktree:** `.worktrees/phase13-t2-sb1-dev-time-labeling-infra/` (THIS directory; you are here).
- **Branch:** `phase13-t2-sb1-dev-time-labeling-infra` (HEAD `8cbb1a5` = T-A.1.6 SHIPPED post pre-pause cleanup).
- **Schema:** v20 (migrated via T-A.1.1).
- **Baseline:** 5013 fast tests passing / 6 skipped / ruff 0 errors / ZERO Co-Authored-By footer drift across all 10 worktree commits.
- **Subagent available:** `.claude/agents/pattern-labeler.md` (project-local; loaded automatically by this session since session-start postdates commit `9c7a5c1`).
- **CLI surface:** `swing patterns label-exemplars` subcommand registered (T-A.1.5).
- **Web surface:** `/patterns/exemplars` GET + `/patterns/exemplars/{id}/action` POST (T-A.1.6); start web app via `python -m swing.cli web`.

The implementer session paused at T-A.1.7 per spec §5.9 step 5 + plan §G.1 T-A.1.7 BINDING. This session is the operator-paired counterpart. The implementer awaits your operator's resume signal with an exemplar-count summary (N silver / M gold per class).

---

## §0.5 FIRST STEP — Step-by-step walkthrough (BEFORE any work)

**At session start, BEFORE running any CLI commands or invoking any subagent, do the following:**

1. Read this brief end-to-end.
2. Read `.claude/agents/pattern-labeler.md` to confirm subagent contract (inputs, outputs, forbidden behaviors).
3. Read `docs/superpowers/specs/2026-05-18-phase13-charts-patterns-autofill-usability-design.md` §5.9 (operator-paired exemplar bootstrap) + §5.2–§5.6 (per-pattern-class rule criteria).
4. Read `docs/superpowers/plans/2026-05-18-phase13-charts-patterns-autofill-usability-plan.md` §G.1 T-A.1.7 (the binding task contract).
5. Confirm CLI subcommand visibility: `python -m swing.cli patterns label-exemplars --help` (should show the 3-step operator-paired workflow).
6. **Emit a step-by-step walkthrough to the operator** covering:
   - The 3-step per-candidate workflow (CLI dispatch payload → subagent → CLI persist).
   - The pattern-class targets (≥5 gold per class × 5 classes = ≥25 gold minimum).
   - The promotion workflow via `/patterns/exemplars` web UI.
   - The commit-corpus step at the end.
   - The resume-signal protocol.
7. **Wait for the operator to confirm the walkthrough** ("OK", "proceed", or amendments). Do NOT invoke the subagent or start the web app before this confirmation.
8. Once confirmed, ask the operator for the FIRST candidate `(ticker, start_date, end_date, pattern_class)` tuple.

This walkthrough-first gate is BINDING — the operator expects to see the plan before any work happens.

---

## §1 Per-candidate workflow (3-step paired loop)

For each candidate window, execute these 3 steps interactively with the operator:

### Step A — Emit dispatch payload (CLI; no DB write)

```
python -m swing.cli patterns label-exemplars \
    --ticker <T> --start <YYYY-MM-DD> --end <YYYY-MM-DD> \
    --pattern-class <vcp|flat_base|cup_with_handle|high_tight_flag|double_bottom_w> \
    [--timeframe daily|weekly]
```

The CLI prints a JSON dispatch payload to stdout. The payload includes:

- `ticker` + `timeframe` + `start_date` + `end_date`
- `window_ohlcv_json` — compact OHLCV bars
- `pattern_class` — the SPECIFIC class being evaluated
- `rule_criteria` — per spec §5.2–§5.6 rule criteria for `pattern_class`
- `structural_evidence_schema` — dataclass shape the subagent must produce

Capture this payload (copy to clipboard or redirect to file: `... > payload.json`).

### Step B — Dispatch the pattern-labeler subagent (Agent tool)

Invoke the `pattern-labeler` subagent via the Agent tool with the dispatch payload as the prompt body. The subagent emits a SINGLE JSON object with EXACTLY 4 keys:

```json
{
  "evaluation": "confirmed" | "watch" | "rejected" | "relabel:<other_class>",
  "confidence": "high" | "medium" | "low",
  "structural_evidence_json": { ... },
  "geometric_evidence_narrative": "ASCII-only one-paragraph explanation"
}
```

Per the subagent's forbidden-behaviors LOCK:

- ASCII-only narrative (no `$`, `^`, `_`, `\`, em-dash, en-dash, fractions, arrows, non-ASCII glyphs).
- No free-form English outside the JSON envelope.
- Relabel target MUST be one of the 5 V1 classes; MUST differ from proposed class.
- Structural evidence must explain WHY (even for `rejected`).

Save the subagent's JSON response to a file (e.g., `silver_<i>.json` where `<i>` is a sequence number).

### Step C — Persist the silver row (CLI; writes to `pattern_exemplars`)

```
python -m swing.cli patterns label-exemplars \
    --ticker <T> --start <YYYY-MM-DD> --end <YYYY-MM-DD> \
    --pattern-class <C> \
    --silver-response-file silver_<i>.json
```

The CLI parses the response + persists one row to `pattern_exemplars` with `label_source='claude_silver'`. Confirm to the operator that the persist succeeded.

### Cadence

After each `(ticker, start, end, class)` cycle, summarize what was persisted + ask the operator for the next candidate OR signal that the per-class minimum is met.

---

## §2 Pattern-class targets (per spec §5.9 + plan §G.1 T-A.1.7)

| Pattern class | Description | Minimum gold |
|---|---|---|
| `vcp` | Volatility Contraction Pattern (Minervini) | ≥5 |
| `flat_base` | Flat-base consolidation | ≥5 |
| `cup_with_handle` | O'Neil cup-with-handle | ≥5 |
| `high_tight_flag` | High-tight flag | ≥5 |
| `double_bottom_w` | W-shaped double bottom | ≥5 |
| **Total minimum gold** |  | **≥25** |

Silver-tier candidates are expected to OVER-produce (~30-80 silvers total) so promotion to gold can be selective. Aim for a 1.5x–2x silver-to-gold ratio per class.

Operator picks candidate tickers based on:
- Known historical instances (memory of the operator's own trade history).
- Reference picks from Minervini / O'Neil / Qullamaggie material if needed.
- One-class-at-a-time blocks make spot-check easier (e.g., do all 8 VCP candidates → review → promote 5; then do flat_base; etc.).

---

## §3 Spot-check + promote/reject/relabel (web UI)

After persisting silver rows (and ideally after completing 1 pattern class block):

### Start the web app (in a second terminal OR background process)

```
python -m swing.cli web
```

Visit `http://127.0.0.1:8080/patterns/exemplars` in the operator's browser.

### Review each silver row

The web UI lists silver-tier exemplars with the structural evidence + narrative. For each:

| Action | When to use | UI button |
|---|---|---|
| **Promote to gold** | The subagent's label matches operator's visual judgment + structural evidence is sound | "Promote to gold" |
| **Relabel** | Wrong class — flip to a different V1 class | "Relabel" + select target class |
| **Reject** | Not a pattern at all (false-positive) | "Reject" |
| **Watch** | Pre-breakout shape; not tradeable yet | "Watch" |

Per the HTMX gotcha trinity at `swing/web/routes/patterns.py`, form submits emit `204 No Content` + `HX-Redirect: /patterns/exemplars` (browser re-navigates); the embedded form carries `hx-headers='{"HX-Request": "true"}'` for OriginGuard propagation.

### Promotion tracking

Promotion is per-row. The web UI updates `final_decision` + `final_pattern_class` columns. Operator MUST hit ≥5 gold per class.

---

## §4 (Optional) Cassette recording

If the operator wants to capture the labeling traffic for replay-mode testing:

```
python scripts/record_pattern_labeler_cassettes.py --audit-sentinels
```

V1 is scaffold-only — cassettes are populated manually from paired-session HTTP traffic. The `--audit-sentinels` flag runs the sentinel-leak audit guard (greps cassettes for un-redacted PII / secrets per the `tests/integrations/_cassette_sanitization` filter set; raises if any sentinel matches).

This is OPTIONAL per spec §5.9 step 6 — not required for T-A.1.7 closure.

---

## §5 Commit exemplar corpus + signal resume

### Commit corpus to worktree branch

Once the operator confirms ≥25 gold exemplars persisted + spot-checked:

```
git -C /c/Users/rwsmy/swing-trading/.worktrees/phase13-t2-sb1-dev-time-labeling-infra \
    add data/

git -C /c/Users/rwsmy/swing-trading/.worktrees/phase13-t2-sb1-dev-time-labeling-infra \
    commit -m "docs(phase13): T-A.1.7 operator-paired exemplar bootstrap corpus"
```

(Or commit pattern_exemplars rows via a DB-dump script if the corpus is DB-only; the implementer's pause message accepts either approach.)

**NO Co-Authored-By footer on the commit.** ~219+ project-cumulative ZERO drift streak. Per fresh forward-binding lesson #7 (Phase 12 Sub-sub-bundle C.B 2026-05-15): do NOT add `Co-Authored-By: Claude Opus 4.7 (1M context) <noreply@anthropic.com>` (or ANY Co-Authored-By footer attributing the AI assistant) to ANY commit message.

### Signal resume to orchestrator

Reply in the operator's orchestrator session (the session where the T-A.1.7 pause was relayed) with:

- **N silver per pattern class** (e.g., "vcp: 8 silver / 5 gold / 1 rejected / 2 relabel; flat_base: ...").
- **Total gold count** (must be ≥25).
- **Any T-A.1.7 deviations** (e.g., couldn't find 5 high_tight_flag candidates in the operator's history; promotion threshold adjusted; cassette recording skipped; etc.).
- **Commit SHA** of the corpus commit on the worktree branch.

The orchestrator will then resume the implementer session for T-A.1.8 closer + pre-Codex orchestrator-side review + Codex adversarial rounds + final return report.

---

## §6 Binding conventions

- **NO Co-Authored-By footer on ANY commit you make.** ~219+ cumulative ZERO drift streak; preserved across T2.SB1 + T3.SB1 + housekeeping commits.
- **ASCII-only in all subagent narratives + CLI output that flows through stdout.** Windows cp1252 stdout gotcha — non-ASCII glyphs (§, →, ↔, em-dash, fractions, arrows) crash with `UnicodeEncodeError` in PowerShell despite passing pytest's `capsys`.
- **Paired-session interactive cadence.** Do NOT batch-process multiple candidates without operator confirmation between each. Operator picks tickers + ranges.
- **DB writes are CLI-driven, not subagent-driven.** The subagent emits JSON; the CLI (`--silver-response-file`) is the ONLY path that writes to `pattern_exemplars`. Never let the subagent attempt to write to the DB directly.
- **Web review surface is the promotion path.** Do NOT promote-to-gold via CLI or DB manipulation; route every promotion through `/patterns/exemplars/{id}/action` POST.
- **Run commands from the worktree path.** `/c/Users/rwsmy/swing-trading/.worktrees/phase13-t2-sb1-dev-time-labeling-infra/` — the implementer's commits + the v20 schema + the new repo modules + the new CLI subcommand + the new web routes ALL live here, not on main.

---

## §7 Do NOT

- **Do NOT proceed past the walkthrough-confirmation gate without operator approval.**
- **Do NOT invoke the pattern-labeler subagent before Step A emits the dispatch payload.** The subagent is contract-bound to consume the payload's `window_ohlcv_json` + `rule_criteria` + `structural_evidence_schema`; freeform invocations break the contract.
- **Do NOT propose pattern classes outside the 5 V1 set** (vcp / flat_base / cup_with_handle / high_tight_flag / double_bottom_w). Sell-side patterns are BANKED to Phase 14 per L3.
- **Do NOT write to `pattern_exemplars` directly via SQL.** Always route through `swing patterns label-exemplars --silver-response-file`.
- **Do NOT proceed to T-A.1.8** — that is the implementer session's responsibility; T-A.1.7 closure signals the operator's orchestrator, who triggers the implementer's resume.
- **Do NOT touch T3.SB1's worktree** (`.worktrees/phase13-t3-sb1-entry-auto-fill/`). T3.SB1 is SHIPPED + awaiting merge per OQ-12 Option E.
- **Do NOT skip the corpus commit** at the end (or operator-equivalent persistence step). The implementer cannot resume cleanly if the exemplar corpus exists only in the operator's DB; the worktree branch must reflect the deliverable.
- **Do NOT modify the v20 migration / repo modules / subagent definition / CLI subcommand / web route.** This session is labeling-pass-only; production code is locked by the implementer's pre-pause commit chain.

---

## §8 Subagent invocation example

Once the dispatch payload is emitted by Step A:

```python
# Pseudocode for what the operator-paired session does:
# (Claude Code session has Agent tool available with subagent_type="pattern-labeler"
# automatically registered from .claude/agents/pattern-labeler.md.)

dispatch_payload = """<the JSON output from Step A's CLI invocation, verbatim>"""

# Invoke via Agent tool:
response = Agent(
    description="Label VCP candidate ABC 2024-01-01 to 2024-02-01",
    subagent_type="pattern-labeler",
    prompt=dispatch_payload,
)

# response is a single JSON object with the 4 keys; save to file:
with open("silver_1.json", "w") as f:
    f.write(response)

# Then Step C runs swing patterns label-exemplars ... --silver-response-file silver_1.json
```

Per the subagent definition: each invocation is INDEPENDENT — no state carries across `(window, pattern_class)` dispatches. The subagent is a pure function over the payload.

---

## §9 References

- **Subagent definition:** `.claude/agents/pattern-labeler.md`
- **CLI source:** `swing/cli_patterns.py` (registered in `swing/cli.py`)
- **Service layer:** `swing/patterns/labeling.py` (`fire_claude_silver_label` + `fire_codex_review_for_silver_row` + `should_fire_codex` selective-Codex policy)
- **Repo layer:** `swing/data/repos/pattern_exemplars.py` (caller-tx contract; NO `INSERT OR REPLACE`)
- **Web routes:** `swing/web/routes/patterns.py` + `swing/web/view_models/patterns_exemplars.py` + `swing/web/templates/patterns/exemplars.html.j2`
- **Spec:** `docs/superpowers/specs/2026-05-18-phase13-charts-patterns-autofill-usability-design.md` §5.9 + §5.2–§5.6
- **Plan:** `docs/superpowers/plans/2026-05-18-phase13-charts-patterns-autofill-usability-plan.md` §G.1 T-A.1.7
- **Original dispatch brief:** `docs/phase13-t2-sb1-executing-plans-dispatch-brief.md` (the implementer's contract; you inherit its conventions)
- **Interim report:** `docs/phase13-t2-sb1-interim-return-report.md` (state at T-A.1.1 ship)

---

*End of brief. T-A.1.7 operator-paired labeling session. Walkthrough-first gate BINDING. Per-candidate 3-step loop (CLI dispatch → subagent → CLI persist). ≥25 gold exemplars across 5 V1 pattern classes. Commit corpus to worktree branch. Signal resume to orchestrator with exemplar-count summary.*
