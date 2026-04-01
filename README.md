# Production-Grade 4H Structure-Based Algorithmic Trading Bot

A professional, modular trading system implementing break-of-structure (BOS), change-of-character (CHOCH), and support/resistance-based strategies on 4-hour timeframes.

**NEW:** Real-time forex data fetching via yfinance! See [Data Fetcher Guide](#data-fetcher-module) below.

## Features

✅ **Modular Architecture** - Clean separation of concerns across data, strategy, risk, and execution
✅ **Structure-Based Trading** - BOS, CHOCH, and S/R zone detection
✅ **Advanced Risk Management** - Trailing stops (1R → breakeven, 2R → trail), 1:2 minimum RR
✅ **Candle-Close Entry** - No intra-candle execution, wait for confirmed candle closure
✅ **Multi-Pair Support** - Scan EURUSD, GBPUSD, USDJPY, XAUUSD simultaneously
✅ **Backtesting Engine** - Full equity curve, drawdown, win rate analysis
✅ **Paper Trading Mode** - Test strategies with simulated execution
✅ **Production-Ready** - Logging, error handling, configurable parameters

---

## Project Structure

```
.
├── config.py              # Centralized configuration (BotConfig, TradeConfig, StrategyConfig)
├── data_handler.py        # OHLCV data fetching & 4H alignment (MT5, CSV sources)
├── strategy.py            # Core trading logic (BOS, CHOCH, support/resistance analysis)
├── risk_manager.py        # Position sizing, trailing stops, P&L tracking
├── execution.py           # Order placement & candle-close logic
├── backtest.py            # Historical backtesting engine
├── bot.py                 # Main orchestrator (live/paper trading loops)
├── utils.py               # Helper functions (pip calculations, metrics)
├── data_generator.py      # Synthetic data for testing
├── examples.py            # Usage examples
├── main.py                # CLI entry point
└── requirements.txt       # Python dependencies
```

---

## Installation

```bash
# Clone and setup
git clone <repo>
cd trading-bot
python -m venv venv
source venv/bin/activate  # On Windows: venv\Scripts\activate

# Install dependencies
pip install -r requirements.txt

# (Optional) For live trading, install MetaTrader5
pip install MetaTrader5
```

---

## Quick Start

### 1. Generate Sample Data
```bash
python main.py setup-data
```
This creates synthetic 4H OHLCV data in `./data/` for testing.

### 2. Run Backtest
```bash
python main.py backtest --symbols EURUSD GBPUSD --export --plot
```

### 3. Analyze Single Signal
```bash
python main.py analyze-signal EURUSD
```

### 4. Paper Trading
```bash
python main.py paper-trading --iterations 10 --interval 30
```

### 5. Show Configuration
```bash
python main.py config
```

---

## 🌍 Data Fetcher Module (NEW!)

Fetch real-time forex data from Yahoo Finance for 4-hour backtesting and live trading.

### Quick Start

**Fetch data (2 minutes):**
```bash
python fetch_and_backtest.py
```

This automatically:
1. Fetches 2 years of 1H data for major forex pairs
2. Resamples to 4H candles
3. Validates data quality
4. Saves to `./data/*.csv`
5. Runs backtest

**Use cached data (instant):**
```bash
python fetch_and_backtest.py --skip-fetch
```

### Supported Pairs

**Major**: EURUSD, GBPUSD, USDJPY, USDCAD, AUDUSD, NZDUSD, USDCHF
**Cross**: EURGBP, EURJPY, GBPJPY, AUDJPY, NZDJPY
**Commodities**: XAUUSD (Gold), XAGUSD (Silver)

### API Example

```python
from data_fetcher import ForexDataFetcher

# Fetch data
fetcher = ForexDataFetcher()
data = fetcher.fetch_all_pairs(use_cache=True)

# Get specific pair
eurusd_df = data['EURUSD']
print(f"EURUSD: {len(eurusd_df)} candles")
print(eurusd_df.head())

# Export summary
summary = fetcher.export_summary_to_csv()
```

### Integration with Trading Bot

```python
from bot_data_pipeline import prepare_data_for_backtest
from backtest import Backtester

# Fetch real data
h4_data = prepare_data_for_backtest(pairs=['EURUSD', 'GBPUSD'])

# Backtest
backtester = Backtester(config)
for pair, df in h4_data.items():
    result = backtester.run_backtest(pair)
    result.print_summary()
```

### Data Format

Files saved as: `./data/EURUSD_H4.csv`

```
datetime,open,high,low,close,volume
2024-04-01 00:00:00,1.08524,1.08745,1.08412,1.08690,15234500
2024-04-01 04:00:00,1.08691,1.09012,1.08650,1.08920,14892300
```

### Documentation

- **[DATA_FETCHER_GUIDE.md](DATA_FETCHER_GUIDE.md)** - Full API reference and examples
- **[DATA_FETCHER_QUICK_REFERENCE.md](DATA_FETCHER_QUICK_REFERENCE.md)** - Quick lookup guide

---

## Core Strategy Logic

### 1. Trend Detection
Uses **EMA 50/200** crossover:
- **Bullish**: EMA50 > EMA200
- **Bearish**: EMA50 < EMA200
- **Sideways**: Avoids entry if EMAs are flat

### 2. Break of Structure (BOS)
- **Bullish BOS**: Price closes above recent swing high
- **Bearish BOS**: Price closes below recent swing low
- Requires confirmation with RSI alignment

### 3. Change of Character (CHOCH)
- **Bullish CHOCH**: Shift from LH/LL to HH/HL
- **Bearish CHOCH**: Shift from HH/HL to LH/LL
- Detects market structure reversals

### 4. Support/Resistance
- Swing levels clustered by proximity (±50 pips)
- Bounces from support = bullish signal
- Rejections from resistance = bearish signal

### 5. RSI Confirmation
- Bullish: RSI > 45 (above midpoint, not overbought)
- Bearish: RSI < 55 (below midpoint, not oversold)
- Avoids counter-trend entries

### 6. Volume Confirmation (Optional)
- Current candle volume > 20-period MA × 1.2
- Validates strength of move

---

## Risk Management System

### Position Sizing
```
Risk ($) = Account × Risk%
Lot Size = Risk / (Distance_Pips × Pip_Cost)
```

**Default:** 1.5% risk per trade on $10,000 = $150 risk

### Stop Loss Placement
- **Bullish**: Below structure level (swing low)
- **Bearish**: Above structure level (swing high)

### Take Profit Requirement
- **Minimum RR = 1:2**
- TP calculated to achieve 2:1 reward/risk

### Trailing Stop Strategy
```
At +1R:  Move SL to entry (breakeven)
At +2R:  Trail SL by 50 pips
```

**Example (Bullish, 1.1000 entry, 1.0950 SL):**
- Risk = 50 pips = 1R
- At profit of 50 pips: SL moves to 1.1000
- At profit of 100 pips: SL trails to 1.0950 + buffer

---

## Trading Logic Flow

```
┌─────────────────────────────────────────┐
│ 1. Scan All Symbols (30-min intervals)  │
├─────────────────────────────────────────┤
│ 2. For each symbol:                     │
│    - Fetch latest 500 × 4H candles      │
│    - Detect trend (EMA 50/200)          │
│    - Check BOS/CHOCH                    │
│    - Validate RSI & volume              │
│    - Queue signal if valid              │
├─────────────────────────────────────────┤
│ 3. Check Pending Signals                │
│    - Wait for candle close              │
│    - Execute on next candle open        │
│    - Calculate position size            │
│    - Place order (paper/live)           │
├─────────────────────────────────────────┤
│ 4. Monitor Positions                    │
│    - Update trailing stops              │
│    - Check SL/TP hits                   │
│    - Log P&L                            │
│    - Close trades when triggered        │
├─────────────────────────────────────────┤
│ 5. Report & Repeat                      │
│    - Print performance stats            │
│    - Loop every 30 minutes              │
└─────────────────────────────────────────┘
```

---

## Configuration

Edit `config.py` to customize:

```python
# Risk parameters
risk_percent_per_trade = 1.5      # 1-2% per trade
min_risk_reward_ratio = 2.0       # 1:2 minimum

# Trading limits
max_concurrent_trades = 3         # Max 3 open positions
max_risk_per_symbol = 2.0         # Max 2% per symbol

# Strategy tuning
ema_fast = 50                     # Fast moving average
ema_slow = 200                    # Slow moving average
rsi_period = 14                   # RSI lookback
support_resistance_proximity = 50 # ±pips for clustering

# Symbols
symbols = [
    Symbol(pair="EURUSD", pip_value=0.0001, pip_cost=10.0),
    Symbol(pair="GBPUSD", pip_value=0.0001, pip_cost=10.0),
    Symbol(pair="USDJPY", pip_value=0.01, pip_cost=9.0),
    Symbol(pair="XAUUSD", pip_value=0.01, pip_cost=100.0),
]
```

---

## API Overview

### DataHandler
```python
from data_handler import DataHandler
from config import TimeFrame

dh = DataHandler(config)
candles = dh.get_ohlcv_objects("EURUSD", TimeFrame.H4, periods=500)
df = dh.fetch_data("EURUSD", TimeFrame.H4)
```

### StrategyEngine
```python
from strategy import StrategyEngine

engine = StrategyEngine(config)
signal = engine.analyze("EURUSD", candles)
# signal: SignalContext with direction, entry, SL, TP, RR
```

### RiskManager
```python
from risk_manager import RiskManager

rm = RiskManager(config)
trade = rm.create_trade(
    symbol="EURUSD",
    direction="long",
    entry_price=1.1000,
    stop_loss=1.0950,
    take_profit=1.1100,
    lot_size=0.1,
    account_balance=10000
)
rm.open_trade(trade)

# Monitor
rm.update_trailing_stop(trade, current_price=1.1050)
rm.check_stop_loss(trade, current_price=1.0945)
rm.check_take_profit(trade, current_price=1.1100)
```

### ExecutionEngine
```python
from execution import ExecutionEngine

ee = ExecutionEngine(config, risk_manager, data_handler)
ee.queue_signal("EURUSD", signal_context)
ee.check_candle_close_and_execute("EURUSD", current_candle)
ee.monitor_and_update_positions("EURUSD", current_candle, account_balance)
```

### Backtester
```python
from backtest import Backtester

backtester = Backtester(config)
result = backtester.run_backtest("EURUSD")

result.print_summary()
backtester.export_trades_to_csv(result, "trades.csv")
backtester.plot_equity_curve(result, "equity.png")
```

---

## Example: Full Backtest

```python
from config import BotConfig
from backtest import Backtester

config = BotConfig(
    initial_capital=50000,
    data_source="csv"
)

backtester = Backtester(config)
result = backtester.run_backtest("EURUSD")

print(f"Total Trades: {result.total_trades}")
print(f"Win Rate: {result.win_rate:.1f}%")
print(f"Profit Factor: {result.profit_factor:.2f}")
print(f"Max Drawdown: {result.max_drawdown:.2f}%")
print(f"Return: {result.total_return_percent:+.2f}%")
```

---

## Example: Paper Trading Session

```python
from config import BotConfig
from bot import TradingBot

config = BotConfig(
    live_trading=False,
    paper_trading=True,
    initial_capital=10000
)

bot = TradingBot(config)
bot.start()

for i in range(10):  # 10 scan cycles
    bot.scan_all_symbols()
    bot.update_positions()
    bot._print_status()
    import time
    time.sleep(30)  # 30 seconds between scans

bot.stop()
```

---

## Production Deployment

### Prerequisites
- MetaTrader 5 terminal running on the machine
- Live account with broker
- Stable internet connection

### Configuration
1. Update `config.py` with real account parameters
2. Set `live_trading=True`, `paper_trading=False`
3. Configure broker credentials (if applicable)

### Monitoring
- Check `trading_bot.log` for all activities
- Export trades: `backtester.export_trades_to_csv(...)`
- Monthly performance review of equity curve

### Risk Controls
- Start with max 1% risk per trade
- Limit to 2-3 concurrent trades
- Monitor max drawdown - stop if > 20%
- Review strategy weekly

---

## Backtesting Interpretation

**Good System:**
- Win Rate: > 50%
- Profit Factor: > 1.5
- Max Drawdown: < 15%
- Avg Win > Avg Loss (ideally 2:1)

**Red Flags:**
- Win Rate < 40% (needs better entries)
- Consecutive losses > 5 (poor risk management)
- Drawdown > 30% (too aggressive)
- Profit Factor < 1.0 (losing system)

---

## Logging & Debugging

### Log Levels
```bash
python main.py --log-level DEBUG backtest      # Verbose
python main.py --log-level INFO paper-trading  # Standard
python main.py --log-level WARNING live-trading # Quiet
```

### Common Issues

**"No data returned for EURUSD"**
- Ensure MT5/data source is accessible
- Check if CSV file exists in `./data/` directory
- Verify timeframe alignment (4H candles)

**"Lot size too small / invalid"**
- Risk calculation creates lot < min_lot (0.01)
- Reduce risk_percent_per_trade or increase account balance

**"Max concurrent trades limit reached"**
- Too many signals generated simultaneously
- Increase max_concurrent_trades or adjust strategy filters

---

## Performance Optimization

- **Reduce scan frequency** from 30 min to 60 min to lower CPU
- **Cache OHLCV data** (currently 30-min TTL)
- **Use paper trading** before live for strategy validation
- **Profile code** with cProfile for bottlenecks

---

## License

This project is provided as-is for educational and trading purposes.

**Disclaimer:** Trading involves substantial risk of loss. Past performance does not guarantee future results. Use at your own risk.

---

## Contributing

Improvements welcome! Areas for enhancement:
- MT5 real-time price feed integration
- Telegram/Discord alert notifications
- Advanced pattern recognition (Harmonic, Elliot Wave)
- Machine learning-based signal filtering
- Multi-timeframe confirmation logic

---

## Support

For issues or questions:
1. Check the examples in `examples.py`
2. Review `main.py` CLI help: `python main.py --help`
3. Enable DEBUG logging: `--log-level DEBUG`
4. Check `trading_bot.log` for detailed error messages

---

**Last Updated:** 2026-04-01
**Version:** 1.0.0 (Production)
