# Qullamaggie MCP — Capabilities Reference

**Purpose:** Persistent capability documentation for the `qullamaggie` MCP server. Future orchestrator and implementer sessions can read this doc to understand what the server provides, how to invoke its tools effectively, and where it fits (or doesn't) in this project's framework.

**Last verified:** 2026-04-26 against server.py at the source repo.

---

## What it is

An MCP server wrapping ~2.5M words of trading commentary from Kristjan Kullamägi (Qullamaggie), extracted from 437 stream sessions (Oct 2019 – Dec 2021). Three-layer access pattern:

1. **Structured indexes** (primary) — pre-extracted rules, setup criteria, ticker references.
2. **Selective transcript loading** (drill-down) — individual videos for exact quotes/context.
3. **Full-text search** (fallback) — keyword search across raw transcripts.

Qullamaggie is a momentum/breakout trader explicitly Minervini-adjacent — VCP-like base patterns, episodic pivots, flag breakouts, gap-and-go plays. Methodologically aligned with the framework references already in `reference/methodology/`, but **not currently a source-of-truth** for this project (see §Governance status below).

---

## Where it lives

| Aspect | Detail |
|---|---|
| Source repo | `C:\Users\rwsmy\qullamaggie-mcp` |
| Upstream | `https://github.com/peterdmv/qullamaggie-mcp` |
| Server entry | `server.py` (FastMCP) |
| Knowledge dir | `knowledge/` (JSON indexes + per-video extractions) |
| Server endpoint | `http://localhost:9871/mcp` (streamable-http) |
| Transport (configured) | streamable-http (registered as `type: "http"` in `~/.claude.json`) |
| Configured scope | user-global in `~/.claude.json` top-level `mcpServers` |
| License | Apache 2.0 |
| Knowledge data dates | Oct 2019 – Dec 2021 (data is ~3-5 years stale relative to the present session — Qullamaggie's 2022+ commentary is not indexed) |

---

## Activation gotchas

- **Server must be running** at `http://localhost:9871/mcp` when a Claude Code session starts. Standard launch: `docker compose up -d` from the source repo.
- **MCP servers are read at session start.** A change to MCP config (or a server starting/stopping) requires a Claude Code session restart to pick up.
- **Tool names appear with prefix `mcp__qullamaggie__`** in the Claude Code tool surface (e.g., `mcp__qullamaggie__analyze_setup`).
- **All tools return JSON strings** (not parsed objects). Output is `json.dumps(..., indent=2)` from server.py — Claude must parse the string when synthesizing.
- **Knowledge data is static.** No live updates; rebuilding requires the source repo's pipeline scripts (`scripts/build_indexes.py`, `scripts/extract_missing.py`).

---

## Tool reference (verified against server.py)

### `query_trading_rules(category?, keyword?)`

Search Qullamaggie's trading rules by category, keyword, or both.

- **category** (optional): `risk_management`, `position_sizing`, `entry`, `exit`, `screening`, `psychology`, `market_regime`. Omit for all categories.
- **keyword** (optional): substring match against `rule_text` (case-insensitive).
- **Returns:** top 50 matching rules sorted by frequency DESC. Each rule has `category`, `rule_text`, `frequency`, `source_videos`, `tags`.
- **Cap:** 50 results. If a query is broader, frequency-rank wins — popular rules surface, rare ones drop.
- **Use when:** You want general principles, not setup-specific criteria. Frequency is a confidence proxy (oft-repeated rules are higher conviction).

### `get_setup_criteria(setup_type)`

Get Qullamaggie's criteria for one named setup pattern.

- **setup_type** (required): one of `episodic_pivot`, `breakout`, `power_earnings_gap`, `flag_pattern`, `parabolic_short`, `gap_and_go`, `base_breakout`, `ipo_breakout`. Returns an `available_types` list on miss.
- **Returns:** `{setup: {description, keywords, ...}, quantitative_criteria: [{metric, threshold, ...}]}`.
- **Use when:** You have a candidate already classified into one of the 8 first-class setup buckets and want the entry/exit/threshold detail.
- **Note:** The setup taxonomy here is broader than this project's current `TT/VCP/A+` taxonomy. Cross-walking the two would require operator decision per V2.1 §VII.F.

### `lookup_ticker(ticker)`

Find every session where Qullamaggie discussed a specific ticker.

- **ticker** (required): symbol, case-insensitive. Falls back to substring partial-match if exact lookup misses.
- **Returns:** `{ticker, count, mentions: [{video_id, video_date, setup_type, direction, outcome, ...}]}`.
- **Use when:** Researching whether Qullamaggie has commented on a ticker the operator is considering, or pulling historical analog setups for current candidates.
- **Coverage:** 1,214 distinct tickers in the index. Coverage skewed toward 2019-2021 momentum names; modern leaders may be absent.

### `search_transcripts(query, max_results?)`

Full-text keyword search across all 437 transcripts.

- **query** (required): one or more space-separated words. **AND logic** — all words must appear in the transcript for it to match.
- **max_results** (default 10, hard cap 25): max excerpts returned.
- **Returns:** `{query, count, results: [{video_id, video_date, video_title, youtube_url, excerpt (~500 chars centered on first match), word_count}]}`.
- **Use when:** Structured indexes don't cover what you need. This is the fallback layer.
- **Limitation:** Brute-force linear scan; AND-logic is strict (a phrase like "tight base" requires both words, doesn't find synonyms or close variants). Quote ordering is not preserved — words can appear anywhere in the transcript.

### `load_transcript(video_id)`

Load the full raw text of a specific video.

- **video_id** (required): 1-indexed integer. **Valid range: 1-437.** (Server docstring says "1-420" but the actual `transcripts.json` has 437 entries; 361-437 are stream-only recaps from fewmoredays.io, no YouTube URL.)
- **Returns:** `{video_id, recap_num, video_date, video_title, source, youtube_url, source_file, word_count, transcript}`.
- **Use when:** Need exact quotes or full context after `search_transcripts` or `lookup_ticker` surfaced a relevant video.
- **Cost:** Each transcript is ~4,000–12,000 words. Pulling several blows context budget — use sparingly.

### `get_market_regime_rules(regime?)`

Filter rules by market-condition keyword.

- **regime** (optional): suggested values `bull`, `bear`, `choppy`, `rotation`, `low_volatility`. **Not enforced as enum** — the server keyword-matches the regime string against `rule_text` and `tags`, so any string works (e.g., `"correction"` would also match anything mentioning correction).
- **Returns:** all `category=market_regime` rules, optionally filtered by keyword. Not capped at 50 like `query_trading_rules`.
- **Use when:** Surfacing regime-context rules during operator's market-condition analysis (e.g., post-correction re-entry rules, parabolic-blowoff exits).

### `analyze_setup(ticker, price_action_summary)`

Cross-references a free-text price-action description against the full knowledge base.

- **ticker** (required): symbol.
- **price_action_summary** (required): natural-language description.
- **Returns:** `{ticker, price_action, matching_setups, applicable_rules (top 20 by frequency), historical_mentions (top 10), analysis_sources}`.
- **Matching logic:** PURELY keyword-overlap. Each setup's `keywords` list is checked against the lowercased price_action_summary string. **No semantic understanding** — "gapping up on earnings" matches `power_earnings_gap` because the words "gap" and "earnings" appear, not because the description means the same thing. Synonyms ("breakaway", "breakout") may or may not register depending on indexed keywords.
- **Use when:** First-pass triage on a candidate before drilling into specific tools. Treat the output as a set of pointers to investigate, not a verdict.
- **Watch out for:** false positives from incidental word overlap (e.g., the word "base" in a non-base context will pull base_breakout matches).

---

## Knowledge base inventory

| Index file | Contents | Size |
|---|---|---|
| `rules.json` | 3,980 deduplicated rules across 7 categories, frequency-ranked | 1.4 MB |
| `setups.json` | 84 setup types (8 first-class with full criteria) | 228 KB |
| `criteria.json` | 193 quantitative thresholds (dollar volume, ADR%, float, etc.) | 88 KB |
| `ticker_index.json` | 1,214 tickers with per-video context | 2.0 MB |
| `topic_index.json` | 2,419 topics → source video IDs | 124 KB |
| `transcripts.json` | Full raw text for 437 sessions (~2.5M words) | 11.5 MB |
| `extracted/video_*.json` | Per-video structured extractions (one file per video) | 437 files |

**Categories** (rules.json): `entry`, `exit`, `risk_management`, `position_sizing`, `psychology`, `screening`, `market_regime`.

**First-class setups** (setups.json, with full criteria): `episodic_pivot`, `breakout`, `power_earnings_gap`, `flag_pattern`, `parabolic_short`, `gap_and_go`, `base_breakout`, `ipo_breakout`. The full taxonomy is broader (84 setup names) but most don't have full criteria entries.

---

## Recommended use patterns (for this project)

### When to consider invoking

- **Operator chart review.** Operator describes a candidate's price action; orchestrator runs `analyze_setup` for first-pass cross-reference, then drills down with `get_setup_criteria` or `query_trading_rules` if a setup matches.
- **Hypothesis-label vocabulary discussion.** Hypothesis labels are currently free-text. If operator wants to standardize, the Qullamaggie setup taxonomy is a candidate prefix vocabulary.
- **Rule-of-thumb lookup during conversation.** Operator asks "what does Qullamaggie say about [position sizing / stops / chasing]?" — `query_trading_rules` is the right tool.
- **Historical analog research.** Looking at a current candidate; want to see if Qullamaggie traded similar names in 2019-2021. `lookup_ticker` first; `search_transcripts` if the ticker isn't indexed.

### When NOT to invoke

- **Production criteria changes.** The server is a reference, not a source-of-truth. Any change to `swing/evaluation/`, `swing/recommendations/`, etc. driven by Qullamaggie's framework would require operator decision under V2.1 §VII.F (source-of-truth correction protocol). Don't sneak the framework into production code via implementer briefs.
- **Live trading decisions.** Data ends Dec 2021; market regime, leadership, sector rotation have all shifted. Treat as historical reference, not current commentary.
- **Statistical claims.** This is one trader's commentary; frequency-ranked rules are conviction proxies, not validated edge measurements. The research branch (`research/`) is where validation work lives.

### Suggested invocation patterns

**Single-candidate analysis:**
```
1. analyze_setup(ticker, "...price action description...")
2. If matching_setups returned: get_setup_criteria(top match)
3. If ticker has historical mentions: lookup_ticker(ticker)
4. Optional: load_transcript(top mention's video_id) for exact quotes
```

**Concept lookup:**
```
1. query_trading_rules(category=relevant, keyword=concept)
2. If frequency-1-2 results aren't enough, search_transcripts(query=concept, max_results=10)
3. If a video stands out, load_transcript(video_id)
```

**Regime context:**
```
1. get_market_regime_rules(regime=current_condition)
2. Cross-reference with operator's current market read
```

---

## Governance status

The qullamaggie MCP server is currently a **reference-only resource**. It does not feed into:

- Production code in `swing/` (criteria, recommendations, advisories, etc.).
- Methodology references in `reference/methodology/` (which are source-of-truth and require V2.1 §VII.F protocol to amend).
- Research-branch studies (which use `reference/methodology/` plus operator-defined hypotheses; Qullamaggie material is not currently a research input).

**To promote any aspect to source-of-truth status** would require:
1. Operator decision (operator-drives discipline).
2. V2.1 §VII.F correction protocol if the change affects production criteria.
3. Explicit method-record entry if the change is research-input.

Until then: orchestrator and implementers may consult it during conversation; it does not bind code or studies.

---

## Maintenance notes

- **Server upgrades** happen via `git pull` in the source repo, then `docker compose up -d --build` (or restart of the running daemon).
- **Knowledge base rebuild** requires the pipeline scripts in the source repo's `scripts/` directory; not part of normal usage.
- **If the server stops responding:** check `docker compose ps` (or whatever launch method is in use), then `docker compose logs qullamaggie-mcp`. After restart, the next Claude Code session start will pick it up automatically.
- **If `claude mcp list` shows "Failed to connect":** server is not running at `http://localhost:9871/mcp`. Start it; relaunch session.

---

## Cross-references

- This doc indexed in `docs/orchestrator-context.md` §"Key file locations" and §"External tools available".
- Memory entry: `reference_qullamaggie_mcp.md` (cross-session pointer).
- Source repo: `C:\Users\rwsmy\qullamaggie-mcp\` — has its own `CLAUDE.md` and `README.md`.
