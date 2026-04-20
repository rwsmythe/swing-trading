# Trading Journal Quick Reference Guide

## Trades Sheet Columns

| Column | Field | Source | Notes |
|--------|-------|--------|-------|
| A | Trade # | Manual | Sequential number (1, 2, 3...) |
| B | Ticker | Manual | Stock symbol |
| C | Setup Date | Manual | Date A+ criteria confirmed |
| D | Entry Date | Manual | Date position opened |
| E | Pivot | Chart | Highest high of consolidation range |
| F | Entry Price | Broker | Actual fill price |
| G | Stop | Chart | LOD of breakout day or tight range |
| H | Shares | Calculated | See Position Sizing below |
| I | Position Value | Auto | `=Entry Price × Shares` |
| J | Risk $ | Auto | `=(Entry Price - Stop) × Shares` |
| K | Risk % | Auto | `=(Entry Price - Stop) / Entry Price` |
| L | Partial Exit Date | Manual | Day 4 exit date |
| M | Partial Exit Price | Broker | Actual fill price (50% of shares) |
| N | Partial Shares | Manual | 50% of original shares |
| O | Partial P/L | Auto | `=(Partial Exit Price - Entry Price) × Partial Shares` |
| P | Final Exit Date | Manual | Date of trailing stop exit |
| Q | Final Exit Price | Broker | Actual fill price |
| R | Final Shares | Manual | Remaining 50% of shares |
| S | Final P/L | Auto | `=(Final Exit Price - Entry Price) × Final Shares` |
| T | Total P/L $ | Auto | `=Partial P/L + Final P/L` |
| U | Total P/L % | Auto | `=Total P/L $ / Position Value` |
| V | Rules Followed | Manual | "Yes" or "No" |
| W | Notes | Manual | Lessons, observations, emotions |

---

## Position Sizing Calculation

**Before entering a trade, calculate:**

```
1. Position Size ($) = Account Equity × 0.15
2. Risk per Share ($) = Entry Price - Stop Price
3. Max Shares (risk-based) = (Account Equity × 0.005) / Risk per Share
4. Max Shares (position-based) = Position Size / Entry Price
5. Shares to Buy = MINIMUM of steps 3 and 4
```

**Example:**
```
Account Equity: $1,500
Entry Price: $32.10
Stop Price: $31.15
Risk per Share: $0.95

Position Size: $1,500 × 0.15 = $225
Max Shares (risk): ($1,500 × 0.005) / $0.95 = 7.89 → 7
Max Shares (position): $225 / $32.10 = 7.01 → 7

Shares to Buy: 7
```

---

## Data Sources

| Data | Source |
|------|--------|
| Pivot, Stop levels | TradingView chart |
| Entry/Exit prices | Alpaca order history |
| Account Equity | Alpaca dashboard |
| Shares filled | Alpaca order confirmation |

---

## Exit Rules Reference

| Exit Type | Trigger | Action |
|-----------|---------|--------|
| Initial Stop | Price closes below stop level | Exit 100% next open |
| Partial Profit | Day 4 after entry | Sell 50% at close or next open |
| Trailing Stop | First close below 10-day MA | Exit remaining 50% next open |

---

## Rules Followed Criteria

Mark "Yes" only if ALL were followed:
- [ ] A+ setup criteria met before entry
- [ ] Position size within 15% equity
- [ ] Risk within 0.5% equity
- [ ] Entry triggered by close above pivot
- [ ] Partial exit on Day 4
- [ ] Final exit per trailing stop rule
- [ ] No emotional overrides

Any violation = "No"
