# D94 (a)+(b) -- latch validity prompt gate + ledger-keyed cancel affordance: WRITING-PLANS dispatch brief

**Audience:** a fresh implementer cell with no prior conversation context.

**Authority:**
- **Operator, 2026-10-25:** the hold is lifted, and "D94 web fix first" (parts (a) and (b) only, ahead of D84).
- **Register row D94** in `docs/tool-director-context.md` (search `| D94`). Read it in full.
- **RD's semantics ruling** (BINDING): `comms/orchestrator/read/20261022T092803Z-rd-d94-ruled-accepted-stands-cancel-is-its.md`.
- **CHARC's form** (BINDING): `comms/orchestrator/read/20261022T093007Z-charc-d94-form-a-prompt-gate-b-ledger-keyed-ca.md`.
- Read both mails in full. Block-quote both in your plan ledger with their authors.

**Cell:** `implementer-opus-high`. The design is ruled and shaped; this is a web-layer rider with careful discriminators.

**KEEP YOUR READING NARROW.** Earlier planning cells ran past the context cap by reading the whole comms record. Read only:
- this brief;
- the D94 row and the two mails above;
- `docs/implementer-dispatch-recipe.md` section 3 (the plan-stage protocol and per-round assertions);
- the code named below.

Do not read other `comms/`, director state files, or other arcs' ledgers.

**Worktree:** create `C:\Users\rwsmy\swing-trading\.worktrees\d94-cancel` on a new branch `d94-cancel` off main at the commit that carries this brief. Run everything with `PYTHONPATH=.`. The live DB is read with `mode=ro` only, never through `swing`'s `connect`.

## 0. Scope (RD + CHARC, summarised; the mails govern)

- **Not a new outcome.** `validity_outcome = 'accepted_by_broker'` STANDS for an accepted-then-cancelled order. Cancellation is the existing `intent_kind = 'cancel'` row naming one broker order id (`0033:662-665`).
- **(a) Prompt gate.** A correction control on an ACCEPTED validity row is offered only while the order's absence from the book is UNEXPLAINED.
  - A `cancel` row naming that `actual_broker_order_id`, or a fill, EXPLAINS it.
  - The control is then replaced by a read-only line: "accepted <date>; cancelled by you <date>, intent <id>".
  - This is a read of the intents the panel already loads, inside `_validity_prompts` (`swing/web/view_models/latches.py` about :3155).
- **(b) Ledger-keyed cancel affordance.**
  - It is offered for every ACCEPTED validity row whose order is not resting and not explained, keyed on the ledger's `actual_broker_order_id`, NEVER on the live book.
  - Today the cancel controls are built `for row in attribution` (the resting book, about :2604-2616). After the change, the source set is the union of `attribution` and the unexplained accepted rows.
  - The cancel POST already accepts any non-empty id and reads no book, so this needs no route change.
- **(a) and (b) together are ONE web-layer rider: no route, no schema, no tripwire.** If the code says otherwise, that is a FORK: stop and return.
- **OUT of scope:**
  - (c), the broker-history tier: a schema tripwire, not this rider;
  - any new `validity_outcome` value;
  - any change to the authorization chain's reads (`0037`/`0039`);
  - `compute_execution_parity`;
  - `swing/data/`, `swing/trades/`, migrations.

## 1. Code to read

- `swing/web/view_models/latches.py`:
  - `_validity_prompts`;
  - the cancel-control build over `attribution`;
  - `intents_by_latch`;
  - `_resolve_orders` (about :2005-2095);
  - the option labels (about :2684-2689).
- `swing/latches/orders.py` (`to_resting_orders`).
- `swing/web/routes/latches.py`: the cancel and validity POST routes, to confirm they need no change.
- `swing/web/templates/partials/latch_orders.html.j2`.
- `swing/latches/classification.py`: only to confirm that nothing there needs to change.
- The existing latch-orders tests: `tests/web/test_routes/test_latches_orders_fragment.py` and the VM tests they sit beside.

## 2. Round 0 (a premise check, no Codex)

Verify RD's and CHARC's code facts against the code. Then, from the live DB (`mode=ro`), state which live rows each prompt and control would render after the change:
- OII link 1;
- DFTX link 2, with cancel row 11;
- IMNM links 3 and 4, where link 3 is cancelled by row 10;
- RHI place 4, which has NO validity row.

RD's expectation, to confirm or refute:
- **DFTX and IMNM link 3:** a read-only explained line.
- **OII and IMNM link 4:** a ledger-keyed cancel control with no false downward prompt. The correction control stays available, because R6 keeps an erroneous accepted row correctable; how the two controls coexist is a plan item.
- **RHI:** a first-answer prompt only.

**If every premise holds and no fork appears:** write the plan, and report the census in your return.
**If anything fails:** STOP AND RETURN with the census and both branches of each fork.

## 3. The plan

Follow the recipe's plan-stage protocol: a task ladder and a test roster of about 1,000 lines or fewer, with a ledger beside it. Carry CHARC's discriminators verbatim, each RED first:

- **Explained:** a seeded accepted row plus a cancel row naming its id renders NO prompt, and the read-only line instead.
- **Ledger-keyed:** an accepted row whose order is absent and has NO cancel row renders the cancel control from the ledger key WITH THE BROKER BOOK EMPTY in the fixture.
  - This is the anti-vacuity check: the control must not depend on `attribution`, or the fixture routes around the branch.
- **First answer:** a place row with no validity row (RHI's shape) renders a first-answer prompt and nothing else.
- **No regression:** the existing resting-book cancel control still renders for a resting order.
- **Round trip:** a cancel POST from the ledger-keyed control writes ONE `cancel` row naming that id, and on reload the explained line replaces the control.
- **Fill:** an accepted row whose order filled (a fill row) is also EXPLAINED. State how a fill is recognised and pin it.

**HTMX:** this is HTMX form work, so the plan carries an **operator-witnessed browser step at the merge gate** (CLAUDE.md: browser verification is BINDING for HTMX work). Embedded forms need `hx-headers`, and the success path is `204` + `HX-Redirect`. Check both on the new control.

**Rounds:**
- `fast` tier, at most THREE counted rounds, then the self-sweep.
- Rulings are inlined in the prompt, or given as a ledger copy cut before its round section.
- The verdict tokens are DESCRIBED, never written line-initially; grep the prompt to prove it.
- A per-item checklist, each item answered holds / fails / cannot-tell with a file:line.
- No prior-round reads, proved by grep.
- Every per-round assertion holds.
- Evidence goes to `C:\Users\rwsmy\swing-data\review-transcripts\d94-cancel\plan\round<N>\`.
- **STOP AND RETURN at EVERY counted round gate** with its ledger row, leaving the depth column empty.
- Commit the plan ONCE, at convergence.

## 4. Gates and return

- Commits are conventional and pathspec-only. `%(trailers)` is empty; no final `-m` paragraph begins with `Word:`; no Co-Authored-By, no `--no-verify`, no amend.
- No `swing/` change: this is planning.
- **Return in chat only.** You NEVER post to a mailbox and never run `scripts/role_mail.py`.
- **If anything does not fit, STOP and return.** Do not choose for yourself.
