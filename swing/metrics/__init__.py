"""Phase 10 metrics dashboard utility module.

Public surface:
- honesty.py: spec §5 low-sample-size honesty policy.
- policy.py: risk_policy LIVE vs AT-TRADE-TIME read split (spec §0.5 §11.1).
- equity_resolver.py: live_capital_denominator_dollars resolver (spec §0.5 §11.4).
- cohort.py: per-hypothesis-cohort filter + aggregation.
- rolling.py: rolling-N window helper (spec §3.8 Class D).
- funnel.py: identification-vs-trade-funnel helper.
- process.py: §3.1 trade-process metric computations.
- capital.py: §3.4 capital-friction metric computations.
- maturity.py: §3.5 maturity-stage metric computations.
- tier.py: §3.3 + §3.7 tier-comparison + deviation-outcome.
- process_grade_trend.py: §3.8 rolling-grade trend.
- discrepancies.py: §0.5 §11.2(a) reconciliation badge count.
"""
