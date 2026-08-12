# D31-exit — the final pass

**Audience:** a fresh Claude Code implementer, no prior conversation context.
**Phase:** executing (single dispatch). **FIX-ONLY. No schema, no migration, no data correction.**
**Base:** branch `d31-exit` @ `14568739` in the EXISTING worktree `.worktrees/d31-exit`. Do NOT create
a new worktree. Do NOT rebase. Suite off that head: **10812 passed / 7 skipped / 1 failed** — the
failure is a PRE-EXISTING flake, see §4 item 7.

> **TWO items. This is the last pass; the arc merges after it.** One is a one-argument production
> change that must ship WITH an explanation of what it deliberately does NOT fix. The other is a stale
> test fixture. **If you find yourself scoping anything else, that is the signal to STOP and report.**

---

## §0 Read first

1. **`docs/d31-exit-orchestrator-b-review-round4-findings.md`** — the findings and the adjudication.
2. `docs/d31-exit-closeout-brief.md` — the previous pass; its scope and conventions still bind.
3. `docs/implementer-dispatch-recipe.md` — the protocol.

### ACCEPTED LIMITATIONS — declared so you neither fix them nor re-argue them

**Canonical practice as of `0470737e`.** Each carries its REASON. **If you think a reason is wrong,
say so in your return report — that is invited.** What is not useful is re-opening them as
undiscovered.

1. **Fractional quantities ≥ 1 are misrepresented** (hashed/compared as 10.9, displayed/persisted as
   10). *Reason: the `int`→`float` migration touches the dataclass contract, envelope, signature and
   form — banked as its own arc; live ledger has 43 fills, zero fractional.*
2. **`SchwabSchemaParityError` escapes the handler at `:699` → 500.** *Reason: pre-existing, zero
   occurrences in 7,795 production calls, and the same MRO gap plausibly affects every handler using
   that tuple — the fix is scoped to that class, not this line.*
3. **`fill_datetime` reduced by an unchecked `[:10]`.** *Reason: the canonical-form assertion is
   unwired at the repo insert and needs a `swing/data` carve-out; this channel can only ADD a flag,
   never exclude, so the cost is a spurious alarm, not a silent omission.*
4. **The auto-fill envelope is client-editable and unsigned.** *Reason: banked to its own arc.*
5. **The ENTRY side renders no date-grain provenance.** *Reason: out of scope for an exit-side arc.*
6. **`trade_exit_form.html.j2:139`** — a sub-half-cent price renders `0.00`, the POST compares rounded
   values, and persistence then violates `fills.price CHECK(price > 0)` as an `IntegrityError` the
   `ValueError` handler misses → 500. *Reason: PRE-EXISTING since `33e48c00`; this arc's whole
   template diff is 7 insertions / 2 deletions. Banked with the register.*
7. **`trade_exit_form.html.j2:143`** — candidate quantity is rendered unchecked against
   `remaining_shares` while the same control sets `max` to it (`max="4" value="10"`), so the browser
   refuses the submit with no explanation and no recovery. *Reason: PRE-EXISTING, same origin.
   Banked with the register, labelled as the same class as an advisory instructing an impossible
   action.*

---

## §1 The tolerance — a rel+abs hybrid, shipped WITH its stated asymmetry

`swing/trades/exit_auto_fill.py:1418`:

```python
math.isclose(row_quantity, quantity, rel_tol=0.0, abs_tol=1e-9)
```

**`rel_tol=0.0` is explicit, so an absolute tolerance stands alone against a relative error over an
unbounded domain.** Verified numerically (reproduce it yourself; do not take it from this brief):

| case | residual | current result | consequence |
|---|---|---|---|
| `10000000.1 + 0.2` vs `10000000.3` | **1.862645e-9** | `False` | **a genuine duplicate is offered CLEAN** — the silent miss the whole rule forbids |
| `10.0` vs `10.0000000005` | 5.0e-10 | `True` | two DISTINCT quantities flagged as the same row |

**This is IN SCOPE and it is the arc's own:** `git log -S "abs_tol" -- swing/trades/exit_auto_fill.py`
names exactly one commit, `5203caa9` — this arc's B-round-1 fix, which closed the exact-float-equality
silent miss and opened this one.

**The fix:** give `math.isclose` a relative tolerance as well (`rel_tol=1e-9` verified to return `True`
on the large-magnitude case).

**RD's requirement, and it is the half that is easy to skip:** the hybrid does **NOT** tighten the
small case — `10.0` vs `10.0000000005` still flags — and **that is CORRECT**, under the asymmetry the
site already states: *a spurious flag is adjudicated by the operator; a silent miss is not.*
**Say so at the site**, so the next reviewer does not read the surviving looseness as an oversight and
"fix" it into a silent miss. Describe what the code does today; promise nothing about a future arc.

**Tests:** pin BOTH directions. The large-magnitude case must flag (it must FAIL under `rel_tol=0.0` —
observe that red before you fix it, and report that you did). The small distinct-quantity case must
STILL flag, so a later tightening that trades a spurious alarm for a silent miss goes red here.

## §2 The stale fixture — operator-facing wording this arc retired

`tests/web/test_routes/test_exit_form_auto_fill.py:805` (the section) and `:858` (the fixture).

The section still describes "fallback dedupe," and the fixture injects **"recorded under the OLD date
convention"** — wording this arc's production code explicitly identifies as false and retired. The
assertions check only generic duplicate markers, so **the test would stay green if that false
operator-facing text were restored.**

Correct the section description and the fixture wording to what production now says, and make the
assertions discriminating enough that restoring the retired text goes red.

## §3 Scope

**In:** `swing/trades/exit_auto_fill.py`, `tests/web/test_routes/test_exit_form_auto_fill.py`, and any
test file needing a §1 case. **Out — flag, never fix:** everything in the §0 accepted-limitations
list; the template; `swing/integrations/schwab/`; no schema, no migration.

## §4 Conventions and gates

Conventional commits; **no `Co-Authored-By`, no `--no-verify`, no amending**; quoted heredoc with the
last paragraph plain prose. Frozen-clock for date-touching tests. **Verify every claim against the
code, including this brief's, and report every count with the method that produced it.**

1. Full fast suite **BEFORE** the Codex loop.
2. Codex §3 at the **`strong`** tier, all four per-round assertions including the anchored
   `grep -c '^tokens used'`. **`NO_NEW_CRITICAL_MAJOR` IS THE END.** **Declare the §0
   accepted-limitations list to your reviewer WITH ITS REASONS and invite it to challenge the
   reasons** — canonical as of `0470737e`, and it demonstrably prevents re-litigation without
   suppressing findings.
3. **DO NOT RUN `codex-auto-review`, and do not offer focus areas for it.**
4. Full fast suite **AFTER** convergence off the final head, plus the trailer audit on the trailer
   **KEY**.
5. **The WSL Codex invocation needs `export PATH="$HOME/.local/node22/bin:$PATH"` IN A SCRIPT FILE**,
   not inline — this harness expands `$VAR` before the command reaches WSL, and without the prefix
   `codex` resolves to a dead npm shim that fails with `exec: node: not found` **and exits 0**. Probe
   `codex --version` (expect `codex-cli 0.147.0`) first.
6. `tests/integrations/schwab/test_ladder_stress_production_path.py::test_forced_finish_lock_leaves_in_flight_row`
   — known load-sensitive flake; confirm the mechanism, re-run isolated, do not fix.
7. **`tests/scripts/test_weeknight_wrapper.py::test_run_stub_skip_exits_zero` fails on `main` itself**
   — verified by the orchestrator by running it on `main`, where none of this arc's code exists. It is
   NOT yours, it is not a regression, and it is not to be fixed here.

## §5 Return report

Final chat message. **Do NOT run `scripts/role_mail.py`; do not post to any inbox; never
`--from orchestrator`.**

Include: per-item disposition with file:line as shipped; **confirmation that you observed the §1 large-
magnitude test RED before fixing**; the asymmetry wording you wrote; commits; test counts off the
FINAL head with the command that produced them; Codex rounds with per-round assertions and the
findings path; whether any accepted limitation was raised by your reviewer and how you dispositioned
it; the trailer-audit result; and everything flagged-not-fixed.
