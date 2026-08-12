# D31-exit — the orchestrator's B review, round 3, and an admission about the prompt

**Reviewed tree:** `d31-exit` @ `2b869feb`. **Verdict: `NEW_CRITICAL_MAJOR_FOUND`** — 3 MAJOR, 4 MINOR.
**Transcript:** `.codex-b-review-orch-3b.txt` (1,047,462 bytes). **Assertions:** `gpt-5.6-sol` / `high` /
anchored `^ERROR` **0** / anchored `^tokens used` **1** / `EXIT=0` / `read-only`.

**A first attempt produced 79 bytes and exited 0** — preserved as
`.codex-b-review-orch-3-DIED-dead-npm-shim-no-banner.txt`. Its entire content is
`/mnt/c/.../npm/codex: 15: exec: node: not found`. **I caused it:** I dropped the
`export PATH="$HOME/.local/node22/bin:$PATH"` prefix after the fix-arc implementer proved this
harness expands `$VAR` before the command reaches WSL. The expansion finding was true; my inference
from it was not. Memory `feedback_wsl_native_codex_invocation` records that the prefix is REQUIRED
and that its absence resolves the dead shim. **I overrode recorded evidence about behaviour with an
inference about mechanism.** The invocation now runs from a script file (which demonstrably preserves
`$HOME`/`$PATH`) and probes `codex --version` before spending a review.

**`EXIT=0` on a totally failed run.** The exit-code capture I added last round would have scored it a
success. Only the absent banner caught it. **Two dead runs now, two different signatures — one with a
banner and no footer, one with neither — and both exited clean.** For CHARC: exit status is not
evidence of a review; the banner is.

---

## THE ADMISSION: two of the three majors are items ALREADY RULED, which my prompt failed to declare

**MAJOR 3 (`exit_auto_fill.py:1148`) — fractional ≥ 1 misrepresented** is **the twice-banked type
migration.** RD banked it, I brought it back with new information, he reversed on the sub-1-share
half and **re-banked the rest.** My round-3 prompt stated Rule 4 for the sub-1-share crash but never
told the reviewer that the fractional-≥1 disagreement is a KNOWINGLY ACCEPTED limitation. So B
reported it against the contract I handed it, correctly.

**MINOR (`view_models/trades.py:1144`) — malformed `[:10]` date** is the cited
`assert_canonical_fill_datetime` item **RD already ruled stays cited** for the `swing/data` carve-out
arc. Same cause: undeclared.

**A reviewer that is not told what has been accepted will re-find it every round, forever.** That is
not the reviewer malfunctioning; it is me feeding it an incomplete contract, and it is the mechanism
by which a review turns into a treadmill.

**The fix is proven — in this very round.** Round 2's B raised the read path's non-re-derivation as a
MAJOR. For round 3 I declared it as a deliberate contract WITH its live-evidence reason, and
explicitly invited the reviewer to challenge the contract rather than forbidding the topic. **B did
not raise it, and still found three majors.** Declaring accepted decisions suppresses re-litigation
without suppressing findings. Every future B prompt on this surface carries the accepted-limitations
list.

---

## GENUINELY NEW AND REAL

### MAJOR 1 — `SchwabSchemaParityError` escapes to a 500 (`exit_auto_fill.py:699`) — PRE-EXISTING

Verified by MRO, not by reading the `except`: `SchwabSchemaParityError` →
`_RedactedMessageError` → `RuntimeError`. It does **not** subclass `SchwabApiError`, so the handler's
`except (SchwabAuthError, SchwabRateLimitError, SchwabApiError)` misses it, and neither
`build_exit_form_vm` nor the GET route converts it. The mapper raises it deliberately for malformed
broker shapes (`integrations/schwab/trader.py:665`). Result: the audit row closes and the operator
gets a 500 instead of the `kind="error"` refusal every other Schwab failure produces.

**`git log -S "SchwabSchemaParityError" -- swing/trades/exit_auto_fill.py` is EMPTY** — this arc never
touched it. **Pre-existing, and unrelated to the date grain.** It surfaced now only because my prompt
generalised the sub-1-share ruling into "a crash on input the schema and the broker permit is a
defect," and B applied that rule to the whole file.

**It is the same class RD just called merge-blocking** — a crash from externally-permitted input —
which makes its scope his call rather than mine.

### MAJOR 2 — first-match refusal precedence (`exit_auto_fill.py:1127`)

The fix-arc implementer FLAGGED this itself and **pinned first-match with a test**, reasoning that
reordering only relocates the incompleteness. B's counter is specific and lands: for a `FILLED`
order with `quantity=0.9`, a price present and `executions=None`, the reason is `no_execution_price`
alone, so the sub-one-share note never fires — and **the operator is told to record the fill by hand
when the form's `min="1"` forbids exactly that.** The test at `tests/trades/test_exit_auto_fill.py:2134`
pins that outcome as correct.

The implementer's reasoning is sound about precedence in general and wrong about this instance: the
defect is not which reason wins, it is that the advisory instructs an impossible action. Reporting
ALL applicable reasons, or suppressing the manual-entry instruction when the sub-one-share condition
holds, resolves it without a precedence debate.

### The real minors

- **`execution_dates.py:211`** — the docstring claims BOTH auto-fill consumers make the entered-date
  fallback "VISIBLE." The ENTRY side puts `entry_date_source` in hidden JSON, returns
  `advisory_text=None`, and renders no provenance marker. A false claim about a sibling module.
- **`tests/trades/test_exit_auto_fill.py:861`** — says all-refused results get a generic advisory
  while reason-specific text is populated-only. The fix arc changed exactly that, and the test's
  assertions pass under either behaviour, so it no longer protects the distinction it describes.
- **`exit_auto_fill.py:1345` / `test_exit_auto_fill.py:1742`** — the implementer already flagged the
  tolerance's real limitation; the NEW half is that the TEST docstring still claims the tolerance
  "cannot conflate" distinct quantities while its discriminator only checks a 1e-4 difference.

---

## Disposition

**MERGE REMAINS BLOCKED, and the arc should be CLOSED OUT rather than grown again.**

1. **A short, bounded final pass:** MAJOR 2 plus the three real minors. All are small, and none is a
   design question.
2. **MAJOR 1 OUT OF SCOPE — banked as its own named item, with RD consulted on severity.** It is
   pre-existing, unrelated to the date grain, and lives in the Schwab error surface. Absorbing it
   would let a fix arc swallow the surrounding module, which is how a bounded arc becomes unbounded.
   But it is a real 500 of the class RD just refused to clear past, so he decides whether it blocks
   this merge or opens a follow-on.
3. **MAJOR 3 and the malformed-date minor: NO ACTION.** Already ruled. They are recorded here as
   *declared* rather than *found* so the next round does not re-litigate them.

**This is not the schema-boundary treadmill (#39) — every finding here is real.** It is a different
failure: a review measured against a contract that omits what has already been decided. The
countermeasure is the accepted-limitations declaration, and it demonstrably works.

---

# BANKED ITEM (RD-ruled 2026-08-12) — the Schwab error-tuple parity gap

**Ruling: BANK AS A NAMED FOLLOW-ON.** The boundary is **INTRODUCED vs PRE-EXISTING**, and severity
does NOT override it. RD's reasoning, kept because it is the part that gets tested next time: *"If
identical operator experience were sufficient to pull a pre-existing defect into an arc, the boundary
would have no content at all — every pre-existing defect produces some operator experience, so the
exception would swallow the rule and every bounded arc would end where its reviewer's imagination
did. What makes an arc bounded is precisely that it declines work it did not cause."* The answer to
"pre-existing is the excuse this project distrusts" is not to abandon the boundary but to make the
banked item REAL. **Bank ≠ forget.**

**THE EVIDENCE, so the next reader inherits it rather than the claim:**

- **Site:** `swing/trades/exit_auto_fill.py:699`.
- **Handler tuple:** `except (SchwabAuthError, SchwabRateLimitError, SchwabApiError)`.
- **MRO:** `SchwabSchemaParityError` → `_RedactedMessageError` → `RuntimeError`. **It does NOT descend
  from `SchwabApiError`, so the tuple misses it.** Verified BY MRO, not by reading the except clause —
  which is the only reason it was found at all, and is the method the next reader should copy.
- **The raise is deliberate:** `swing/integrations/schwab/trader.py:665`, for malformed broker shapes.
- Neither `build_exit_form_vm` nor the GET route converts it → **500 instead of the `kind="error"`
  refusal every other Schwab failure produces**, after the audit row has already been closed.
- **Production incidence (RD's query, 2026-08-12): `schwab_api_calls` total 7,795 — success 6,495 /
  error 1,289 / auth_failed 11. `error_message` matching 'parity' or 'schema': ZERO. Errors on
  `accounts.orders.list` all-time: 3** (1,278 of the 1,289 are `marketdata.pricehistory`). **A
  schema-parity failure has never fired in production on any endpoint.** RD noted the answer *could*
  have changed his ruling: recurring live parity failures on the orders endpoint would have pulled it
  in-arc regardless of the boundary.
- **Not this arc's:** `git log -S "SchwabSchemaParityError" -- swing/trades/exit_auto_fill.py` is
  EMPTY.

**SCOPED TO THE CLASS, NOT THE LINE (RD).** The follow-on question is *"which handlers catch the
Schwab error tuple, and does `SchwabSchemaParityError` escape each?"* — the same MRO gap plausibly
reaches every surface using that tuple. Fixing this one call site would be the instance-patch this
project keeps learning not to accept, **and that is why banking is the better answer here rather than
merely the cheaper one: the right fix is wider than this arc could have taken.**
