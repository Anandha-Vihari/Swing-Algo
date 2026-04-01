# ADAPTIVE TREND STRATEGY - MT5 SETUP GUIDE
## For Your PC with MetaTrader 5

### STEP 1: Install MT5 Connection (Python)
```bash
pip install MetaTrader5
```

### STEP 2: Compile EA in MT5
1. Open MetaTrader 5
2. Click: File → Open Data Folder
3. Navigate: MQL5 → Experts
4. Copy `AdaptiveStrategy.mq5` here
5. In MT5, press F4 (Navigator)
6. Right-click Experts folder → Refresh
7. Right-click AdaptiveStrategy → Compile

### STEP 3: Backtest in MT5 Strategy Tester
1. Open MT5
2. Press Ctrl+R (Strategy Tester)
3. Expert Advisor: AdaptiveStrategy
4. Symbol: EURUSD
5. Period: H4 (4H)
6. Date Range: Last 2 years
7. Run backtest

### STEP 4: Check Results
- Look for **Win Rate > 55%**
- Check **Profit Factor > 1.5**
- Verify **Max Drawdown < 30%**

---

## Expected Results on Your PC:
- Better accuracy than yfinance (MT5 uses broker data)
- Real slippage modeling
- More reliable backtests
- Can test on different accounts/spreads

## Parameters to Optimize:
1. TREND_STRENGTH (6-8)
2. BREAKOUT_PIPS (8-15)
3. SL_PIPS (30-80)
4. RR_RATIO (1.8-2.5)

---

## Alternative: Python MT5 Backtester
See: `mt5_backtest_connector.py`
