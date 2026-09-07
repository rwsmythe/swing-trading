> Delivered to swing-trading by the operator, 2026-09-07, by the same convention as `token-efficiency-findings-coa.md` (untracked here; source of record is coa-chess). Source: coa-chess CHARC session 5795e615; the rule amendment is coa-chess commit f9deac81 (recipe + fill + standard). The measuring pass at the bottom is a short read-only script over `~/.claude/projects/<slug>/*/subagents/*.jsonl` and was run against THIS project's transcripts for the numbers in Sec 3.

# A depth cap on cells is binding on a number the cell cannot read -- and the dispatcher can

**From:** coa-chess CHARC, 2026-09-07. **Purpose:** coa-chess adopted a ~400K context-depth cap on
2026-09-06 (from the joint token-efficiency review: context depth is the dominant spend; 68% of read
tokens landed on turns above 400K). One day in, the rule turned out to rest on a premise that is
false for every cell in every Claude Code harness, and the fix is a dispatcher-side instrument that
ports unchanged. Swing-trading should know before it writes the same rule, or if it already has.

## 1. The finding

**A subagent (an implementer cell) can NEVER see the `[ctx]` depth line, or any output of the
`UserPromptSubmit` hook.** That hook fires when a USER submits a prompt to the main session. A cell
dispatched through the Agent tool never receives a user prompt, so the hook never fires for it.

coa-chess's rule had told cells to read their depth from that line and put it in the review ledger
every round. Three cells in one day reported "no `[ctx]` line seen all session" or gave an estimate.
The dispatcher could not see cell depth either. Result: two dispatches went out to cells sitting at
~540K and ~650K, both caught by the operator, neither by the harness.

**Verified, not inferred:** across 70 cell transcripts in the coa-chess project, ZERO carry a
hook-produced `[ctx]` line. The single textual hit is the cell that BUILT the gauge, quoting the
line in its own brief and test. Every occurrence of the hook's name inside cell transcripts is quoted
text, none is a hook record.

## 2. The instrument that works, and reproduces

Each cell's transcript lives at
`~/.claude/projects/<project-slug>/<session-id>/subagents/agent-a*.jsonl`. Every assistant record
carries `message.usage`. On a single request:

    depth = input_tokens + cache_read_input_tokens + cache_creation_input_tokens

is the context presented to the model that turn -- the cell's depth. The LAST record's value is the
current depth; the maximum over the file is the cell's high-water mark. coa-chess's orchestrator
found this and measured three live cells; CHARC reproduced all three from the raw files (two exact,
one differing only because the cell had kept running). The operator's independent reading of the same
cells agreed within 0.4%.

**Two traps, both paid for:**
- A naive glob of the project directory MISSES `subagents/` entirely. One arc's spend was
  undercounted by 43% (9.18M vs 16.06M) that way. Any transcript sum must include it.
- In newer transcripts the filename carries the cell name (`agent-a<name>-<hash>.jsonl`). In this
  project's transcripts it does not (`agent-a<hash>.jsonl`); the cell's identity is in the first
  record's content instead.

## 3. This project's own numbers (measured 2026-09-07 from its transcripts)

| | |
|---|---|
| cell transcripts on disk | 37 |
| cells whose peak context exceeded 400K | **24 of 37** |
| cells whose peak exceeded 800K | 3 |
| six deepest peaks | 990,589 / 878,622 / 814,146 / 752,022 / 727,542 / 672,112 |

For comparison, coa-chess's six deepest cells peaked 931K-972K. In both harnesses the cell tier has
been running to the full window. That is where the cell-side spend went, and it is the strongest
single argument a depth cap has -- provided the cap is checked by someone who can see the number.

## 4. What coa-chess changed (one meaning, written in three docs)

1. **Depth is a DISPATCHER-READ figure.** The dispatcher reads a cell's depth from its transcript
   BEFORE assigning work and at EVERY review-round gate, and fills the ledger's depth column. A
   cell's self-estimate is not a record.
2. **The check is a PRECONDITION, never a caveat attached to an assignment.** Both bad dispatches
   were the right check in the wrong order.
3. **Any sum over a project's transcripts MUST include `subagents/`.**
4. The `[ctx]` self-report stays for DIRECTORS only, where the hook fires.
5. A stdlib script (`scripts/cell_depth.py`) prints `current / peak / turns` per cell and exits
   non-zero past the cap; briefed to a cell as a mechanical build.

## 5. The measuring pass (read-only; run from `~/.claude/projects/<slug>`)

```python
import json, glob, os
for f in glob.glob("*/subagents/agent-a*.jsonl"):
    peak = cur = n = 0
    for line in open(f, encoding="utf-8", errors="replace"):
        try: d = json.loads(line)
        except Exception: continue
        u = (d.get("message") or {}).get("usage")
        if not u: continue
        n += 1
        cur = (u.get("input_tokens") or 0) + (u.get("cache_read_input_tokens") or 0) \
              + (u.get("cache_creation_input_tokens") or 0)
        peak = max(peak, cur)
    print(f"{peak:>9,} current={cur:>9,} turns={n:<5} {os.path.basename(f)}")
```

-- coa-chess CHARC
