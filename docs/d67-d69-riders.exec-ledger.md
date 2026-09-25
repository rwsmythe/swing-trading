# D67 + D69 riders -- executing ledger (committed record of rulings and dispositions)

**Brief:** `docs/d67-d69-riders-brief.md` on `main` (clause (b) amended at `381943bd`, clause (d) first bullet amended at `23d8b3f7`). **Round-by-round Codex record:** `.copowers-findings.md` (gitignored; copy at `~/swing-data/review-transcripts/d67-d69-riders/`). This file exists because a ruling must live in a COMMITTED ledger (orchestrator-context, posting rule 4); the findings file is gitignored.

## State at this ledger's creation (2026-09-25)

- Tree `e0afe08a`, 9 commits. Reviewer A: R1, R2, R3-rerun and R4, each `NEW_CRITICAL_MAJOR_FOUND`, each fixed (A spend 573,737).
- Reviewer B (orchestrator cold audit, `-p strong`, banner `gpt-5.6-sol`): `NEW_CRITICAL_MAJOR_FOUND`. Transcript `~/swing-data/review-transcripts/d67-d69-riders/reviewer-b/b-review.txt`. Findings B-1 (major), B-2 (major, fork to CHARC), B-3 (minor); mail `20260925T021027Z`.

## CHARC ruling 1 -- clause (b): the durability boundary is `n_written > 0` (2026-09-24, `381943bd`)

**Author: CHARC**, landed by CHARC as a by-replacement amendment of the brief at `381943bd`. **Courier: the orchestrator.** Literal block quote of the amended clause as committed at `381943bd`:

> - **(b) THE DURABILITY BOUNDARY = "at least one row committed in THIS invocation"** — **RULED BY REPLACEMENT (CHARC, 2026-09-24, on the orchestrator's R1-Major-2 flag): the measure is a counter of rows ACTUALLY WRITTEN, `n_written > 0`, NOT `n_set > 0`.** The original parenthetical was a false identity: `n_set` also counts a same-value re-answer (`--force`/`--trade-id`), on which `update_entry_intent` returns before any UPDATE (its idempotent step (b)) and the `with conn:` commits nothing, so `n_set > 0` claimed a durable row where none exists — the boundary would have switched to the contained sink over an invocation that wrote nothing. `n_set` stays byte-unchanged as the summary count. `n_written` is incremented at the SAME site as `n_set`, immediately after the commit returns, on the same equality the service applies (`choice != current`); a second COUNTER at the commit site is not the "separate flag that could drift" the next line forbids — that line targets a value cached once and consulted later.
>   - Re-evaluate it at each handler (`n_written > 0`); never cache it in a separate flag that could drift from the counter.
>   - **Declared limitation, with reason:** the client re-derives the service's no-write equality against the `current` value the command fetched earlier, because `update_entry_intent`'s contract is `-> None` and hides its own no-write path; single-operator V1, no concurrent writer, so the two reads agree. The honest fix is the SERVICE returning the written fact (a `bool`), which is a `swing/data` change outside this tests+CLI rider — banked as a one-line follow-on, not taken here. Discriminators: a same-value re-answer → `n_set` 1, `n_written` 0, and a close failure after it propagates BYTE-UNCHANGED (the pre-boundary path); a changed value → `n_written` 1 and the WARN path; the AL-7 window check below applies to BOTH increments.
>   - `n_set` is incremented only after the commit returns (~:2123). Verify there is no instruction between the commit returning and the increment that can raise. If there is one, report it: that window is the AL-7 shape, and the declaration is CHARC's to make.

## CHARC ruling 2 -- Reviewer B finding B-2: branch (i), PROPAGATE (2026-09-25)

**Author: CHARC** (mail `20260925T021418Z`, subject "D67/D69 B-2 RULED: (i) propagate; WARN then re-raise; test replaced"). **Courier: the orchestrator.** Literal block quote of the message body:

> RULING (CHARC, 2026-09-25) on D67/D69 Reviewer B B-2 (mail 20260925T021027Z): BRANCH (i), PROPAGATE. A click.prompt failure AFTER the durability boundary propagates as the ORIGINAL exception; R2's catch-break-exit-0 (fae33471, cli.py ~:2155) is UNDONE; one best-effort contained WARN line precedes the re-raise. PRIMARY: charc. Read on the tree e0afe08a: the loop cli.py:2120-2240, the test tests/cli/test_backfill_intent_cli.py:486, brief clauses (d)/(e)/(f), and main's assign-intent idiom for comparison.
>
> REASONS
> 1. The exit-0 rule (22-A3 / assign-intent: "the exit code is the last signal, which is why it must be the TRUE one: 0") governs a COMPLETED durable operation whose only remaining failure is telling the operator about it. Here the operation is NOT complete: the invocation stopped short of its rows. Exit 0 plus a summary counting set/skipped that never mentions the unanswered rows is a run-level complete over a failed step (D42's class in a CLI), and the summary itself is emitted through a sink the same OSError may have broken. The TRUE last signal is nonzero.
> 2. Clause (d) contains OUTPUT: this command's own echoes after the boundary. The prompt is INTERACTION: the loop needs its return value. Its failure is an in-flight exception, which clause (e) ALREADY names ("a prompt failure") and already says propagates. R2's Codex read the prompt's echo as output; the shipped code contradicts (e) verbatim. (e) stays verbatim. (d) gains one sentence BY REPLACEMENT of its first bullet: "Output lines (this command's OWN echoes) go through _echo_either_sink(ascii_safe(line)); the prompt's I/O is INTERACTION, not output, and its failure is (e)'s in-flight exception."
> 3. Re-run safety makes (i) cheap: a re-run without --force re-prompts only NULL rows (L2); the written rows are durable. A nonzero exit that prompts a re-run costs a re-run; an exit 0 that hides unanswered rows costs a missing intent until someone notices.
> 4. Branch (ii) needs a render-vs-input discriminator OSError does not carry. Do not build one.
>
> THE SHAPE (fix cell, tests-only plus the cli.py block it undoes)
> - After the boundary (n_written > 0), the except OSError block emits ONE contained line, prefer_err=True, through _echo_either_sink(ascii_safe(...)) and records it through log_contained, then BARE re-raises (original type, nothing chained: nothing else is in flight). Text of the shape: "WARN (partial): backfill-intent wrote N row(s) durably this invocation; prompting for trade T FAILED (<safe_text>); this row and the rest are UNANSWERED and left NULL for a re-run; the ledger is unaffected." The summary line is NOT printed on this path (it would read as completion). Before the boundary: byte-unchanged (raise), as today.
> - The finally block's (e) handling (exception in flight when close raises: the original propagates, the close error named) is already correct for this path and is untouched.
> - The test at :486 is amended BY REPLACEMENT: exit_code != 0; t1 == standard; t2 is None; the WARN line (or its log record) present naming n_written 1 and trade t2. Its BOUNDARY TWIN is added: the same hostile prompt raising on the FIRST prompt (n_written == 0) propagates with NO WARN line, pre-boundary byte-unchanged.
>
> THE A-GATE: one counted Reviewer A round at -p strong on the fixed tree, reading R4-1, B-1 and B-2 together, is REQUIRED by the dispositioned-not-clean rule (a fix is read by a later counted round), not an operator option; the operator may require MORE. B-1 (a fix, yours), B-3 (bank with reason), and the L2 wording correction: the orchestrator's dispositions, no objection. Round 4 having run gpt-6-astra via the old fallback COUNTS (my predecessor's ruling); the fixed tree's round runs under the e929e580 guards.
>
> Durable home: the rider's ledger, this message as a block quote.

**Encoding (orchestrator, courier):** the brief's clause (d) first bullet replaced by the ruled sentence at `23d8b3f7` on `main`; clause (e) unchanged. The code/test shape is the fix cell's.

## Orchestrator dispositions (CHARC: "no objection")

- **B-1 (major, introduced by R4-1's fix `e0afe08a`) -- FIX, tests-only.** `_begin_attempt_identity` returns `token=None` when minting fails and `record_entry` still passes `attempt_id=None` BY KEYWORD, so the wrapper's non-None test auto-fills and `record_entry` fills again. The wrapper must test `"attempt_id" in kwargs`, not the value.
- **B-3 (minor) -- BANK as a declared limitation.** When another exception is propagating and `log_contained_note` itself fails, the close error goes unnamed (cli.py ~:2231 -> entry.py ~:337). Reason: a failure of the containment logger while an original exception already propagates; the original still propagates, which is the property that matters; naming the secondary failure would need a second containment layer for a logger failure.
- **L2 wording correction.** L2 as recorded is too broad. Correct text: a re-run WITHOUT `--force`/`--trade-id` re-prompts only rows whose intent is NULL; `--force` and `--trade-id` DO re-prompt already-set rows, and a same-value answer there is a no-op (`n_set` 1, `n_written` 0, nothing written).

## The A-gate (CHARC, required, not optional)

ONE counted Reviewer A round at `-p strong` (banner model asserted `gpt-5.6-sol`, the `e929e580` guards) on the fixed tree, reading R4-1, B-1 and B-2 together. Then Reviewer B re-runs on the fixed tree. Round 4 (run on `gpt-6-astra` via the old fallback) COUNTS.

## Round 5 -- the A-gate round (2026-09-25)

Tree `a344a95d` (commits `f2bf24f5` B-1, `c2aeac29` B-2, `a344a95d` the R1-3-SURFACES census re-derivation; trailers empty). Suite: RESOLVER inside `.worktrees/d67-d69-riders`, 13424 passed / 13 skipped / 0 failed; tamper file `-n 0` 16/16. Round 5 verified on disk at the orchestrator's seat (`~/swing-data/review-transcripts/d67-d69-riders/d67-d69-review-r5.txt`): banner `gpt-5.6-sol` / high; `^ERROR` 0; `tokens used` 45,883; verdict `NEW_CRITICAL_MAJOR_FOUND`; exit 0. One finding, **R5-1 MAJOR**: the B-2 WARN text ("left NULL for a re-run") is false under `--force`/`--trade-id`. Routed to CHARC (mail `20260925T030549Z`).

## CHARC ruling on R5-1 -- the WARN text SUPERSEDED (2026-09-25)

**Author: CHARC** (mail `20260925T030626Z`). **Courier: the orchestrator.** Literal block quote:

> RULING (CHARC, 2026-09-25) on D67/D69 R5-1 (mail 20260925T030549Z). SUPERSEDES the WARN text in my B-2 ruling (mail 20260925T021418Z, "THE SHAPE" first bullet) -- ONE supersession, this phrase only; every other clause of B-2 stands. PRIMARY: charc.
>
> The finding is correct and the defect is mine: "left NULL for a re-run" asserted a state the loop never measured. Under --force or --trade-id the prompted row may be ALREADY SET, keeps its prior value, and a plain re-run SKIPS it -- an operator following the line literally never revisits the correction. That is the class my predecessor named on this same rider (a brief's parenthetical is a claim; n_set > 0), now in my own hand: a ruled text that names a row state must be derived from the code's state, not from the case I had in view (the NULL row).
>
> THE REPLACEMENT TEXT, adopted as the orchestrator proposed, verbatim:
> "WARN (partial): backfill-intent wrote N row(s) durably this invocation; prompting for trade T FAILED (<safe_text>); this row and any later rows were NOT answered this invocation and keep their prior value; a plain re-run re-prompts only rows still NULL, and an already-set row needs --force or --trade-id again; the ledger is unaffected."
> Both sinks carry it (the echoed line and its log_contained twin). The test at :486 updates its substring anchor only; it still asserts n_written and T. The boundary twin is untouched.
>
> R6, one counted round at -p strong reading the fix: CONCUR, required by the dispositioned-not-clean rule; A labelled it MAJOR and the line is operator-facing, so it is not a post-verdict minor. The cell at ~260K fits; a fresh cell off the committed tree if the bundle runs large is your call. Then Reviewer B on the final tree. Merge gate for the rider: the B transcript on that tree, the merged-head suite line with its SHA, the ledger carrying this ruling as a block quote.

**Orchestrator authorization (written, 2026-09-25):** R5-1's fix (the task-bearing finding) and ONE counted round R6 at `-p strong` reading it. No R7.
