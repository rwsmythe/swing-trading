# Swing Trading Priority Terms Reference

**Phase 0.1 Reference Document**  
**Purpose**: Quick reference for essential trading terminology

---

## Table of Contents

1. [ADR (Average Daily Range)](#1-adr-average-daily-range)
2. [LOD (Low of Day)](#2-lod-low-of-day)
3. [RS (Relative Strength)](#3-rs-relative-strength)
4. [EP (Episodic Pivot)](#4-ep-episodic-pivot)
5. [Consolidation](#5-consolidation)
6. [Pivot](#6-pivot)
7. [Tightness](#7-tightness)
8. [Summary Table](#summary-table)

---

## 1. ADR (Average Daily Range)

### Definition
The average percentage a stock moves from its daily low to its daily high, calculated over a specified period (typically 14 or 20 days).

### Formula
```
Daily Range = (High - Low) / Low × 100%

ADR = Average of Daily Range over N days
```

### Example Calculation (5-day simplified)

| Day | Low | High | Daily Range |
|-----|-----|------|-------------|
| 1 | $48.00 | $51.00 | 6.25% |
| 2 | $49.50 | $52.00 | 5.05% |
| 3 | $50.00 | $53.50 | 7.00% |
| 4 | $51.00 | $53.00 | 3.92% |
| 5 | $52.00 | $55.00 | 5.77% |

```
ADR = (6.25 + 5.05 + 7.00 + 3.92 + 5.77) / 5 = 5.6%
```

### Why It Matters
- **High ADR (>4-5%)** = More profit potential per swing, but also more volatility
- **Low ADR (<2%)** = Stock moves slowly; harder to generate meaningful returns
- Used in the "tightness" calculation: tight day = daily range ≤ 2/3 × ADR

### Trading Interpretation
- A stock with 5% ADR can reasonably move 5% in a day
- If your stop is 3% below entry, a 5% ADR stock could hit that stop on normal volatility
- Framework filters for ADR >4-5% to ensure stocks have enough movement potential

### Where to Find It
- TradingView: Add "Average True Range" indicator (shows $ value; divide by price for %)
- Finviz: Not directly shown; calculate manually or use screener proxies
- Some platforms have ADR% as a built-in column

---

## 2. LOD (Low of Day)

### Definition
The lowest price a stock traded at during a specific trading session.

### Example
```
Stock XYZ on March 15:
  Open:  $25.00
  High:  $26.50
  Low:   $24.75  ← This is the LOD
  Close: $26.25
```

### Why It Matters
- **Primary use**: Initial stop-loss placement
- If you buy a breakout and the stock drops below the LOD of your entry day, the breakout has failed
- LOD represents the point where buyers stepped in; breaking it suggests that support failed

### Trading Application
```
Entry: $26.50 (breakout)
LOD:   $24.75
Stop:  $24.70 (just below LOD)

Risk per share = $26.50 - $24.70 = $1.80
Risk % = $1.80 / $26.50 = 6.8%
```

### Critical Point: Why Tightness Matters
If a stock consolidates in a tight range:
- LOD of the tight day might be $26.00 instead of $24.75
- Risk becomes $26.50 - $25.95 = $0.55 (2.1%)
- Much smaller risk for the same entry

### Related Terms
- **HOD (High of Day)**: Highest price of the session
- **PDH (Previous Day High)**: Often used as resistance/breakout level
- **PDL (Previous Day Low)**: Often used as support level

---

## 3. RS (Relative Strength)

### Definition
A measure of how a stock is performing compared to the overall market or its peers over a specified period.

> **Important**: This is NOT the same as RSI (Relative Strength Index), which is a momentum oscillator ranging 0-100. RS compares performance; RSI measures overbought/oversold conditions.

### Conceptual Formula
```
RS Rating = Stock's % gain over period / Market's % gain over period
```

In practice, services like IBD (Investor's Business Daily) calculate a 1-99 RS Rating comparing a stock to all other stocks over the past 12 months.

### Example

| | 6-Month Performance |
|----------|---------------------|
| Stock A | +45% |
| Stock B | +15% |
| S&P 500 | +10% |

- **Stock A**: Strong RS (outperforming market significantly)
- **Stock B**: Moderate RS (slightly outperforming)

### Visual RS Check (No Calculation Needed)

Compare two charts over the same timeframe:
- Stock pulling back less than the index during market dips = **High RS**
- Stock making new highs while index is flat = **High RS**
- Stock declining while market rises = **Low RS (avoid)**

### Why It Matters
- High RS stocks are "leaders" — institutional money is flowing in
- Framework requires RS > 85-90 (top 10-15% of all stocks)
- Leaders tend to lead both up AND down; you want to be in them during uptrends

### Where to Find It
- **Finviz**: Use performance filters (% change over weeks/months)
- **TradingView**: Use "Compare" feature to overlay stock vs SPY
- **IBD/MarketSmith**: Proprietary RS Rating (paid service)
- **Manual**: Compare 3-month and 6-month % gains vs. SPY/QQQ

---

## 4. EP (Episodic Pivot)

### Definition
A significant price gap (usually upward) driven by a fundamental catalyst—typically an earnings surprise or major news—occurring on extremely high volume. Often marks the beginning of a major trend move.

### Characteristics
- Gap up >10-15% at market open
- Volume on gap day = multiple of average daily volume (often 5-10x or more)
- Usually breaks out of a prior base or trading range
- Driven by fundamental surprise (not just technical)

### Example
```
Stock XYZ Reports Earnings:
  Prior Close: $50.00
  Expected EPS: $0.50
  Actual EPS: $0.85 (70% beat)
  
Next Day:
  Open:   $62.00 (24% gap up)
  Volume: 15 million shares (average is 2 million = 7.5x)
  High:   $68.00
  Close:  $65.00
```

This is an EP. The fundamental surprise (earnings beat) caused institutional buying to flood in.

### EP Criteria Checklist
- [ ] Gap >10% on open
- [ ] Volume >3-5x average (ideally higher)
- [ ] Fundamental catalyst (earnings, FDA approval, major contract, etc.)
- [ ] Breaking out of prior consolidation/base
- [ ] In a leading sector (bonus)

### Why It Matters
- EPs can be the start of 50-200%+ moves over weeks/months
- The framework calls this potentially "the best swing trading setup"
- Entry is typically via ORB (Opening Range Breakout) — buying when price breaks above the first 5-15 minutes' high

### For Beginners
- EPs are harder to trade with an EOD approach (they require early entry)
- Focus on Breakouts from Tight Consolidation first
- Study EPs passively; add to your arsenal later

---

## 5. Consolidation

### Definition
A period after a price trend where the stock moves sideways or pulls back slightly, characterized by reduced volatility and volume. The stock is "resting" or "digesting" gains before potentially continuing its trend.

### Visual Representation
```
UPTREND:                    CONSOLIDATION:              BREAKOUT:
                                  ___________
        /                        /           \               /
       /                        |             |             /
      /                         |_____________|            /
     /                                                    /
    /                                                    /
```

### Common Consolidation Shapes

| Pattern | Description | Visual |
|---------|-------------|--------|
| **Flag** | Slight downward drift after uptrend | Parallel downward-sloping lines |
| **Pennant** | Converging trendlines | Triangle shape |
| **Tight Channel** | Horizontal, narrow range | Rectangle |
| **High Tight Flag** | Very tight after explosive move | Small rectangle after steep rise |

### Example
```
Week 1-3: Stock moves from $20 → $35 (uptrend / "the pole")
Week 4-5: Stock trades between $33-$36 (consolidation / "the flag")
          Volume decreases during this range
          Price hovers near the rising 20-day MA
Week 6:   Stock breaks above $36 on increased volume (breakout)
```

### Why It Matters
- Consolidations are where setups form
- The breakout from consolidation is your entry trigger
- Quality of consolidation determines setup quality:
  - Tightness
  - Volume contraction
  - MA support
  - Clear pivot level

### What You're Looking For
1. Prior strong uptrend (the "pole")
2. Sideways/slight pullback (the "flag" or consolidation)
3. Decreasing volume during consolidation
4. Price near rising 10 or 20-day MA
5. Tightening range in final days

---

## 6. Pivot

### Definition
A specific price level that, if broken, triggers an action (entry or exit). The pivot is the "line in the sand" — an objective decision point.

### Types of Pivots

| Type | Definition | Action When Broken |
|------|------------|-------------------|
| **Entry Pivot** | High of consolidation range | Enter long position |
| **Stop Pivot** | Low of consolidation / LOD | Exit position (stop-loss) |

### Example
```
Consolidation range: $48.00 - $52.00

Entry Pivot: $52.00 (or $52.10 to confirm break)
Stop Pivot:  $47.90 (just below consolidation low)

If price closes above $52.00 → Entry triggered
If price drops below $47.90 → Exit (stop triggered)
```

### Visual Representation
```
         Entry Pivot ($52.00)
         ════════════════════════
        |                        |
        |     Consolidation      |
        |   Price bounces here   |
        |                        |
         ════════════════════════
         Stop Pivot ($48.00)
```

### Why It Matters
- Provides objective, unambiguous entry/exit points
- Removes emotion from decision-making
- A clear pivot = a tradeable setup
- No clear pivot = no trade

### Identifying Pivots
1. Draw horizontal line at the highest high of the tight consolidation
2. This becomes your entry trigger
3. The more times price has touched this level without breaking, the more significant the breakout
4. Stop pivot is typically the low of the tightest candles or consolidation low

### Pivot Quality Indicators
- **Strong Pivot**: Multiple touches, clear horizontal level, aligns with round number
- **Weak Pivot**: Sloping, unclear, only touched once

---

## 7. Tightness

### Definition
A period of exceptionally low volatility within a consolidation, where daily price ranges become significantly smaller than average. Indicates the stock is "coiling" before a potential explosive move.

### Quantitative Definition (Framework Standard)
```
Tight Day = Daily Range ≤ (2/3 × ADR)

A+ Setup requires: 2-3 consecutive tight days
```

### Example Calculation
```
Stock ADR (14-day): 6%
Tightness Threshold: 6% × (2/3) = 4%

Recent Days:
  Day 1: Low $50.00, High $52.50 → Range = 5.0% (NOT tight)
  Day 2: Low $51.00, High $52.80 → Range = 3.5% (TIGHT ✓)
  Day 3: Low $51.50, High $53.00 → Range = 2.9% (TIGHT ✓)
  Day 4: Low $51.80, High $53.10 → Range = 2.5% (TIGHT ✓)

Days 2-4 show tightness. Setup is forming.
```

### Visual Representation
```
Wide volatility (early consolidation):

     |         |         |
     |         |         |
     |---------|---------|
     |         |         |
     |         |         |

Tightening (setup forming):

                         |---|---|---|
                         (smaller candles, less range)
```

### Why It Matters

1. **Tightness = Low Risk Entry**
   - When range is small, your stop (LOD) is close to your entry
   - Same position size, much smaller dollar risk

2. **Tightness = Coiled Energy**
   - Low volatility often precedes high volatility
   - Buyers and sellers in equilibrium; breakout resolves the tension

3. **Automatic Risk Control**
   > "If you only trade tight charts, you dont need to calculate risk. LOD stop will on average be < .5% of your account. If you size correctly."

### Tightness Checklist
- [ ] ADR calculated for stock
- [ ] Tightness threshold calculated (2/3 × ADR)
- [ ] At least 2-3 consecutive days with range ≤ threshold
- [ ] Tightness occurring near rising MA (10 or 20-day)
- [ ] Volume contracting during tight days
- [ ] Clear pivot level formed at top of tight range

### Example: Risk Comparison

**Without Tightness**:
```
Entry: $50.00
Stop (consolidation low): $46.00
Risk per share: $4.00 (8%)
```

**With Tightness**:
```
Entry: $50.00
Stop (LOD of tight candle): $49.00
Risk per share: $1.00 (2%)
```

Same entry point, 75% less risk — this is why tightness is mandatory for A+ setups.

---

## Summary Table

| Term | One-Line Definition | Primary Use | Where to Find |
|------|---------------------|-------------|---------------|
| **ADR** | Average daily price range as % | Filter for volatility; calculate tightness | ATR indicator / manual calc |
| **LOD** | Lowest price of the day | Initial stop-loss placement | Any chart (candlestick low) |
| **RS** | Stock performance vs. market | Filter for leaders | Finviz performance / TradingView compare |
| **EP** | Gap up on earnings/news + huge volume | High-potential setup (advanced) | Earnings calendars + price/volume screens |
| **Consolidation** | Sideways rest period after trend | Where setups form | Visual chart analysis |
| **Pivot** | Price level triggering entry/exit | Objective decision points | Horizontal lines on chart |
| **Tightness** | Low volatility within consolidation | Defines A+ quality; controls risk | Daily range vs. ADR calculation |

---

## Quick Reference Formulas

### ADR Calculation
```
Daily Range % = (High - Low) / Low × 100
ADR = Sum of Daily Range % over N days / N
```

### Tightness Check
```
Tight Day = Daily Range ≤ (ADR × 0.667)
```

### Risk Per Share
```
Risk = Entry Price - Stop Price
Risk % = Risk / Entry Price × 100
```

### Position Size (Framework Standard)
```
Position $ = Account Equity × 0.15 (or 0.10 to 0.20)
Shares = Position $ / Entry Price
```

### Risk Validation
```
Total Risk $ = Shares × (Entry - Stop)
Max Allowed Risk = Account Equity × 0.005

If Total Risk $ > Max Allowed Risk → Setup invalid OR reduce shares
```

---

## Next Steps

With these terms understood:
1. **Phase 0.2**: Set up TradingView and Finviz accounts
2. **Phase 0.3**: Apply these concepts to real historical charts
3. **Phase 1**: Begin building your Trading Plan using these terms precisely

---

*Document Version: 1.0*  
*Part of: Swing Trading System Development*
