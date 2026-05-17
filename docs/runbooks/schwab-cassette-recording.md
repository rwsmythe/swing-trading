# Schwab cassette recording — operator runbook

> **Scope:** Sub-bundle 1 T-1.0 + Sub-bundle 1 T-1.13 (cassette-driven E2E
> integration tests for the V2 Schwab mapper widening). Operator-paired
> recording session is a **HARD PREREQ** for the rest of Sub-bundle 1
> implementation (T-1.1..T-1.13) per spec §6.5 OQ-E LOCK + brief §0.7
> mid-dispatch pause.

This runbook supersedes the CLAUDE.md gotcha "Schwab cassette runbook is V2
PLANNED — V1 ships mock-based tests only" — Sub-bundle 1 shifts the bar to
**cassette-required**.

---

## §1 Why cassettes

The V1 Schwab integration arc (Phase 11) deliberately shipped with mock-based
tests only. Sub-bundle 1 introduces execution-grain widening that depends on
the SHAPE of `orderActivityCollection[].executionLegs[]` from real Schwab
responses — see spec §10 worked examples (CVGI fill_id=9 + LION fill_id=15).
Recording 4 real order types under sanitization gives T-1.13 byte-for-byte
fixtures that let the mapper extension, the comparator switch, and the
classifier Shape C predicate all be verified end-to-end against production
data without hitting the Schwab API on every test run.

The cassettes are recorded ONCE per Sub-bundle 1 dispatch (refresh if Schwab
upstream changes the response shape; staleness recovery in §4 below).

---

## §2 Required order-type coverage

Per spec §6.5 OQ-E LOCK + plan §F.1, 4 order types are REQUIRED. A 5th is
optional stretch.

| # | Order type | Cassette filename | Why |
|---|---|---|---|
| 1 | LIMIT BUY (filled) | `test_e2e_limit_buy_no_false_positive.yaml` | Operator predominant entry; CVGI family |
| 2 | LIMIT SELL (filled) | `test_e2e_limit_sell_no_false_positive.yaml` | Operator predominant exit; LION family |
| 3 | STOP FIRED (filled from STOP order) | `test_e2e_stop_fired_no_false_positive.yaml` | Tests OQ-D Path A FIRED-stop discipline |
| 4 | MARKET BUY (filled) | `test_e2e_market_buy_no_false_positive.yaml` | Verifies executionLegs surface for MKT (rare) |
| 5 | STOP_LIMIT FIRED (OPTIONAL stretch) | `test_e2e_stop_limit_fired_no_false_positive.yaml` | Dual-tier price-vs-stop verification |

If you have no recent STOP_LIMIT fill within the lookback window (default 30
days), skip the 5th cassette without blocking — T-1.13 guards the stretch
test with `pytest.mark.skipif(not cassette.exists())`.

Cassettes land in `tests/integrations/cassettes/schwab/`.

---

## §3 Recording session — operator workflow

**Pre-conditions:**

1. **Valid Schwab refresh-token.** Sub-bundle 1 dispatch coincides with the
   weekly 7-day OAuth window (production tokens DB expires ~2026-05-22). If
   `swing schwab status --environment production` does NOT report `LIVE`,
   re-auth via the `/schwab/setup` web form OR `swing schwab setup` CLI
   first. The CLI is T-A.2 self-healing so the recovery is a single
   command. (Refer to CLAUDE.md gotcha "Schwab OAuth web setup flow" for
   the web path.)
2. **Recent historical fills** of the 4 REQUIRED order types within the
   `--days` lookback window (default 30). The recording script greps
   `account_orders` by `status='FILLED'` + filters in-Python; if the script
   reports `FAILED: cassette ... contains no <type> orders with
   executionLegs[]`, either widen the window (e.g., `--days 60`) or place
   the missing order in TOS / Schwab Mobile + wait for fill.
3. **`pytest-recording` (vcrpy) dev dep installed** (already a transitive
   dep of the existing Phase 11 cassette tests — confirm via `python -c
   "import vcr"` if uncertain).
4. **You are on the Sub-bundle 1 worktree branch** —
   `cd .worktrees/schwab-mapper-bundle-1` per dispatch-brief §1.1.
5. **Credentials cascade resolves** — if env vars `SCHWAB_CLIENT_ID` +
   `SCHWAB_CLIENT_SECRET` are not set in the shell, the recording script
   falls through to `~/swing-data/user-config.toml`
   `[integrations.schwab].client_id` + `.client_secret`. The script DOES
   NOT prompt (it passes `allow_prompt=False`) per Phase 12 Sub-bundle B
   discipline — set creds via env var OR user-config.toml BEFORE running.

**Recording commands:**

```powershell
# From the Sub-bundle 1 worktree, with creds resolved as above:

# Record all 4 REQUIRED order types in one invocation (default --days 30):
python scripts/record_schwab_cassettes.py --environment production

# OR record a subset (per-order-type recovery after a single-type failure):
python scripts/record_schwab_cassettes.py --environment production \
    --order-types stop_fired

# OR widen the lookback when a recent fill is missing:
python scripts/record_schwab_cassettes.py --environment production \
    --order-types stop_fired --days 60

# OR include the stretch STOP_LIMIT FIRED cassette:
python scripts/record_schwab_cassettes.py --environment production \
    --order-types limit_buy,limit_sell,stop_fired,market_buy,stop_limit_fired
```

The script's `--help` flag documents the full surface verbatim.

**What the script does for each order_type:**

1. Opens `vcr.use_cassette(<path>, record_mode='new_episodes', ...)` with
   the shared sanitization filter dict imported from
   `tests/conftest.py:vcr_config`.
2. Invokes `schwabdev.Client(...).account_orders(maxResults=200,
   fromEnteredTime=..., toEnteredTime=..., status='FILLED')` (camelCase
   kwargs per CLAUDE.md gotcha).
3. **Post-record validation gate** (Codex R4 M#2): re-parses the captured
   response + asserts at least ONE order matches the requested order_type
   AND carries non-empty `orderActivityCollection[].executionLegs[]`. If
   the gate fails, the cassette file is **DELETED** + the script exits
   non-zero with an operator-actionable remediation message.
4. **Sentinel-leak audit** (plan §G.4 + AC#7 bullet 8): scans the freshly
   written cassette bytes for unsanitized accountNumber / accountHash /
   access_token / refresh_token / id_token / code / client_id /
   client_secret / bearerToken JSON-value substrings + URI accountHash path
   segments + bare base64 token-shape. If any pattern matches, the
   cassette is **DELETED** + the script exits non-zero. Expected matches
   in shipped cassettes are ONLY the sanitization placeholders
   (`<account>`, `<HASHED_REDACTED>`, `<REDACTED>`, `<hex-token>`,
   `<base64-token>`).

**Operator verification:**

After the script reports `OK:` for each order type:

```powershell
# Visual diff each cassette for any sensitive substring you'd recognize
# (e.g., the trailing-4-digits of your accountNumber, your accountHash
# prefix, your email if Schwab embeds it anywhere):
git diff tests/integrations/cassettes/schwab/

# Confirm only sanitized placeholders surface for sensitive fields:
grep -E '"accountNumber"|"accountHash"|"access_token"|"refresh_token"' \
    tests/integrations/cassettes/schwab/*.yaml
# Expected: every value is "<REDACTED>" or "<HASHED_REDACTED>".

# Confirm no raw accountHash in URL paths:
grep -E '/accounts/[^<][^/?#]+' tests/integrations/cassettes/schwab/*.yaml
# Expected: only "/accounts/<account>/..." matches (or zero output).
```

If the visual diff surfaces ANY unsanitized substring the audit missed,
report it as a deviation per brief §0.6 — the sanitization filter spec at
`tests/conftest.py:vcr_config` + the `_LEAK_PATTERNS` catalogue at
`scripts/record_schwab_cassettes.py` need extension before commit.

**Commit cassettes to the worktree branch:**

```powershell
cd .worktrees/schwab-mapper-bundle-1
git add tests/integrations/cassettes/schwab/
git status   # confirm only the 4-5 YAML files staged
git commit -m "test(schwab-cassette): record 4 order types for Sub-bundle 1"
```

**Signal resume** to the implementer subagent (plain-chat "resume" or
equivalent). Implementation continues with T-1.1..T-1.13.

---

## §4 Staleness recovery runbook

Schwab API may drift over time. Symptoms of cassette staleness:

1. T-1.13 test fails with `KeyError` / `AttributeError` / `ValueError`
   on a previously-mapped field.
2. T-1.13 test fails because mapper raises `SchwabSchemaParityError` on
   replay.
3. T-1.13 test fails because the dataclass `__post_init__` validator
   rejects a leg shape that schwabdev returns.

**Recovery:**

1. **Refresh tokens if expired:** `swing schwab logout && swing schwab
   setup` (or web `/schwab/setup`).
2. **Re-record cassettes** per §3 above. The recording script overwrites
   existing cassette files in-place (vcrpy `record_mode='new_episodes'`
   appends; you may delete the old cassette first if you want a clean
   recording).
3. **Operator diffs OLD vs NEW** sanitized cassette text — non-redacted
   fields surface the actual shape change.
4. **Breaking change → follow-up dispatch.** If the mapper / comparator /
   classifier needs to handle a new shape, surface to orchestrator as
   deviation. Do NOT silently widen the mapper inside this T-1.13 fix
   without an explicit dispatch authorization (spec §1.3 escalation rule).

---

## §5 Production-write classifier soft-block awareness

The recording script writes to `schwab_api_calls` audit rows when it
invokes the Schwab API. Per Phase 12 Sub-sub-bundle C.D NEW lesson #2,
Claude Code's production-write classifier may soft-block a PowerShell
invocation that targets `production` environment **per invocation** even
after AskUserQuestion authorization. If the script is being invoked from
within a Claude Code session (orchestrator-driven or implementer-driven),
the operator pre-authorizes via plain-chat "yes" each time.

For interactive operator workflow (no Claude in the loop), this caveat
does not apply.

---

## §6 What gets shipped

After §3 recording session completes, the worktree branch
`schwab-mapper-bundle-1` carries:

- `tests/integrations/cassettes/schwab/test_e2e_limit_buy_no_false_positive.yaml`
- `tests/integrations/cassettes/schwab/test_e2e_limit_sell_no_false_positive.yaml`
- `tests/integrations/cassettes/schwab/test_e2e_stop_fired_no_false_positive.yaml`
- `tests/integrations/cassettes/schwab/test_e2e_market_buy_no_false_positive.yaml`
- (Optional) `tests/integrations/cassettes/schwab/test_e2e_stop_limit_fired_no_false_positive.yaml`

These are checked into the worktree branch. The Sub-bundle 1 integration
merge (orchestrator-owned per brief §1.4) folds them into `main`.

---

## §7 Cross-references

- **Spec:** `docs/superpowers/specs/2026-05-17-schwab-mapper-execution-grain-widening-design.md` §6.5 OQ-E LOCK + §10 worked examples.
- **Plan:** `docs/superpowers/plans/2026-05-17-schwab-mapper-execution-grain-widening-plan.md` §F (this runbook) + §G (acceptance criteria) + §A.1.0 (T-1.0 task) + §A.1.13 (T-1.13 consumer).
- **Brief:** `docs/post-phase12-schwab-mapper-bundle-1-execution-grain-widening-executing-plans-dispatch-brief.md` §0.7 (mid-dispatch operator pause).
- **CLAUDE.md gotchas:** "Schwab cassette runbook is V2 PLANNED" (this runbook supersedes); "Schwab OAuth web setup flow" (re-auth path); "schwabdev camelCase kwarg discipline" (the script honors); "schwabdev silent-failure-mode discipline" (`construct_authenticated_client` raises on silent failure).
- **Sanitization filter source:** `tests/conftest.py:vcr_config` (single source of truth; recording script imports the same dict).
- **Recording script:** `scripts/record_schwab_cassettes.py`.
- **Tests for the recording script:** `tests/integrations/test_record_schwab_cassettes_script.py`.
