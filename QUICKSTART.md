# Quick Start Guide

Get the trading bot running in 5 minutes.

## Step 1: Setup
```bash
python -m venv venv
source venv/bin/activate  # Windows: venv\Scripts\activate
pip install -r requirements.txt
```

## Step 2: Generate Sample Data
```bash
python main.py setup-data
```
Creates synthetic 4H data in `./data/` for testing.

## Step 3: Run Your First Backtest
```bash
python main.py backtest --export --plot
```

Output:
```
============================================================
BACKTEST RESULTS
============================================================
Period: 2025-04-01 00:00:00 to 2026-04-01 00:00:00

Capital:
  Initial:      $10,000.00
  Final:        $11,250.50
  Net Profit:   $1,250.50
  Return:       +12.51%

Trade Statistics:
  Total Trades: 24
  Winning:      16 (66.7%)
  Losing:       8 (33.3%)
  Profit Factor: 2.15

Drawdown & Risk:
  Max Drawdown: 8.3%
  Largest Win:  $425.00
  Largest Loss: -$150.00
  Avg Win:      $156.25
  Avg Loss:     -$93.75
============================================================
```

## Step 4: Analyze a Single Signal
```bash
python main.py analyze-signal EURUSD
```

Output:
```
============================================================
SIGNAL FOUND for EURUSD
Direction:      BULLISH
Entry Price:    1.10500
Stop Loss:      1.10200
Take Profit:    1.11400
Risk/Reward:    2.50
Confirmation:   bos
Timestamp:      2026-04-01 12:00:00
============================================================
```

## Step 5: Paper Trade (Simulation)
```bash
python main.py paper-trading --iterations 5 --interval 30
```

This runs 5 scan cycles with 30-second delays between each.

## Step 6: Check Configuration
```bash
python main.py config
```

## What Happens Next?

### Run Backtests on Different Symbols
```bash
python main.py backtest --symbols EURUSD GBPUSD USDJPY
```

### Export Trade List
```bash
python main.py backtest --symbols EURUSD --export
# Creates: trades_EURUSD.csv
```

### Plot Equity Curve
```bash
python main.py backtest --symbols EURUSD --plot
# Creates: equity_EURUSD.png
```

### Modify Strategy Parameters
Edit `config.py`:
```python
strategy_config=StrategyConfig(
    ema_fast=50,           # Change EMA period
    ema_slow=200,
    rsi_period=14,         # Adjust RSI sensitivity
    detect_bos=True,       # Enable/disable BOS
    detect_choch=True,     # Enable/disable CHOCH
)
```

### Adjust Risk Parameters
Edit `config.py`:
```python
trade_config=TradeConfig(
    risk_percent_per_trade=1.5,    # 1% or 2%
    min_risk_reward_ratio=2.0,     # 1:2 minimum RR
    max_concurrent_trades=3,       # Max open positions
    trailing_stop_distance_r=1.0,  # Trail at +1R
)
```

---

## Common Commands

```bash
# Backtest all symbols with export
python main.py backtest --export --plot

# Backtest specific symbols
python main.py backtest --symbols EURUSD GBPUSD

# Paper trade simulation (10 cycles)
python main.py paper-trading --iterations 10

# Analyze signal for a symbol
python main.py analyze-signal EURUSD
python main.py analyze-signal GBPUSD
python main.py analyze-signal USDJPY

# Show current config
python main.py config

# Increase verbosity
python main.py --log-level DEBUG backtest

# Generate sample data
python main.py setup-data
```

---

## Understanding Backtest Results

**Good Strategy Signs:**
- ✅ Win Rate > 50%
- ✅ Profit Factor > 1.5
- ✅ Max Drawdown < 15%
- ✅ Avg Win : Avg Loss ratio ≥ 2:1

**Red Flags:**
- ❌ Win Rate < 40% (need better entry signal)
- ❌ Profit Factor < 1.0 (losing strategy)
- ❌ Drawdown > 30% (too aggressive)
- ❌ Max loss > 3× avg loss (risk management issue)

---

## Next Steps for Live Trading

1. **Paper Trade First**
   ```bash
   python main.py paper-trading --iterations 100
   ```
   Run for at least 20-30 simulated trades to validate logic.

2. **Review Logs**
   - Check `trading_bot.log` for any errors
   - Ensure entries match your strategy rules
   - Verify SL/TP calculations

3. **Optimize Parameters**
   - If win rate too low: adjust RSI threshold or add filters
   - If risk per trade too high: reduce `risk_percent_per_trade`
   - If few signals: loosen structure criteria

4. **Enable Live Trading**
   ```bash
   # First, ensure MT5 is running with live account
   # Edit config.py:
   live_trading = True
   paper_trading = False

   # Then:
   python main.py live-trading --force
   ```

---

## Troubleshooting

**"No data returned for EURUSD"**
```bash
python main.py setup-data  # Generate sample data
```

**"Lot size too small"**
- Increase account balance in config
- Reduce risk percentage
- Increase stop loss distance

**"Max concurrent trades limit reached"**
- Increase `max_concurrent_trades` in config
- Or wait for a trade to close

**"Signal not executing"**
- Check RSI confirmation is aligned
- Ensure volume check passes (if enabled)
- Verify RR ratio is at least 1:2

**"Paper trading not creating trades"**
- Enable DEBUG logging: `--log-level DEBUG`
- Check if signals are being generated: `analyze-signal EURUSD`
- Verify strategy config isn't too strict

---

## File Reference

| File | Description |
|------|-------------|
| `config.py` | All parameters (edit here to customize) |
| `data_handler.py` | Data fetching & validation |
| `strategy.py` | Trading signals (BOS, CHOCH, S/R) |
| `risk_manager.py` | Position sizing & stops |
| `execution.py` | Order placement & monitoring |
| `backtest.py` | Backtesting engine |
| `bot.py` | Main orchestrator |
| `main.py` | CLI (run: `python main.py --help`) |
| `utils.py` | Utility functions |
| `examples.py` | Usage examples |
| `data_generator.py` | Create synthetic data |
| `requirements.txt` | Python dependencies |
| `README.md` | Full documentation |
| `ARCHITECTURE.md` | System design details |

---

## Real-World Example

### Scenario: You want to trade EURUSD with 2% risk
Edit `config.py`:
```python
BotConfig(
    initial_capital=50000,
    trade_config=TradeConfig(
        risk_percent_per_trade=2.0,  # 2% = $1000
        min_risk_reward_ratio=2.0,
        max_concurrent_trades=3,
    ),
    symbols=[
        Symbol(pair="EURUSD", ...),
    ]
)
```

### Run backtest to validate
```bash
python main.py backtest --symbols EURUSD --export
```

### Check results
```
Winning:      18 (72%)
Profit Factor: 2.8
Max Drawdown: 12%
Net Profit:   +$4,200
Return:       +8.4%
```

### If results look good, paper trade
```bash
python main.py paper-trading --iterations 50
```

### Monitor
```
[2026-04-01 14:00] Trade #1: EURUSD LONG @ 1.10500
[2026-04-01 18:00] Trade #1: TP hit @ 1.11400 | +$1000 (+2.0%)
[2026-04-02 02:00] Trade #2: EURUSD SHORT @ 1.11500
...
```

### Ready for live?
```bash
# Ensure MT5 is running with live account
python main.py live-trading
```

---

## Tips & Best Practices

1. **Always paper trade first** - Never go live without testing
2. **Monitor the first week** - Watch for unexpected behavior
3. **Keep risk small** - 1-2% per trade, max 10% drawdown before review
4. **Avoid over-optimization** - Don't tune parameters to backtest data
5. **Log everything** - Check `trading_bot.log` for every action
6. **Review weekly** - Analyze closed trades for pattern improvements
7. **Scale gradually** - Start with 1 symbol, then add more

---

## Need Help?

- Run: `python main.py --help`
- Check: `trading_bot.log`
- Read: `README.md` and `ARCHITECTURE.md`
- Enable debug: `--log-level DEBUG`

**Discord/Support Coming Soon**

---

Happy Trading! 📈
