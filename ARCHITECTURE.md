# Architecture & Design Document

## Overview

This is a production-grade algorithmic trading system built with modular, separation-of-concerns design. The bot analyzes 4-hour forex/commodity charts for break-of-structure (BOS), change-of-character (CHOCH), and support/resistance patterns, then executes trades with strict risk management.

---

## System Architecture

### Layered Design

```
┌─────────────────────────────────────────────────┐
│         CLI / Main Entry (main.py)              │
├─────────────────────────────────────────────────┤
│    Orchestrator Layer (bot.py)                  │
│  - TradingBot (live/paper loop)                 │
│  - BotMonitor (performance reporting)           │
│  - Multi-symbol scanning & coordination         │
├─────────────────────────────────────────────────┤
│    Execution & Risk Management Layer            │
│  - ExecutionEngine (candle-close logic)         │
│  - RiskManager (position sizing, stops)         │
│  - PositionSizer (lot calculations)             │
├─────────────────────────────────────────────────┤
│    Strategy Analysis Layer                      │
│  - StrategyEngine (main signal generation)      │
│  - StructureAnalyzer (BOS, CHOCH, S/R)         │
│  - ConfirmationAnalyzer (RSI, volume checks)   │
├─────────────────────────────────────────────────┤
│    Data Layer                                   │
│  - DataHandler (OHLCV fetching & validation)   │
│  - OHLCV (individual candle objects)           │
│  - Timeframe alignment & caching               │
├─────────────────────────────────────────────────┤
│    Configuration Layer (config.py)              │
│  - BotConfig, TradeConfig, StrategyConfig      │
│  - Symbol definitions                          │
│  - Parameter centralization                    │
├─────────────────────────────────────────────────┤
│    Utilities & Testing                          │
│  - Backtester (historical analysis)            │
│  - utils.py (metrics, calculations)             │
│  - data_generator.py (synthetic data)          │
└─────────────────────────────────────────────────┘
```

---

## Module Responsibilities

### 1. config.py
**Purpose:** Centralized configuration management

**Classes:**
- `TimeFrame(Enum)` - Supported timeframes (H4, H1, D1)
- `TradeConfig` - Risk & execution parameters
- `StrategyConfig` - Strategy tuning parameters
- `Symbol` - Per-symbol configuration (pip value, lot constraints)
- `BotConfig` - Main configuration container

**Key Features:**
- Immutable dataclass-based config
- Factory methods (`get_symbol_config()`)
- Type hints for type safety
- No hardcoding of parameters

---

### 2. data_handler.py
**Purpose:** Data sourcing, validation, and alignment

**Classes:**
- `OHLCV` - Single candle object with calculations (HL2, HLC3, OHLC4)
- `DataHandler` - Main data management

**Key Methods:**
- `fetch_data()` - Gets OHLCV from MT5 or CSV
- `_align_timeframe()` - Ensures proper 4H alignment (00:00, 04:00, 08:00, etc.)
- `validate_data_integrity()` - Checks for NaN, invalid OHLC, zero volume
- `get_ohlcv_objects()` - Returns list of OHLCV objects for analysis
- `_cache` - 30-minute TTL caching to reduce API calls

**Data Sources:**
- MetaTrader5 (live terminal connection)
- CSV files (backtesting)
- Configurable source switching

**Validation:**
- OHLC relationship checks: `high >= open/close`, `low <= open/close`
- NaN detection
- Zero-volume flagging
- Candle alignment verification

---

### 3. strategy.py
**Purpose:** Core trading signal generation

**Classes:**
- `TrendDirection(Enum)` - BULLISH, BEARISH, SIDEWAYS
- `StructureLevel` - Support/resistance zone representation
- `SignalContext` - Complete signal with entry/SL/TP
- `StructureAnalyzer` - Market structure detection
- `ConfirmationAnalyzer` - Entry confirmation filters
- `StrategyEngine` - Main signal generator

**StructureAnalyzer Methods:**
1. `find_swing_highs_lows()` - Locates structural turning points
   - Uses lookback window to identify local extremes
   - Classifies as swing high or swing low

2. `detect_break_of_structure_bos()` - BOS detection
   - Bullish BOS: close > recent swing high
   - Bearish BOS: close < recent swing low
   - Returns direction + structure level

3. `detect_change_of_character_choch()` - CHOCH pattern
   - Bullish CHOCH: LH/LL → HH/HL
   - Bearish CHOCH: HH/HL → LH/LL
   - Analyzes 10-candle recent structure

4. `detect_support_resistance()` - S/R zone detection
   - Clusters swing levels by proximity (±50 pips)
   - Returns consolidated support & resistance zones
   - Uses clustering to handle zone consolidation

5. `get_trend_direction()` - Trend determination
   - EMA 50 > EMA 200 = Bullish
   - EMA 50 < EMA 200 = Bearish
   - EMA 50 ≈ EMA 200 = Sideways → skip entry

**ConfirmationAnalyzer Methods:**
- `calculate_rsi()` - RSI momentum indicator
- `check_rsi_confirmation()` - Validates entry with RSI
- `check_volume_confirmation()` - Validates volume increase

**StrategyEngine.analyze() Flow:**
```
1. Verify enough candles (>50)
2. Determine trend (EMA 50/200)
3. Skip if sideways
4. Check BOS first
5. If no BOS, check CHOCH
6. If no CHOCH, check S/R zones
7. Validate RSI alignment
8. Check volume (optional)
9. Calculate SL/TP with 1:2 minimum RR
10. Return SignalContext or None
```

---

### 4. risk_manager.py
**Purpose:** Position management and risk control

**Classes:**
- `PositionStatus(Enum)` - Trade lifecycle states
- `TradeEntry` - Entry point snapshot
- `Trade` - Complete trade object with P&L tracking
- `PositionSizer` - Lot size calculation
- `RiskManager` - Main risk management controller

**Position Sizing Logic:**
```
Risk Amount = Account Balance × Risk%
Lot Size = Risk Amount / (Distance in Pips × Pip Cost per Lot)
Bounded by: min_lot ≤ Lot Size ≤ max_lot
```

**Example:**
```
Account: $10,000
Risk: 1.5% = $150
Entry: 1.1000, SL: 1.0950 = 50 pips distance
EURUSD pip cost: $10 per 0.1 lot
Lot = $150 / (50 pips × $10/50pips for 0.1 lot) = 0.3 lots
```

**Trailing Stop Implementation:**
```
At +1R (100% of initial risk):
  - Move SL to entry price (breakeven)
  - Eliminates risk

At +2R (200% of initial risk):
  - Trail SL by 50 pips from current price
  - Locks in profit

Example (Long, Entry 1.1000, Initial SL 1.0950):
  Current 1.1050 (+50 pips = +1R):
    New SL = 1.1000 (breakeven)

  Current 1.1100 (+100 pips = +2R):
    New SL = 1.1100 - 0.0050 = 1.1050 (trail 50 pips)
```

**Trade Lifecycle:**
1. `create_trade()` - Initializes trade object
2. `open_trade()` - Registers in active_trades
3. `update_trailing_stop()` - Adjusts SL based on profit
4. `check_stop_loss()` - Exits if SL hit
5. `check_take_profit()` - Exits if TP hit
6. `close_trade()` - Calculates P&L and moves to closed_trades

**Account Statistics:**
- Win rate, profit factor, max drawdown
- Largest win/loss, average hold time
- Gross profit/loss breakdown

---

### 5. execution.py
**Purpose:** Trade placement and position monitoring

**Classes:**
- `ExecutionEngine` - Main execution controller

**Key Methods:**

1. `queue_signal()` - Stages signal waiting for candle close
   - Creates entry in `pending_signals` dict
   - Timestamps signal creation

2. `check_candle_close_and_execute()` - Candle close detection
   - Checks if new 4H candle has opened
   - Executes on next candle's open (ensures close confirmation)
   - Detects age of signal (5-hour cutoff)

3. `_execute_signal()` - Order placement
   - Validates risk limits
   - Calculates position size
   - Routes to live or paper execution
   - Registers trade with RiskManager

4. `monitor_and_update_positions()` - Position updates
   - Update trailing stops
   - Check SL/TP hits
   - Log current position status

**Candle Close Logic (Critical):**
```
Signal arrives: Queue it (don't trade immediately)
          ↓
Wait for next 4H candle open (detected by time change)
          ↓
Execute at new candle's OPEN price
          ↓
This ensures we traded after confirmed candle close
No intra-candle entries - wait for full 4H confirmation
```

---

### 6. backtest.py
**Purpose:** Historical performance analysis

**Classes:**
- `BacktestResult` - Performance metrics container
- `Backtester` - Main backtesting engine

**Backtest Flow:**
```
1. Load historical 4H candles
2. For each candle (starting at index 50):
   a. Hold current candle history
   b. Check if analysis should run (every 5 candles)
   c. Run strategy analysis
   d. Queue signal if found
   e. Check if pending signal should execute
   f. Monitor active trades
   g. Update account balance
3. Calculate final metrics
4. Export equity curve & trade list
```

**Metrics Calculated:**
- Total return %
- Win rate
- Profit factor (gross profit / abs(loss))
- Max drawdown (peak-to-trough %)
- Largest win/loss
- Average bars in trade
- Equity curve over time

---

### 7. bot.py
**Purpose:** Main orchestrator and trading loops

**Classes:**
- `TradingBot` - Main bot controller
- `BotMonitor` - Performance reporting

**Bot Lifecycle:**

1. **start()** - Initialize and log configuration
2. **scan_all_symbols()** - Signal detection phase
   - Fetches latest data for each symbol
   - Runs strategy analysis
   - Queues signals if found
   - Rate limits (5-min minimum between scans per symbol)

3. **update_positions()** - Position management phase
   - Checks pending signals for candle close
   - Executes queued signals
   - Updates trailing stops
   - Monitors SL/TP hits

4. **run_live_loop()** - Production loop
   - Continuously scans (configurable interval, default 30 min)
   - Updates positions
   - Prints status
   - Logs all activities

5. **stop()** - Graceful shutdown
   - Closes open positions (manual)
   - Prints session summary
   - Exits cleanly

---

### 8. main.py
**Purpose:** CLI interface

**Commands:**
```
backtest              Run historical backtest
paper-trading         Simulation with fake execution
live-trading          REAL TRADING (REAL MONEY)
analyze-signal        Analyze single symbol
setup-data            Generate sample data
config                Show current configuration
```

---

## Key Design Decisions

### 1. Candle-Close-Only Entry
- **Why:** Avoid false breakouts on intra-candle wicks
- **How:** Queue signal, wait for next candle open
- **Benefit:** Higher probability, less whipsaws

### 2. Modular Architecture
- **Why:** Easy to test, modify, extend components independently
- **How:** Each module has single responsibility
- **Benefit:** Can swap strategy, risk mgmt, or data source without refactoring

### 3. Configuration-Driven
- **Why:** Avoid hardcoding, enable quick parameter tuning
- **How:** All tunable params in `config.py`
- **Benefit:** Same code works for multiple strategies/accounts

### 4. Event-Based Execution
- **Why:** Mimics real trading workflow (signal → validation → execution)
- **How:** Pending signals queue, then execute on confirmation
- **Benefit:** Prevents early entries, enforces discipline

### 5. Comprehensive Logging
- **Why:** Reproducibility and debugging
- **How:** All trades, updates, errors logged to file
- **Benefit:** Can audit every decision post-trade

---

## Data Flow Diagrams

### Signal Generation
```
Historical Candles (500)
    ↓
StrategyEngine.analyze()
    ├─ TrendDirection (EMA 50/200)
    ├─ StructureAnalyzer
    │  ├─ Swing highs/lows
    │  ├─ BOS detection
    │  ├─ CHOCH detection
    │  └─ S/R zones
    └─ ConfirmationAnalyzer
       ├─ RSI check
       └─ Volume check
    ↓
SignalContext (or None)
 - Direction
 - Entry price
 - Stop loss
 - Take profit
 - Risk/reward ratio
```

### Trade Execution
```
Active Loop
    ↓
scan_all_symbols()
    ├─ Fetch latest candles
    ├─ Analyze → signal
    └─ Queue signal
    ↓
update_positions()
    ├─ Check candle close
    └─ Execute pending signal
       ├─ Validate risk limits
       ├─ Calculate lot size
       ├─ Place order
       └─ Register trade
    ↓
Monitor Active Trades
    ├─ Update trailing stops
    ├─ Check SL/TP
    └─ Log results
    ↓
Loop every 30 min
```

---

## Error Handling & Recovery

**Data Errors:**
- Missing candles → skip that symbol
- Invalid OHLC → log warning, continue
- Connection failure → retry with backoff

**Strategy Errors:**
- Insufficient data → wait for next scan
- No signal generated → continue scanning
- Invalid RR ratio → reject signal

**Execution Errors:**
- Position already open → skip new signal
- Lot size calculation fails → log error, skip
- Order placement fails → log error, manual review

**Recovery Strategy:**
1. Log all errors with context
2. Continue processing other symbols
3. Report errors in session summary
4. Never crash mid-session without cleanup

---

## Performance Considerations

**Computational:**
- EMA calculation: O(n) per candle
- Swing analysis: O(lookback²) but only on signal check
- RSI: O(period) per check
- Overall: < 1ms per symbol per scan

**Memory:**
- Cache stores last 500 candles * 5 symbols ≈ 1 MB
- Trade list grows linearly with trades

**Network:**
- MT5: API calls every 30 minutes (minimal)
- CSV: Single file read per scan

**Optimization:**
- Cache OHLCV data (30-min TTL)
- Analyze only when needed (configurable frequency)
- Batch symbol scanning
- Lazy loading of data

---

## Testing Strategy

1. **Unit Tests**
   - Test position sizing logic
   - Test structure detection
   - Test RSI confirmation

2. **Integration Tests**
   - End-to-end backtest
   - Signal → execution flow
   - Risk management calculations

3. **Backtesting**
   - Historical validation
   - Parameter sensitivity analysis
   - Drawdown resilience

4. **Paper Trading**
   - 1-2 week simulation
   - Real data, no real money
   - Verify execution logic

5. **Live Trading**
   - Start with small account
   - Monitor for 1-2 weeks
   - Adjust based on results

---

## Security & Safety

1. **No Hardcoding** - All parameters in config
2. **Graceful Degradation** - Failures don't crash bot
3. **Logging Everything** - Audit trail for compliance
4. **Risk Limits** - Enforced max drawdown, concurrent trades
5. **Manual Review** - Paper trading before live
6. **Kill Switch** - KeyboardInterrupt for emergency stop

---

## Future Enhancements

1. Multi-timeframe confirmation (4H + daily trend)
2. Harmonic pattern detection
3. Algorithmic spread analysis
4. Telegram/Discord alerts
5. ML-based signal filtering
6. Advanced position management (partial TP, scaling)
7. Correlation analysis (reduce redundant trades)
8. News event filtering

