# Schwab endpoint-set diff: schwabdev 2.5.1 -> 3.0.5 (L2 re-anchor proof)

**Purpose.** This artifact is the evidence backing the FIRST-EVER L2-LOCK baseline
re-anchor (Phase 15, schwabdev v3 upgrade). The L2 lock's binding SPIRIT is **"zero new
Schwab REST endpoints / market-data sources."** The v3 migration churns docstrings,
comments, and one method name that embed `schwabdev.Client.` (so the source-grep baseline
shifts), but it adds **ZERO new endpoints**. This diff enumerates the complete pre/post
Schwab + OAuth endpoint set to prove that, and is the operator-facing input to the
GATE A (L2 sign-off) checkpoint (plan §H.1 / OQ-4).

**Method.** Endpoint labels are the `schwab_api_calls.endpoint` audit values emitted by the
production wrappers (`swing/integrations/schwab/trader.py`, `marketdata.py`, `auth.py`),
cross-checked against the manual OAuth POST URLs in `auth.py`. The Trader / Market-Data
REST paths themselves are issued by schwabdev internally (we call its methods); the OAuth
URLs are ours.

## Endpoint set (pre = 2.5.1, post = 3.0.5)

| # | Audit label | REST path / call | schwabdev method | 2.5.1 | 3.0.5 | New? |
|---|-------------|------------------|------------------|-------|-------|------|
| 1 | `accounts.linked` | `GET /trader/v1/accounts/accountNumbers` | `account_linked()` -> `linked_accounts()` | yes | yes | **no** (method renamed; SAME path) |
| 2 | `accounts.details` | `GET /trader/v1/accounts/{hash}` | `account_details(...)` | yes | yes | no |
| 3 | `accounts.orders.list` | `GET /trader/v1/accounts/{hash}/orders` | `account_orders(...)` | yes | yes | no |
| 4 | `accounts.transactions.list` | `GET /trader/v1/accounts/{hash}/transactions` | `transactions(...)` | yes | yes | no |
| 5 | `marketdata.quotes` | `GET /marketdata/v1/quotes` | `quotes(...)` | yes | yes | no |
| 6 | `marketdata.pricehistory` | `GET /marketdata/v1/pricehistory` | `price_history(...)` | yes | yes | no |
| 7 | `oauth.code_exchange` | `POST https://api.schwabapi.com/v1/oauth/token` (manual) | n/a (our request) | yes | yes | no |
| 8 | `oauth.refresh` | `update_tokens(force_access_token=True)` -> `POST /v1/oauth/token` | `update_tokens(...)` | yes | yes | no |
| 9 | `oauth.revoke` | `POST https://api.schwabapi.com/v1/oauth/revoke` (manual) | n/a (our request) | yes | yes | no |

## What the migration actually changed (and why the source-grep baseline shifts)

1. **One method rename, SAME endpoint:** `account_linked()` -> `linked_accounts()` (row 1).
   The REST path `/trader/v1/accounts/accountNumbers` is unchanged. Not a new endpoint.
2. **Token storage:** the tokens are now persisted in a schwabdev-internal SQLite DB
   (`tokens_db=`) instead of the 2.x JSON file (`tokens_file=`). This is an **on-disk
   storage** change with **no API call** and no swing-DB schema change (L3).
3. **Docstring / comment / type-annotation prose** embedding the literal
   `schwabdev.Client(` signature (the `tokens_file=` kwarg, the `account_linked` reference)
   was rewritten to the v3 form. These are PROSE lines, not new call sites -- but they
   shift the `schwabdev.Client.` source-grep baseline, which is why the L2 lock must
   re-anchor (the grep counts text occurrences, not endpoints).
4. **Deletions only:** the P14.N7 daemon-checker wrapper + the F-1 topbar badge were
   removed (no endpoint impact).

## Conclusion

**ZERO new Schwab REST endpoints or market-data sources.** The L2 lock SPIRIT is preserved.
The baseline re-anchor reflects only prose/rename churn, not surface growth. Per the GATE A
escalation rule: if a future diff ever shows a genuinely-new endpoint, STOP + escalate (it
does not here).

Operator sign-off at the executing-plans GATE A authorizes setting
`L2_LOCK_BASELINE_SHA` to the real pre-merge HEAD in
`tests/integration/test_l2_lock_source_grep.py`.
