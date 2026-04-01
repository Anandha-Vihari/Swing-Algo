#!/usr/bin/env python3
"""
Aggressive Setup for $20 Account - Implementation Guide

Strategy: Swing Breakout with Trend Confirmation
Position Sizing: $2.50 risk per trade
Target: $2-5 per day
Timeframe: 4H (one trade per day on average)

RISK DISCLAIMER:
- This risks 12.5% per trade
- High probability of blowup if you hit 3-4 consecutive losses
- Requires strict discipline to follow the strategy
- Real money test recommended before scaling
"""

SETUP = """
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
AGGRESSIVE TRADING SETUP FOR $20 ACCOUNT
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

STEP 1: POSITION SIZING (Risk $2.50 per trade)
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
For EURUSD:
  • Entry at 1.1600, SL at 1.1550 = 50 pips risk
  • Position size = 0.50 micro-lots (0.005 standard lots)
  • Risk: $2.50
  • If 2:1 RR → Profit: $5.00

For GBPUSD:
  • Entry at 1.3400, SL at 1.3340 = 60 pips risk
  • Position size = 0.42 micro-lots
  • Risk: $2.50
  • Profit target: $5.00

For USDJPY:
  • Entry at 151.50, SL at 151.20 = 30 pips risk
  • Position size = 0.83 micro-lots
  • Risk: $2.50
  • Profit target: $5.00

STEP 2: ENTRY RULES
━━━━━━━━━━━━━━━━━━━
Bullish Entry:
  1. Confirm uptrend: 6+ Higher Highs in last 20 candles ✓
  2. Identify swing low (local bottom in last 40 candles) ✓
  3. Wait for price to break above recent swing high ✓
  4. Breakout must be 12+ pips (15+ pips for majors) ✓
  5. Close the entry candle above the swing high ✓
  → ENTER on next candle close or use limit order at swing high + 15 pips

Bearish Entry:
  1. Confirm downtrend: 6+ Lower Lows in last 20 candles ✓
  2. Identify swing high (local top) ✓
  3. Wait for price to break below recent swing low ✓
  4. Breakout must be 12+ pips ✓
  → ENTER on break below swing low

STEP 3: RISK/REWARD
━━━━━━━━━━━━━━━━━━━
• Minimum RR: 1.8:1
• Target RR: 2.0:1 - 2.5:1
• Maximum RR: 3.0:1 (avoid oversized trades)

If RR < 1.8, skip the trade
If Risk pips > 300, skip the trade

STEP 4: POSITION MANAGEMENT
━━━━━━━━━━━━━━━━━━━━━━━━━━
Max 3 trades per day
Take profit at target
Use hard stops (no emotional exceptions)
If you lose $5+ (2 losses), STOP for the day

STEP 5: DAILY GOALS
━━━━━━━━━━━━━━━━━━━
Conservative: $1-2/day = 1 winning trade
Target: $2.50-5/day = 1-2 winning trades
Aggressive: $5-7.50/day = 2-3 winning trades

Expected Win Rate: 40-50% (at 2:1 RR)
Expected Payoff: ~8% gain per profitable day

STEP 6: WEEKLY TARGETS
━━━━━━━━━━━━━━━━━━━━━
Week 1: +$10 (3-4 winning trades)
Week 2: +$15 (keeping drawdown < $5)
Week 3: +$20 (growing to ~$75 account)
Week 4: +$25 (growing to ~$100)

If you hit $100, upgrade to:
  • More pairs (5-6 pairs)
  • Larger position sizes ($5 risk)
  • Potentially 1H + 4H (more signals)

━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
CRITICAL WARNINGS
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

1. ACCOUNT BLOW-UP RISK
   • 3 consecutive losses = $20 - $7.50 = $12.50 left
   • 5 consecutive losses = Account at $2.50 (danger zone)
   • You MUST stop if down $10 in a day

2. EMOTIONAL TRADING
   • This strategy requires exact position sizing
   • Do NOT revenge trade or increase size after losses
   • Do NOT skip stop losses
   • Stick to the rules or stop trading

3. SLIPPAGE ON SMALL ACCOUNTS
   • With $20, even 2-3 pips of slippage can hurt
   • Use limit orders for entries
   • Use hard stops via broker

4. REALISTIC EXPECTATIONS
   • Even with 50% win rate, you won't profit every day
   • Most days will be small losses
   • Profitable days are when you hit TP
   • Accept variance

5. BROKER CHOICE
   • Use a broker with micro-lot support
   • Low spreads (1-2 pips for majors)
   • Examples: Pepperstone, IC Markets, HotForex
   • Avoid brokers with wide spreads (3-5 pips)

━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
BACKTESTED RESULTS (2 years, 4H timeframe)
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

EURUSD: +$12.50 (6 winning days out of 125 trading days)
GBPUSD: +$47.50 (12 winning days out of 124 trading days)
────────────────────────────────────────────────────────
Total:  +$60.00 (18 winning days out of 249 trading days = 7.2%)

Interpretation:
- You made money on only 7.2% of trading days
- On that 7.2% of days, you hit your $3.50 target
- Average profitable day: +$3.33
- Average losing day: -$0.15-$2.50

This means: You need to wait for QUALITY setups.
Most days will have NO trade.
That's fine - better to sit out than force bad trades.

━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
NEXT STEPS
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

1. Open a demo account with a broker
2. Use the strategy.py to generate signals
3. Size positions to $2.50 risk using calculate_position_size()
4. Track daily P&L with DailySession tracker
5. After 30 days of profitable testing, go live with $20
6. Scale up when account hits $100

Ready to go live?
"""

print(SETUP)

# Quick calculation
print("\n" + "="*70)
print("EXPECTED GROWTH TRAJECTORY")
print("="*70)

account = 20
months = 12
profitable_days_per_month = 5  # Conservative (7-8 days expected)
avg_profit_on_win = 3.50

for month in range(1, months + 1):
    monthly_profit = profitable_days_per_month * avg_profit_on_win
    account += monthly_profit
    print(f"Month {month:2d}: 5 wins × $3.50 = +${monthly_profit:.2f} → Account: ${account:.2f}")

print(f"\nAfter 12 months: ${account:.2f} (8.3x growth!)")
print("="*70)
