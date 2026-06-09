# Minervini primary-base recall - summary

NOTE: n~3 proof-of-concept. Raw fractions are PRIMARY; Wilson + bootstrap are
MECHANICAL/EXPLORATORY at this n, NOT evidence of stable performance. Precision is a
same-ticker temporal-specificity contrast, NOT a population base rate.

## Recall (sub-floor evaluable {twosmw-fig11-1-amzn, ttlc-fig10-1-body, twosmw-fig11-6-dks})
sub-floor sweep recall (RAW): 3/3 (fired: twosmw-fig11-1-amzn;ttlc-fig10-1-body;twosmw-fig11-6-dks; missed: -)
  Wilson 95pct (MECHANICAL at n=3): [0.438, 1.000]
  ticker-clustered bootstrap 95pct (EXPLORATORY): [1.000, 1.000]
day-precision single-session recall (RAW, BODY-only n=1): 1/1 -- single yes/no, NO interval
sweep first-rejecting-criterion histogram: {}

## Positive control (YHOO -- sufficient-history documented primary base)
- twosmw-fig11-3-yhoo: window-sweep fired=False (first_rejecting_criterion=depth)

## Below-minimum (reported, NOT a screen miss -- below Minervini's >=2-month floor)
- twosmw-fig11-7-jnpr: history-excluded (25 bars < MIN_HISTORY_BARS)

## Data unavailable (no Tiingo archive; NOT a screen miss, NOT below-minimum)
- (none)

## Precision (same-ticker young-window control; single-session per-anchor PRIMARY)
- twosmw-fig11-1-amzn (sub_floor): control single-session per-anchor fire (PRIMARY)=0.000; window best-of (SEPARATE)=0.000; k=5, eligible_before_sampling=309; exemplar single=None window=True
- ttlc-fig10-1-body (sub_floor): control single-session per-anchor fire (PRIMARY)=0.000; window best-of (SEPARATE)=0.000; k=5, eligible_before_sampling=328; exemplar single=True window=True
- twosmw-fig11-6-dks (sub_floor): control single-session per-anchor fire (PRIMARY)=0.000; window best-of (SEPARATE)=0.000; k=5, eligible_before_sampling=270; exemplar single=None window=True
- twosmw-fig11-3-yhoo (positive_control): control single-session per-anchor fire (PRIMARY)=0.000; window best-of (SEPARATE)=0.000; k=5, eligible_before_sampling=226; exemplar single=False window=False

